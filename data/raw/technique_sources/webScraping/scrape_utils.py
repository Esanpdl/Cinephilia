"""Shared helpers for the technique-list extractor.

Standard library only. Responsibilities: HTTP fetching with retry/backoff,
on-disk caching, and schema/rank validation shared by both sources.
"""

import hashlib
import json
import logging
import random
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("technique_lists")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 4
BASE_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 30.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def utc_now_iso() -> str:
    """Current time as ISO-8601 UTC with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / _cache_key(url)


def _urllib_get(url: str, headers: dict[str, str]) -> bytes | None:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        return resp.read()


def _curl_get(url: str, headers: dict[str, str]) -> bytes | None:
    """Fetch via the curl binary (more browser-like TLS fingerprint).

    Used as a fallback when the site's bot protection rejects urllib; the
    sites here answered curl normally. Returns None if curl is unavailable
    or the response is not 2xx.
    """
    curl = shutil.which("curl")
    if curl is None:
        return None
    cmd = [
        curl, "-sS", "-L",
        "--max-time", str(REQUEST_TIMEOUT_SECONDS),
        "--fail",
        "-o", "-",
    ]
    for name, value in headers.items():
        cmd += ["-H", f"{name}: {value}"]
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=REQUEST_TIMEOUT_SECONDS + 15)
    except subprocess.SubprocessError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def fetch(url: str, cache_dir: Path, headers: dict[str, str] | None = None,
          force: bool = False) -> bytes:
    """Fetch a URL with retry/backoff/jitter, caching the body on disk.

    Idempotent: re-runs reuse cached bytes unless ``force`` is set. Attempts
    are bounded, delayed with exponential backoff + jitter, honour the
    Retry-After header, and retry only transient conditions (timeouts,
    connection errors, 5xx, 429) or bot-wall 403s via the curl transport
    fallback. Other 4xx (401/404/...) are treated as fatal.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_path_for(cache_dir, url)

    if not force and cache_path.exists():
        log.info("cache hit: %s", url)
        return cache_path.read_bytes()

    request_headers = DEFAULT_HEADERS if headers is None else headers
    data: bytes | None = None
    last_error: str = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        retry_after: str | None = None
        fatal = False

        try:
            data = _urllib_get(url, request_headers)
            break
        except urllib.error.HTTPError as exc:
            status = exc.code
            last_error = f"HTTP {status}"
            if status not in RETRYABLE_STATUS and status != 403:
                fatal = True  # 400/401/404/... -> do not blind-retry.
            retry_after = exc.headers.get("Retry-After")
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
            last_error = str(exc)

        if not fatal and data is None:
            data = _curl_get(url, request_headers)
            if data is not None:
                break
            delay = _backoff_delay(attempt, retry_after)
            log.warning(
                "attempt %d/%d failed for %s (%s); retrying in %.1fs",
                attempt, MAX_ATTEMPTS, url, last_error, delay,
            )
            time.sleep(delay)
        elif fatal:
            raise RuntimeError(f"HTTP {status} for {url}: not retried")
        else:
            break

    if data is None:
        raise RuntimeError(
            f"failed to fetch {url} after {MAX_ATTEMPTS} attempts: {last_error}"
        )

    cache_path.write_bytes(data)
    log.info("fetched (%d bytes) and cached: %s", len(data), url)
    return data


def _backoff_delay(attempt: int, retry_after: str | None) -> float:
    if retry_after is not None:
        try:
            return float(retry_after)
        except (TypeError, ValueError):
            pass
    base = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
    return base + random.uniform(0.0, 1.0)


def decode_html(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def write_json(path: Path, listing: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(listing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("wrote %s", path)


def validate_listing(listing: dict) -> list[str]:
    """Run schema and rank checks; return a list of problems (empty = OK)."""
    problems: list[str] = []

    if listing["schema_version"] != 1:
        problems.append("schema_version != 1")
    if not isinstance(listing["source"], str) or not listing["source"]:
        problems.append("missing source")
    if not listing["source_list_url"].startswith(("http://", "https://")):
        problems.append("bad source_list_url")
    if not isinstance(listing.get("retrieved_at"), str):
        problems.append("missing retrieved_at")

    items = listing["items"]
    if not isinstance(items, list):
        problems.append("items is not a list")
        return problems

    ranks = [it["rank"] for it in items]
    if len(ranks) != len(set(ranks)):
        problems.append("duplicate ranks")

    if ranks:
        if min(ranks) != 1 or max(ranks) != len(ranks):
            problems.append(
                f"ranks do not start at 1 and end at count "
                f"(min={min(ranks)}, max={max(ranks)}, n={len(ranks)})"
            )
        if ranks != sorted(ranks):
            problems.append("ranks out of order")
        if any(b - a != 1 for a, b in zip(ranks, ranks[1:])):
            gaps = [b for a, b in zip(ranks, ranks[1:]) if b - a != 1]
            problems.append(f"rank gaps near {gaps[:5]}")

    for it in items:
        if not isinstance(it.get("title"), str) or not it["title"].strip():
            problems.append(f"rank {it.get('rank')}: empty title")
        y = it.get("year")
        if y is not None and not isinstance(y, int):
            problems.append(f"rank {it.get('rank')}: year is not int/null")
        d = it.get("director")
        if d is not None and not isinstance(d, str):
            problems.append(f"rank {it.get('rank')}: director is not str/null")
        if not isinstance(it.get("source_page_url"), str):
            problems.append(f"rank {it.get('rank')}: missing source_page_url")
        sul = it.get("source_item_url")
        if sul is not None and not isinstance(sul, str):
            problems.append(f"rank {it.get('rank')}: bad source_item_url")

    if listing.get("complete") and len(items) != listing.get("actual_count"):
        problems.append("complete but actual_count mismatch")
    if len(items) != listing.get("actual_count"):
        problems.append(
            f"actual_count ({listing.get('actual_count')}) != len(items) ({len(items)})"
        )

    return problems