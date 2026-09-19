"""Create an explicit allowlist bundle, excluding every .env and user table."""
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from apps.recommendations.services.content.artifacts import sha256_file, write_json


def main():
    module = Path("backend/apps/recommendations/services/content")
    paths = [
        Path("backend/apps/__init__.py"),
        Path("backend/apps/recommendations/__init__.py"),
        Path("backend/apps/recommendations/services/__init__.py"),
        *(module / name for name in ("__init__.py", "artifacts.py", "features.py", "metadata.py", "ranking.py")),
        *(Path("training/content") / name for name in ("build_index.py", "config.json", "requirements.txt", "README.md")),
        Path("data/content/catalog.json"),
    ]
    output = ROOT / "data/content/cinephilia-content-training.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in paths:
            bundle.write(ROOT / path, path.as_posix())
    write_json(output.with_suffix(".manifest.json"), {
        "bundle_sha256": sha256_file(output),
        "files": {path.as_posix(): sha256_file(ROOT / path) for path in paths},
    })
    print(f"Packaged {len(paths)} allowed files: {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
