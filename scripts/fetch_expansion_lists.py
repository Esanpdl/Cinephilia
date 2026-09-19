"""Fetch the two explicitly requested public Letterboxd lists; keep raw HTML.

Only list identity, source ordering and supplied years are extracted here.
Movie metadata is supplied separately by TMDB. No credentials are sent to this host.
"""
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/technique_sources"
LISTS = {
    "letterboxd_animation250": ("https://letterboxd.com/official/list/top-250-animated-films/", 250),
    "letterboxd_blackwhite100": ("https://letterboxd.com/sean_chavel/list/best-black-white-cinematography-ever/", 100),
}


def fetch(url):
    cache = OUT / "expansion_html" / (hashlib.sha256(url.encode()).hexdigest() + ".html")
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"}, timeout=40)
    response.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(response.text, encoding="utf-8")
    time.sleep(1)
    return response.text


def main():
    for source, (base, expected) in LISTS.items():
        items, pages, seen = [], [], set()
        url = base
        while url:
            if url in seen or not url.startswith(base):
                raise ValueError("Unexpected pagination URL")
            seen.add(url)
            body = fetch(url)
            blocks = re.findall(r'<li\b[^>]*class="[^"]*(?:posteritem|poster-container)[^"]*"[^>]*>(.*?)</li>', body, re.S)
            if not blocks:
                raise ValueError(f"No film entries on {url}; inspect the saved HTML.")
            for block in blocks:
                name = re.search(r'data-item-name="([^"]+)"', block)
                link = re.search(r'data-item-link="([^"]+)"', block)
                if not name or not link:
                    raise ValueError(f"Missing identity fields on {url}")
                title = html.unescape(name[1]).strip()
                year = re.search(r'\((\d{4})\)$', title)
                rank = re.search(r'<p class="list-number">(\d+)</p>', block)
                position = len(items) + 1
                if rank and int(rank[1]) != position:
                    raise ValueError("Source ranks are not continuous")
                items.append({"rank": position, "title": title, "year": int(year[1]) if year else None, "director": None, "source_page_url": url, "source_item_url": urljoin("https://letterboxd.com", html.unescape(link[1]))})
            pages.append(url)
            following = re.search(r'<a\b[^>]*class="next"[^>]*href="([^"]+)"', body)
            url = urljoin(base, html.unescape(following[1])) if following else None
            if len(pages) > 10:
                raise ValueError("Unexpected list length")
        if len(items) != expected or len({item["source_item_url"] for item in items}) != expected:
            raise ValueError(f"{source}: expected {expected} unique films, found {len(items)}")
        payload = {"schema_version": 1, "source": source, "source_list_url": base, "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "actual_count": len(items), "complete": True, "pages_fetched": len(pages), "items": items}
        destination = OUT / f"{source}.json"
        if not destination.exists():
            destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{source}: {len(items)} unique films from {len(pages)} pages", flush=True)


if __name__ == "__main__":
    main()
