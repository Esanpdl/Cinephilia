"""Download the authentic GroupLens release and verify its published file checksums."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import zipfile

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from apps.recommendations.services.collaborative.artifacts import digest, write_json

URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"
PUBLISHED_MD5 = {
    "links.csv": "8f033867bcb4e6be8792b21468b4fa6e",
    "movies.csv": "0df90835c19151f9d819d0822e190797",
    "ratings.csv": "cf12b74f9ad4b94a011f079e26d4270a",
    "tags.csv": "963bf4fa4de6b8901868fddd3eb54567",
}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data/collaborative/raw/ml-32m.zip")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists():
        temporary = args.output.with_suffix(".zip.part")
        with requests.get(URL, stream=True, timeout=(15, 60)) as response:
            response.raise_for_status()
            received, reported = 0, 0
            with temporary.open("wb") as destination:
                for chunk in response.iter_content(1024 * 1024):
                    destination.write(chunk)
                    received += len(chunk)
                    if received - reported >= 25 * 1024 * 1024:
                        print(f"Downloaded {received / 2**20:.0f} MiB of MovieLens 32M.", flush=True)
                        reported = received
            expected = response.headers.get("Content-Length")
            if expected and received != int(expected):
                raise ValueError("MovieLens download is incomplete.")
        temporary.replace(args.output)
    checksums = {}
    with zipfile.ZipFile(args.output) as archive:
        for name, expected in PUBLISHED_MD5.items():
            checksum = hashlib.md5()
            with archive.open("ml-32m/" + name) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    checksum.update(block)
            checksums[name] = checksum.hexdigest()
            if checksums[name] != expected:
                raise ValueError(f"Published GroupLens checksum mismatch: {name}.")
            print(f"Verified official checksum: {name}.", flush=True)
        # Preserve the actual license/citation with every local training handoff.
        for name in ("README.txt", "checksums.txt"):
            (args.output.parent / name).write_bytes(archive.read("ml-32m/" + name))
    write_json(args.output.parent / "source.json", {
        "dataset": "MovieLens 32M", "url": URL,
        "readme_url": "https://files.grouplens.org/datasets/movielens/ml-32m-README.html",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": digest(args.output), "published_md5": checksums,
    })
    print(f"Authentic dataset ready: {args.output}", flush=True)


if __name__ == "__main__":
    main()
