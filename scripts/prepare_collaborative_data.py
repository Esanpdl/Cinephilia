"""Map authentic MovieLens ratings to catalog TMDB IDs without fitting a model."""
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from apps.recommendations.services.collaborative.artifacts import canonical_json, digest, write_json

RAW_DTYPE = np.dtype([("user", "<i4"), ("movie", "<i4"), ("rating", "<f4"), ("timestamp", "<i8")])


def match_links(links, catalog):
    catalog_by_id = {movie["tmdb_id"]: movie for movie in catalog}
    groups, excluded = defaultdict(list), []
    seen_ids = set()
    for link in links:
        ml_id = int(link["movieId"])
        if ml_id <= 0 or ml_id in seen_ids:
            raise ValueError("MovieLens movie IDs must be unique positive integers.")
        seen_ids.add(ml_id)
        reason = None
        try:
            tmdb_id = int(link["tmdbId"])
        except (ValueError, TypeError):
            reason, tmdb_id = "missing_or_invalid_tmdb_id", None
        if not reason and tmdb_id not in catalog_by_id:
            reason = "outside_catalog"
        if not reason:
            movie = catalog_by_id[tmdb_id]
            imdb_id = f"tt{int(link['imdbId']):07d}" if link["imdbId"] else ""
            if movie["imdb_id"] and imdb_id and movie["imdb_id"] != imdb_id:
                reason = "imdb_identity_conflict"
            else:
                groups[tmdb_id].append({**movie, "movielens_id": ml_id})
        if reason:
            excluded.append({"movielens_id": ml_id, "tmdb_id": tmdb_id, "reason": reason})
    matched = []
    for tmdb_id, entries in sorted(groups.items()):
        if len(entries) != 1:
            excluded.extend({"movielens_id": entry["movielens_id"], "tmdb_id": tmdb_id, "reason": "ambiguous_duplicate_tmdb_link"} for entry in entries)
        else:
            matched.append(entries[0])
    return matched, excluded, max(seen_ids)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = ROOT / "data/collaborative"
    source = json.loads((data / "raw/source.json").read_text(encoding="utf-8"))
    archive_path = data / "raw/ml-32m.zip"
    if digest(archive_path) != source["archive_sha256"]:
        raise ValueError("MovieLens archive differs from its verified download.")
    catalog = json.loads((data / "catalog.json").read_text(encoding="utf-8"))
    if hashlib.sha256(canonical_json(catalog["movies"]).encode("utf-8")).hexdigest() != catalog["catalog_sha256"]:
        raise ValueError("Catalog checksum mismatch.")
    retained, total, last_pair = [], 0, -1
    with zipfile.ZipFile(archive_path) as archive:
        links = list(csv.DictReader(io.TextIOWrapper(archive.open("ml-32m/links.csv"), encoding="utf-8")))
        movies, excluded, maximum_movie = match_links(links, catalog["movies"])
        if not movies:
            raise ValueError("No unambiguous MovieLens/TMDB links matched the catalog.")
        lookup = np.full(maximum_movie + 1, -1, dtype=np.int32)
        for row, movie in enumerate(movies):
            lookup[movie["movielens_id"]] = row
        with archive.open("ml-32m/ratings.csv") as ratings:
            if ratings.readline().strip() != b"userId,movieId,rating,timestamp":
                raise ValueError("Unexpected MovieLens ratings columns.")
            while lines := ratings.readlines(32 * 1024 * 1024):
                chunk = np.loadtxt(lines, delimiter=",", dtype=RAW_DTYPE, ndmin=1)
                if np.any(chunk["user"] <= 0) or np.any(chunk["movie"] <= 0) or np.any(chunk["movie"] > maximum_movie) or np.any(chunk["timestamp"] <= 0):
                    raise ValueError("Invalid MovieLens identities/timestamps.")
                values = chunk["rating"]
                if not np.all(np.isfinite(values)) or np.any((values < .5) | (values > 5)) or np.any(values * 2 != np.floor(values * 2)):
                    raise ValueError("Invalid MovieLens rating scale.")
                pairs = chunk["user"].astype(np.int64) * (maximum_movie + 1) + chunk["movie"]
                if pairs[0] <= last_pair or np.any(np.diff(pairs) <= 0):
                    raise ValueError("MovieLens user/movie pairs are duplicated or out of source order.")
                last_pair = int(pairs[-1])
                selected = lookup[chunk["movie"]] >= 0
                filtered = chunk[selected].copy()
                filtered["movie"] = lookup[filtered["movie"]]
                retained.append(filtered)
                total += len(chunk)
                print(f"Read {total:,} authentic ratings; matched {sum(len(part) for part in retained):,}.", flush=True)
    if total != 32000204:
        raise ValueError("Unexpected number of ratings in the stable MovieLens 32M release.")
    rows = np.concatenate(retained)
    del retained
    # Dense training user indices are explicitly unrelated to Django user IDs.
    user_ids, users = np.unique(rows["user"], return_inverse=True)
    output = data / "prepared"
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output / "ratings.npz", users=users.astype(np.int32), items=rows["movie"], ratings=rows["rating"], timestamps=rows["timestamp"], movielens_user_ids=user_ids)
    write_json(output / "movies.json", movies)
    write_json(output / "excluded_links.json", excluded)
    for name in ("README.txt", "checksums.txt"):
        (output / name).write_bytes((data / "raw" / name).read_bytes())
    write_json(output / "manifest.json", {
        "schema_version": 1, "prepared_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "MovieLens 32M", "source_url": source["url"], "source_archive_sha256": source["archive_sha256"],
        "catalog_sha256": catalog["catalog_sha256"], "catalog_movie_count": len(catalog["movies"]),
        "raw_rating_count": total, "matched_rating_count": len(rows), "matched_movie_count": len(movies), "user_count": len(user_ids),
        "excluded_link_counts": {reason: sum(entry["reason"] == reason for entry in excluded) for reason in sorted({entry["reason"] for entry in excluded})},
        "files": {name: digest(output / name) for name in ("ratings.npz", "movies.json", "excluded_links.json", "README.txt", "checksums.txt")},
    })
    print(f"Prepared {len(rows):,} ratings, {len(user_ids):,} MovieLens users, {len(movies):,} exact movie links.", flush=True)


if __name__ == "__main__":
    main()
