"""Package only exact MovieLens inputs and source; never package environment keys."""
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from apps.recommendations.services.collaborative.artifacts import digest, write_json


def main():
    module = Path("backend/apps/recommendations/services/collaborative")
    paths = [
        Path("backend/apps/__init__.py"), Path("backend/apps/recommendations/__init__.py"),
        Path("backend/apps/recommendations/services/__init__.py"),
        *(module / name for name in ("__init__.py", "artifacts.py", "math.py")),
        *(Path("training/collaborative") / name for name in ("build_model.py", "sgd.py", "validation.py", "config.json", "requirements.txt", "README.md")),
        *(Path("data/collaborative/prepared") / name for name in ("ratings.npz", "movies.json", "manifest.json", "excluded_links.json", "README.txt", "checksums.txt")),
        Path("scripts/download_movielens.py"), Path("scripts/prepare_collaborative_data.py"),
        Path("data/collaborative/catalog.json"), Path("data/collaborative/raw/source.json"),
    ]
    output = ROOT / "data/collaborative/cinephilia-collaborative-training.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(ROOT / path, path.as_posix(), compress_type=zipfile.ZIP_STORED if path.suffix == ".npz" else zipfile.ZIP_DEFLATED)
    write_json(output.with_suffix(".manifest.json"), {"bundle_sha256": digest(output), "files": {path.as_posix(): digest(ROOT / path) for path in paths}})
    print(f"Packaged {len(paths)} allowed source/data files: {output} ({output.stat().st_size:,} bytes).")


if __name__ == "__main__":
    main()
