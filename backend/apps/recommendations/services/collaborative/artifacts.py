"""Versioned, checksum-verified JSON/NPZ artifacts; no pickle deserialization."""
import hashlib
import json
from pathlib import Path
import uuid

ENGINE = "biased-svd-v1"
DATA_FILES = ("model.npz", "movies.json", "evaluation.json")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(path, algorithm="sha256"):
    checksum = hashlib.new(algorithm)
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(canonical_json(value), encoding="utf-8")
    temporary.replace(path)


def read_manifest(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format_version") != 1 or manifest.get("engine") != ENGINE:
        raise ValueError("Unsupported collaborative artifact format.")
    if set(manifest.get("files", {})) != set(DATA_FILES):
        raise ValueError("Incomplete collaborative artifact manifest.")
    for name in DATA_FILES:
        if digest(directory / name) != manifest["files"][name]:
            raise ValueError(f"Collaborative artifact checksum mismatch: {name}.")
    return manifest
