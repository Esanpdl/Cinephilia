"""Download the exact TMDB-linked trailers in Cinephilia's 500-film manifest.

Run without arguments to download/resume the full list. --dry-run is offline.
No TMDB/Lightning keys, database access, title searches or replacement videos.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MANIFEST = ROOT / "data/phase8/trailer_manifest_500.json"
DESTINATION = ROOT / "data/raw/trailers"


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_movies(path):
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload["movies"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Manifest contains no movies.")
    seen = set()
    for row in rows:
        mid = row["tmdb_id"]
        if type(mid) is not int or mid <= 0 or mid in seen:
            raise ValueError("Manifest has an invalid or duplicate TMDB ID.")
        seen.add(mid)
        if row["required_filename"] != f"{mid}.mp4":
            raise ValueError(f"Unexpected filename for TMDB {mid}.")
        url = row.get("trailer_url", "")
        if url:
            parsed = urlparse(url)
            key = parse_qs(parsed.query).get("v", [""])[0]
            if parsed.scheme != "https" or parsed.netloc not in {"www.youtube.com", "youtube.com"} or parsed.path != "/watch" or not re.fullmatch(r"[A-Za-z0-9_-]{11}", key):
                raise ValueError(f"Unexpected trailer URL for TMDB {mid}.")
    return rows


def ffmpeg_path():
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    # yt-dlp recognizes the bundled imageio binary by its ffmpeg-prefixed name.
    return imageio_ffmpeg.get_ffmpeg_exe()


def verify_video(path, ffmpeg):
    if not path.is_file() or path.stat().st_size < 1024:
        raise ValueError("No complete video file was produced.")
    with path.open("rb") as handle:
        if b"ftyp" not in handle.read(64):
            raise ValueError("Output is not an MP4 container.")
    # Decode a real video frame; audio-only files and unreadable containers fail.
    check = subprocess.run([ffmpeg, "-hide_banner", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True, timeout=60)
    if check.returncode or not check.stdout.startswith(b"\xff\xd8"):
        raise ValueError("FFmpeg could not decode a video frame: " + check.stderr.decode("utf-8", "replace")[-400:])


def safe_message(message):
    # Do not persist signed media URLs or authentication query strings in logs.
    return re.sub(r"https?://[^\s]+", "[remote URL]", str(message))


class Logger:
    def __init__(self):
        self.messages = []

    def debug(self, message):
        if not message.startswith("[debug]"):
            self.messages.append(safe_message(message))

    def warning(self, message):
        message = safe_message(message)
        self.messages.append("WARNING: " + message)
        print("  Warning: " + message, flush=True)

    def error(self, message):
        self.messages.append("ERROR: " + safe_message(message))


def trailer_only(info, *, incomplete=False):
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        return "Live streams are not trailers."
    duration = info.get("duration")
    if duration is not None and not 5 <= duration <= 1200:
        return "Video is outside the 5-second to 20-minute trailer limit; review manually."
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dry-run", action="store_true", help="Validate and list files without network access.")
    parser.add_argument("--limit", type=int, help="Process only the first N selected entries.")
    parser.add_argument("--tmdb-id", type=int, action="append", help="Process one ID; repeat for more.")
    parser.add_argument("--max-height", type=int, choices=[480, 720, 1080], default=720)
    parser.add_argument("--cookies", type=Path, help="Optional local Netscape-format cookie file; never loaded automatically.")
    args = parser.parse_args()
    rows = load_movies(args.manifest)
    if args.tmdb_id:
        wanted = set(args.tmdb_id)
        if wanted - {row["tmdb_id"] for row in rows}:
            parser.error("A requested TMDB ID is not in the selected manifest.")
        rows = [row for row in rows if row["tmdb_id"] in wanted]
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be positive.")
        rows = rows[:args.limit]
    print(f"Selected {len(rows)} trailers. Destination: {DESTINATION}", flush=True)
    if args.dry_run:
        for row in rows:
            print(f"{row['tmdb_id']}.mp4 | {row['title']} ({row['year']}) | {row['trailer_url'] or 'No link'}")
        return 0
    try:
        import yt_dlp
        ffmpeg = ffmpeg_path()
    except ImportError:
        parser.error("Install trailer_requirements.txt with this Python interpreter first.")
    runtime = "deno" if shutil.which("deno") else "node" if shutil.which("node") else None
    if not runtime:
        parser.error("Install Node.js 22+ or Deno 2.3+ for YouTube extraction.")
    if args.cookies and not args.cookies.is_file():
        parser.error("The supplied cookie file does not exist.")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    staging = DESTINATION / "_partial"
    logs = DESTINATION / "_download_logs"
    staging.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    # OS-released lock prevents two copies from writing the same files/status.
    lock = (DESTINATION / "_download.lock").open("a+b")
    lock.seek(0)
    lock.write(b"0")
    lock.flush()
    lock.seek(0)
    if sys.platform == "win32":
        import msvcrt
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            parser.error("Another trailer downloader is already running.")
    else:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    status_path = DESTINATION / "_download_status.json"
    state = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {"movies": {}}
    state.update(manifest=str(args.manifest.resolve()), manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest())
    counts = Counter()
    started = time.monotonic()
    for index, row in enumerate(rows, 1):
        mid = row["tmdb_id"]
        final = DESTINATION / f"{mid}.mp4"
        logger = Logger()
        record = {"tmdb_id": mid, "title": row["title"], "source_url": row["trailer_url"], "checked_at": now()}
        print(f"[{index}/{len(rows)}] {row['title']} ({row['year']}) -> {final.name}", flush=True)
        try:
            if final.exists():
                verify_video(final, ffmpeg)
                record.update(status="existing", bytes=final.stat().st_size)
            elif not row["trailer_url"]:
                record.update(status="missing_link")
            else:
                height = args.max_height
                options = {
                    "format": f"bestvideo[ext=mp4][height<={height}]+bestaudio[ext=m4a]/best[ext=mp4][height<={height}]/bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                    "format_sort": ["vcodec:h264"], "merge_output_format": "mp4",
                    "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
                    "outtmpl": str(staging / f"{mid}.%(ext)s"),
                    "ffmpeg_location": ffmpeg, "js_runtimes": {runtime: {}},
                    "noplaylist": True, "continuedl": True, "overwrites": False,
                    "retries": 3, "fragment_retries": 3, "socket_timeout": 30,
                    "concurrent_fragment_downloads": 1, "sleep_interval_requests": 1,
                    "sleep_interval": 3, "max_sleep_interval": 6,
                    "match_filter": trailer_only, "logger": logger, "quiet": True,
                }
                if args.cookies:
                    options["cookiefile"] = str(args.cookies.resolve())
                with yt_dlp.YoutubeDL(options) as downloader:
                    info = downloader.extract_info(row["trailer_url"], download=True)
                if not info or info.get("_type", "video") != "video" or info.get("id") != parse_qs(urlparse(row["trailer_url"]).query)["v"][0]:
                    raise ValueError("No single matching video was downloaded.")
                partial = staging / final.name
                verify_video(partial, ffmpeg)
                partial.replace(final)
                record.update(status="downloaded", bytes=final.stat().st_size, video_id=info.get("id"), video_title=info.get("title"), duration_seconds=info.get("duration"), width=info.get("width"), height=info.get("height"))
        except KeyboardInterrupt:
            record.update(status="interrupted")
            state["movies"][str(mid)] = record
            state["updated_at"] = now()
            atomic_json(status_path, state)
            print("Stopped. Rerun the same command to resume; partial files are preserved.")
            return 130
        except Exception as error:
            record.update(status="failed", error=safe_message(error))
            print("  Failed: " + record["error"], flush=True)
        finally:
            if logger.messages:
                (logs / f"{mid}.log").write_text("\n".join(logger.messages) + "\n", encoding="utf-8")
        counts[record["status"]] += 1
        print("  " + record["status"], flush=True)
        # Keep known metadata when rechecking a previously completed file.
        previous = state["movies"].get(str(mid), {})
        state["movies"][str(mid)] = {**previous, **record}
        state["updated_at"] = now()
        atomic_json(status_path, state)
    print(f"Finished in {time.monotonic() - started:.1f}s: {dict(counts)}")
    print(f"Results: {status_path}")
    return 1 if counts["failed"] or counts["missing_link"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
