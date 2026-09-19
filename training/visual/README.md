# Preserved color palette extraction

This directory preserves the actual Python algorithm used for the film-student
collection, its runnable batch entry point, dependencies and source checksums.
It is local OpenCV processing with a pretrained RapidOCR text detector. No new
visual model was trained, and this extraction has not run on Lightning AI.
The directory name does not imply otherwise.

## Files

- `extractor.py`: full frame filtering, text masking, palette clustering,
  brightness/saturation/contrast and histogram implementation.
- `analyze_trailers.py`: runnable batch entry point importing this preserved
  extractor directly.
- `requirements.txt`: pinned offline extraction dependencies.
- `source_review.py`: applies the separate, recorded source-specific exclusions.
- `source-reviews.json`: preserved decisions bound to the reviewed video hashes.
- `source-manifest.json`: original locations and SHA-256 checksums.

The application implementation remains in
`backend/apps/cinematography/services/visual_analysis.py`. This is an explicit
reproduction snapshot. After changing the application extractor or runner, run
`scripts/preserve_visual_extraction.py` and verify it with `--check` so this copy
does not silently diverge. The preservation script never copies credentials.

## Run from the project root

```powershell
.\.venv\Scripts\python.exe -m pip install -r training/visual/requirements.txt
.\.venv\Scripts\python.exe scripts/preserve_visual_extraction.py --check
.\.venv\Scripts\python.exe training/visual/analyze_trailers.py --help
.\.venv\Scripts\python.exe -u training/visual/analyze_trailers.py --workers 2
```

The last command processes local videos in `data/raw/trailers/` against the
existing 500-film manifest, writing cached frames and analysis under
`data/phase8/`. It does not download videos or publish database records. It
resumes compatible cached analyses; `--tmdb-id 940 --force` re-extracts that
one source. Do not run it concurrently with the application extraction runner:
both use the same output files. A targeted run replaces the last-run receipt;
follow it with a full cached run before the whole-collection inventory check.
The runner reads decisions from `data/phase8/source_decisions.json`. The copy here
preserves the review inputs for handoff; restore it to that data path when
reproducing the reviewed collection on another computer. Decisions are valid
only for their recorded video checksums. Original measurements before applying
review exclusions are retained in `data/phase8/analysis/before-source-review/`.

## Current method and limits

1. Sample 48 timestamps between 7% and 90% of the source duration.
2. Crop nearly black borders and reject detected fades, flat graphics and
   near-duplicate frames.
3. Detect and mask text pixels; reject text-heavy or uniform-background cards.
4. Cluster retained pixels into six Lab palette colors and calculate measured
   image statistics and a normalized HSV histogram.
5. Preserve frame timestamps, source checksum, exclusions and evidence images.

These are automatic rules, not human scene understanding. The current method
does not detect scene boundaries or reliably identify large promotional numbers,
logos, footage from another film, or an altered edition. Contact-sheet inspection
is a separate quality check, not the extraction algorithm or a trained model.
Measurements describe the sampled source footage, not the entire film.

See [the film-student guide](../../docs/film-student-guide.md) for import,
verification, source review and the current collection status.
