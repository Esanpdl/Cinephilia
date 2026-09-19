"""Portable JSON/NPZ artifact format, with checksums and no pickle loading."""
import hashlib
import json
from pathlib import Path
import uuid

FORMAT_VERSION = 1
ENGINE_VERSION = "weighted-tfidf-v1"
DATA_FILES = ("features.npz", "neighbors.npz", "movies.json", "feature_schema.json")


def canonical_json(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_file(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(canonical_json(payload), encoding="utf-8")
    temporary.replace(path)


def read_manifest(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format_version") != FORMAT_VERSION or manifest.get("engine") != ENGINE_VERSION:
        raise ValueError("Unsupported content index format or engine version.")
    if set(manifest.get("files", {})) != set(DATA_FILES):
        raise ValueError("Content index file manifest is incomplete.")
    for name in DATA_FILES:
        if sha256_file(directory / name) != manifest["files"][name]:
            raise ValueError(f"Content index checksum mismatch: {name}.")
    return manifest
