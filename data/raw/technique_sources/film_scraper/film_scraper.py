"""
Film-Grab Image Scraper
=======================
A script to scrape high-quality film frames from Film-Grab (https://film-grab.com/).

Location:
  Cinephilia/data/raw/technique_sources/film_scraper/film_scraper.py

Output Destination:
  Cinephilia/data/film_frames/<Movie Title>/01.jpg, 02.jpg, ...

Features:
- Multi-URL scraping via `links.txt` or single URL via `.env` / CLI.
- Movie title used as folder name (e.g., `film_frames/12 Angry Men/`).
- Stills saved with clean numbering: `01.jpg`, `02.jpg`, ..., `48.jpg`.
- Smart image limit:
  - If total images <= MAX_IMAGES (default 48): downloads all images.
  - If total images > MAX_IMAGES: randomly selects 48 images while preserving chronological order.
- High-quality image extraction (full lightbox resolution, avoiding thumbnails).
- Multi-threaded concurrent downloading with retry logic.
- Saves `metadata.json` summary in each movie folder.
"""

import os
import re
import sys
import json
import random
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import urllib.request
import requests
from bs4 import BeautifulSoup

# Ensure Windows consoles don't crash on UTF-8 characters
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Determine directory paths relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Default output directory: Cinephilia/data/film_frames
DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", "film_frames"))
DEFAULT_LINKS_FILE = os.path.join(SCRIPT_DIR, "links.txt")


# ---------------------------------------------------------
# Environment & Configuration Loader
# ---------------------------------------------------------

def load_env_file(env_path=None):
    """
    Load environment variables from a .env file.
    Checks the script's directory first, then the current working directory.
    Uses `dotenv` if installed, otherwise parses simple KEY=VALUE pairs.
    """
    if env_path is None:
        script_env = os.path.join(SCRIPT_DIR, ".env")
        cwd_env = os.path.join(os.getcwd(), ".env")
        if os.path.exists(script_env):
            env_path = script_env
        elif os.path.exists(cwd_env):
            env_path = cwd_env
        else:
            return

    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)
    except ImportError:
        # Fallback manual parser
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val


def load_links_from_file(file_path: str) -> list:
    """
    Read URLs from a text file, ignoring blank lines and comments starting with '#'.
    """
    if not os.path.isabs(file_path):
        file_path = os.path.join(SCRIPT_DIR, file_path)

    if not os.path.exists(file_path):
        return []

    urls = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("http://") or line.startswith("https://"):
                urls.append(line)
    return urls


def get_config():
    """
    Parse command-line arguments and fallback to .env / environment variables.
    """
    load_env_file()

    env_output_dir = os.getenv("OUTPUT_DIR", "").strip()
    if env_output_dir:
        if not os.path.isabs(env_output_dir):
            resolved_output_dir = os.path.abspath(os.path.join(SCRIPT_DIR, env_output_dir))
        else:
            resolved_output_dir = env_output_dir
    else:
        resolved_output_dir = DEFAULT_OUTPUT_DIR

    parser = argparse.ArgumentParser(
        description="Scrape high-quality movie frames from Film-Grab (film-grab.com)"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Film-Grab movie URL OR path to a text file containing multiple links"
    )
    parser.add_argument(
        "--links-file",
        type=str,
        default=os.getenv("LINKS_FILE", "links.txt"),
        help="Path to a text file containing multiple movie URLs (default: links.txt)"
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=int(os.getenv("MAX_IMAGES", "48")),
        help="Maximum number of images to scrape per movie (default: 48)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=resolved_output_dir,
        help=f"Base folder to save movie frame folders (default: {resolved_output_dir})"
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=int(os.getenv("THREADS", "6")),
        help="Number of concurrent download threads (default: 6)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=os.getenv("CLEAN_EXISTING", "false").lower() in ("true", "1", "yes"),
        help="Clean existing images in movie directory before scraping (default: False)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=os.getenv("SKIP_EXISTING", "true").lower() in ("true", "1", "yes"),
        help="Skip movies that are already downloaded (default: True)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force re-scraping even if movie is already downloaded"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible random selection"
    )

    args = parser.parse_args()
    if args.force:
        args.skip_existing = False
        args.clean = True
    return args


# ---------------------------------------------------------
# URL & Filename Utilities
# ---------------------------------------------------------

def sanitize_folder_name(name: str) -> str:
    """
    Sanitize movie title for safe Windows folder naming.
    Replaces illegal characters (: * ? \" < > |) with dashes or spaces.
    """
    # Normalize unicode apostrophes
    name = name.replace("’", "'").replace("‘", "'")
    # Replace colons and slashes with dashes
    name = name.replace(":", " -").replace("/", " -").replace("\\", " -")
    # Remove characters not allowed on Windows
    name = re.sub(r'[*?"<>|]', "", name)
    # Collapse multiple spaces
    name = re.sub(r'\s+', " ", name).strip()
    name = name.strip(". ")
    return name or "Untitled Movie"


def get_slug_from_url(url: str) -> str:
    """
    Extract movie slug from URL, e.g.:
    https://film-grab.com/2013/11/19/12-angry-men/ -> 12-angry-men
    """
    path = urllib.parse.urlparse(url).path.strip("/")
    parts = path.split("/")
    if parts:
        return parts[-1]
    return "unknown_movie"


# ---------------------------------------------------------
# Image Extraction Logic
# ---------------------------------------------------------

def extract_movie_info_and_images(page_url: str):
    """
    Fetch the movie detail page, extract movie title, and locate all full-size frame URLs.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }

    print(f"\n[+] Fetching page: {page_url}")
    response = requests.get(page_url, headers=headers, timeout=25)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch page. HTTP Status Code: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract title
    title = None
    if "the-cinematograph.com" in page_url:
        raw_title = soup.title.get_text(strip=True) if soup.title else ""
        title = re.split(r'[-–—]\s*THE CINEMATOGRAPH', raw_title, flags=re.I)[0].strip()
    else:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True).split("–")[0].split("-")[0].strip()

    if not title:
        title = get_slug_from_url(page_url).replace("-", " ").title()

    candidate_urls = []

    # 1. Primary method: Film-Grab Photo Gallery lightbox links (highest quality)
    lightbox_anchors = soup.find_all("a", class_=lambda c: c and "bwg_lightbox" in c)
    for a in lightbox_anchors:
        href = a.get("href")
        if href:
            candidate_urls.append(urllib.parse.urljoin(page_url, href))

    # 2. Secondary fallback: check entry-content links and images (for the-cinematograph.com & non-lightbox pages)
    if not candidate_urls:
        content_container = (
            soup.find("div", class_=lambda c: c and ("entry-content" in c or "post-content" in c))
            or soup.find("article")
            or soup
        )

        for a in content_container.find_all("a"):
            href = a.get("href", "")
            lower_href = href.lower()
            if any(lower_href.endswith(ext) or ext + "?" in lower_href for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                candidate_urls.append(urllib.parse.urljoin(page_url, href))

        for img in content_container.find_all("img"):
            src = img.get("data-full-url") or img.get("data-src") or img.get("src")
            if src:
                # Strip intermediate resize dimensions (e.g. -1024x768.jpg) to obtain original full-resolution image
                full_src = re.sub(r'-\d+x\d+(\.[a-zA-Z]+)$', r'\1', src.split('?')[0])
                candidate_urls.append(urllib.parse.urljoin(page_url, full_src))

    # Clean, convert thumbnails to full resolution, and deduplicate
    cleaned_images = []
    seen = set()

    for url in candidate_urls:
        parsed = urllib.parse.urlparse(url)
        # Strip query parameters (?bwg=...) to get clean canonical image URL
        clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

        # If the URL is pointing to a thumbnail, point to the full-size version instead
        if "/photo-gallery/thumb/" in clean_url:
            clean_url = clean_url.replace("/photo-gallery/thumb/", "/photo-gallery/")

        lower_path = parsed.path.lower()
        # Filter out common non-content images
        if any(skip in lower_path for skip in ["avatar", "gravatar", "logo", "banner", "button", "wp-includes"]):
            continue

        if not any(lower_path.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            continue

        if clean_url not in seen:
            seen.add(clean_url)
            cleaned_images.append(clean_url)

    return title, cleaned_images


# ---------------------------------------------------------
# Image Downloader
# ---------------------------------------------------------

def download_single_image(url: str, save_path: str, max_retries: int = 3) -> tuple:
    """
    Download a single image file with retries and proper URL encoding.
    Returns (success: bool, save_path: str, file_size_bytes: int, error_msg: str)
    """
    encoded_url = url.replace(" ", "%20")
    netloc = urllib.parse.urlparse(url).netloc
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://{netloc}/"
    }

    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(encoded_url, headers=headers, timeout=25, stream=True)
            if resp.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                file_size = os.path.getsize(save_path)
                if file_size > 0:
                    return True, save_path, file_size, ""
                else:
                    last_error = "Downloaded 0 bytes"
            else:
                last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            last_error = str(e)

    return False, save_path, 0, last_error


# ---------------------------------------------------------
# Single Movie Scraper
# ---------------------------------------------------------

def scrape_single_movie(url: str, max_images: int = 48, base_output_dir: str = None,
                        max_threads: int = 6, seed: int = None, clean_existing: bool = False,
                        skip_existing: bool = True) -> dict:
    """
    Scrapes a single movie:
    - Creates folder named after the movie title inside `base_output_dir`
    - Saves frames as 01.jpg, 02.jpg, 03.jpg, ...
    - Saves metadata.json
    """
    if base_output_dir is None:
        base_output_dir = DEFAULT_OUTPUT_DIR

    title, all_image_urls = extract_movie_info_and_images(url)
    total_found = len(all_image_urls)

    print(f"[+] Movie Title: {title}")
    print(f"[+] Total frames found on page: {total_found}")

    if total_found == 0:
        print("[!] No images found on this page. Skipping.")
        return {"title": title, "url": url, "scraped": 0, "status": "no_images"}

    # Output folder named after the movie title
    movie_folder_name = sanitize_folder_name(title)
    output_dir = os.path.join(base_output_dir, movie_folder_name)

    # Check if already complete and should skip
    if skip_existing and os.path.isdir(output_dir):
        existing_frames = [f for f in os.listdir(output_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
        manifest_path = os.path.join(output_dir, "metadata.json")
        target_count = min(max_images, total_found)
        if len(existing_frames) >= target_count and os.path.exists(manifest_path):
            print(f"[i] Movie '{title}' already completed ({len(existing_frames)} frames present). Skipping.")
            return {
                "title": title,
                "url": url,
                "scraped": len(existing_frames),
                "available": total_found,
                "bytes": 0,
                "status": "skipped"
            }

    # 1. Select images according to the user's rule:
    #    - If total <= max_images: scrape all
    #    - If total > max_images: select max_images randomly (any frame can be present)
    if seed is not None:
        random.seed(seed)

    if total_found <= max_images:
        selected_urls = list(all_image_urls)
        print(f"[+] Found {total_found} images (<= {max_images}). Scraping ALL {total_found} images.")
    else:
        # Randomly sample max_images
        sampled = random.sample(all_image_urls, max_images)
        # Sort chronologically by original page index
        url_order = {u: i for i, u in enumerate(all_image_urls)}
        selected_urls = sorted(sampled, key=lambda u: url_order[u])
        print(f"[+] Found {total_found} images (> {max_images}). Randomly selected {max_images} frames.")

    # 2. Prepare output directory
    os.makedirs(output_dir, exist_ok=True)

    # 3. Clean existing files if requested
    if clean_existing and os.path.exists(output_dir):
        cleaned_count = 0
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            if os.path.isfile(item_path):
                try:
                    os.remove(item_path)
                    cleaned_count += 1
                except Exception:
                    pass
        if cleaned_count > 0:
            print(f"[+] Cleaned {cleaned_count} previous file(s) from {output_dir}")

    print(f"[+] Saving images to: {os.path.abspath(output_dir)}")

    # 4. Prepare download tasks: 01.jpg, 02.jpg, 03.jpg, ...
    download_tasks = []
    metadata_files = []
    digits = max(2, len(str(len(selected_urls))))

    for i, img_url in enumerate(selected_urls, start=1):
        # Extract file extension, default to .jpg
        ext = os.path.splitext(urllib.parse.urlparse(img_url).path)[1].lower() or ".jpg"
        # Naming format: 01.jpg, 02.jpg, ...
        frame_filename = f"{i:0{digits}d}{ext}"
        save_path = os.path.join(output_dir, frame_filename)

        download_tasks.append((img_url, save_path, frame_filename))

    # 5. Multi-threaded downloading
    print(f"[+] Downloading {len(download_tasks)} images using {max_threads} parallel threads...\n")

    successful_downloads = 0
    failed_downloads = 0
    total_bytes = 0

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_task = {
            executor.submit(download_single_image, task[0], task[1]): task
            for task in download_tasks
        }

        for future in as_completed(future_to_task):
            task = future_to_task[future]
            img_url, save_path, filename = task
            success, path, size, error = future.result()

            if success:
                successful_downloads += 1
                total_bytes += size
                size_kb = size / 1024
                print(f"  [+] [{successful_downloads + failed_downloads}/{len(download_tasks)}] "
                      f"Downloaded: {filename} ({size_kb:.1f} KB)")
                metadata_files.append({
                    "frame": filename,
                    "source_url": img_url,
                    "size_bytes": size,
                    "size_kb": round(size_kb, 1)
                })
            else:
                failed_downloads += 1
                print(f"  [-] Failed to download {filename}: {error}")

    # Sort metadata files by frame name for neat JSON
    metadata_files = sorted(metadata_files, key=lambda x: x["frame"])

    # 6. Save metadata manifest
    metadata = {
        "movie_title": title,
        "source_url": url,
        "scraped_at": datetime.now().isoformat(),
        "total_available_images": total_found,
        "scraped_image_count": successful_downloads,
        "failed_image_count": failed_downloads,
        "total_downloaded_mb": round(total_bytes / (1024 * 1024), 2),
        "frames": metadata_files
    }
    manifest_path = os.path.join(output_dir, "metadata.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "-" * 50)
    print(f"Movie Complete: {title}")
    print(f"  * Available:     {total_found} frames")
    print(f"  * Downloaded:    {successful_downloads} frames (01.jpg .. {successful_downloads:0{digits}d}.jpg)")
    print(f"  * Total size:    {total_bytes / (1024 * 1024):.2f} MB")
    print(f"  * Folder:        {os.path.abspath(output_dir)}")
    print("-" * 50)

    return {
        "title": title,
        "url": url,
        "scraped": successful_downloads,
        "available": total_found,
        "bytes": total_bytes,
        "status": "success" if successful_downloads > 0 else "failed"
    }


# ---------------------------------------------------------
# Main Batch Orchestrator
# ---------------------------------------------------------

def main():
    config = get_config()

    # Determine list of URLs to scrape:
    urls_to_scrape = []

    # Case 1: Target passed via CLI
    if config.target:
        if os.path.isfile(config.target):
            # Target is a file containing links
            urls_to_scrape = load_links_from_file(config.target)
            print(f"[+] Loaded {len(urls_to_scrape)} link(s) from CLI file: {config.target}")
        elif config.target.startswith("http://") or config.target.startswith("https://"):
            # Target is a direct URL
            urls_to_scrape = [config.target]
        else:
            # Check if relative file path
            candidate_path = os.path.join(SCRIPT_DIR, config.target)
            if os.path.isfile(candidate_path):
                urls_to_scrape = load_links_from_file(candidate_path)
                print(f"[+] Loaded {len(urls_to_scrape)} link(s) from file: {candidate_path}")
            else:
                print(f"[!] Error: Target '{config.target}' is neither a valid URL nor an existing file.")
                sys.exit(1)

    # Case 2: Check links file (LINKS_FILE in .env or list.txt or links.txt)
    if not urls_to_scrape:
        candidates = []
        if config.links_file:
            candidates.append(config.links_file)
        candidates.extend(["list.txt", "links.txt"])

        for cand in candidates:
            file_urls = load_links_from_file(cand)
            if file_urls:
                urls_to_scrape = file_urls
                print(f"[+] Loaded {len(urls_to_scrape)} link(s) from: {cand}")
                break

    # Case 3: Fallback to FILM_URL in .env
    if not urls_to_scrape:
        env_url = os.getenv("FILM_URL", "").strip()
        if env_url:
            urls_to_scrape = [env_url]

    # Validate that we have at least one URL
    if not urls_to_scrape:
        print("\n[!] Error: No URLs found to scrape.")
        print(f"    Please either:")
        print(f"    1. Add links (one per line) to: {DEFAULT_LINKS_FILE}")
        print(f"    2. Set FILM_URL in .env")
        print(f"    3. Pass a URL or links file on the command line:")
        print(f"       python film_scraper.py https://film-grab.com/2013/11/19/12-angry-men/")
        print(f"       python film_scraper.py links.txt\n")
        sys.exit(1)

    total_movies = len(urls_to_scrape)
    print("\n" + "=" * 65)
    print(f"FILM-GRAB BATCH SCRAPER: Starting scrape for {total_movies} movie(s)")
    print(f"Base output folder: {os.path.abspath(config.output_dir)}")
    print(f"Max images/movie:   {config.max_images} (Random sample if total > {config.max_images})")
    print(f"Frame naming:       01.jpg, 02.jpg, ...")
    print("=" * 65)

    results = []
    for index, movie_url in enumerate(urls_to_scrape, start=1):
        print(f"\n>>> [{index}/{total_movies}] Scraping Movie: {movie_url}")
        try:
            res = scrape_single_movie(
                url=movie_url,
                max_images=config.max_images,
                base_output_dir=config.output_dir,
                max_threads=config.threads,
                seed=config.seed,
                clean_existing=config.clean,
                skip_existing=config.skip_existing
            )
            results.append(res)
        except Exception as e:
            print(f"[!] Error processing {movie_url}: {e}")
            results.append({"url": movie_url, "status": "error", "error": str(e), "scraped": 0, "bytes": 0})

    # Summary report
    total_downloaded = sum(r.get("scraped", 0) for r in results)
    total_bytes = sum(r.get("bytes", 0) for r in results)
    successful_movies = sum(1 for r in results if r.get("status") == "success")

    print("\n" + "=" * 65)
    print("BATCH SCRAPING SUMMARY")
    print("=" * 65)
    print(f"  * Movies Processed:   {successful_movies}/{total_movies} successful")
    print(f"  * Total Frames Saved: {total_downloaded}")
    print(f"  * Total Download Size: {total_bytes / (1024 * 1024):.2f} MB")
    print(f"  * Frames Directory:   {os.path.abspath(config.output_dir)}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
