# Film-student collection and trailer analysis

Open **http://127.0.0.1:5173/students** after running `./scripts/start_dev.ps1`.
The collection preserves the exact 500 selected movie identities and their ranks,
including films whose trailer is missing or awaiting source review.

## Verified state on 18 September 2026

The full extraction run has finished: 500 local video analyses. The project owner
supplied *The Lady Vanishes* (TMDB 940) as Criterion's **Three Reasons** promotional
featurette, saved as `data/raw/trailers/940.mp4`. Its source URL is
`https://www.youtube.com/watch?v=pTKfhyj2neg`; Criterion's own article embeds that
exact video. Source review excluded 13 promotional/transition samples, leaving
29 black-and-white frames. Its analysis is now published and explicitly labeled
as a promotional featurette. The original video and pre-review measurements
remain preserved locally.

The local integrity check passed for 18,953
retained frames and verified that the database preserves the original 500 film
identities and ranks.

The imported collection publishes 488 analyses and 961 study cards. Review of
the 32 flagged sources cleared 20 for sampled-footage studies; 12 need a
replacement or stronger source/edition provenance and remain withheld. Published
source color modes are 257 color, 211 black and white, and 20 mixed.
These classifications describe sampled source videos, not independently verified
whole-film editions.

The frontend build, eight frontend unit tests and twelve extraction/backend
checks passed after source review. Temporary backend test writes were rolled
back. OpenAPI schema validation completed without warnings or errors. The
current verification receipts are retained under `data/phase8/`.
All five browser scenarios passed, including the newly published Lady Vanishes
featurette, loaded evidence images, scope labeling and timestamp playback links.

See [the replacement list](source-replacements.md) or
`data/phase8/source-review-needed.md` for the 12 withheld-source cases,
and `data/phase8/inventory-verification.json` for the full integrity
receipt. All 32 flagged cases now have recorded decisions; the 12 unresolved
sources still need replacement footage or verifiable provenance. No replacement
footage was downloaded during this review.

## What the section provides

- A searchable collection with color-format, technique and availability filters.
- Film studies with six-color palettes, brightness, saturation, tonal contrast,
  representative frames and measured study cards linked to trailer timestamps.
- A text-region overlay showing the detected polygons excluded from measurements.
- Two-film comparisons and related palettes based on trailer color histograms.
- An interactive visual explorer, frame-observation quiz and weekly spotlight.
- Signed-in technique contributions for the full catalog, with staff moderation
  before publication. These contributions do not extend the selected 500.

The main recommendation engines remain separate. Age-certification filtering is
deferred at the project owner's request.

## What the measurements mean

The current extractor (`palette-text-2.1`) samples 48 timestamps between 7% and
90% of each local trailer. It crops nearly black outer bars and excludes fades,
flat graphics and near-duplicate samples. A pretrained RapidOCR text detector
identifies text polygons; expanded masks remove those pixels from all color
measurements. Text-heavy cards and samples with nearly uniform remaining
backgrounds are excluded. At least five usable frames must remain.

Brightness is mean grayscale intensity, saturation is mean HSV saturation, and
tonal contrast is the difference between the 90th and 10th grayscale percentiles.
The palette clusters sampled unmasked pixels into six Lab colors. A normalized
192-bin HSV histogram supplies palette similarity. Frames contribute equally to
the histogram; the displayed percentage describes palette overlap.

Color mode describes the retained trailer samples. A black-and-white source-list
citation and measured trailer color are presented separately. Trailer grading,
editions, promotional graphics and OCR errors can affect the result. The overlay
shows detector polygons; the actual exclusion mask also includes a small margin.
Text within the filmed scene is masked conservatively too.

This implementation does not measure cuts, average shot length, pacing or optical
flow. It does not establish narrative similarity, cinematographer intent, lighting
setups, or whole-film technique frequency. Composition and lighting interpretations
require reviewed evidence. No new CV model was trained; extraction runs locally
using OpenCV and an existing text detector.

## Resume and import

Run these commands from the `Cinephilia` directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r training/visual-requirements.txt
.\.venv\Scripts\python.exe -u scripts/analyze_trailers.py --workers 2
.\.venv\Scripts\python.exe scripts/audit_trailer_sources.py
.\.venv\Scripts\python.exe backend/manage.py import_trailer_analysis
.\.venv\Scripts\python.exe scripts/verify_trailer_inventory.py --database
.\.venv\Scripts\python.exe scripts/verify_cinematography.py
```

Extraction resumes using the trailer size, modification time and method version.
Results are written atomically per film. The source audit command above reads
local metadata; it does not fetch or download replacement trailers. Run one full
extraction at a time and import after it finishes.

To re-extract a specific trailer, use
`scripts/analyze_trailers.py --tmdb-id <id> --force`. A targeted run replaces the
last-run receipt; follow it with a full cached run before the inventory check.

The importer refuses mismatched movie identities and withholds outdated analyses,
changed trailer files, unreviewed source flags and rejected sources. Existing
study-card moderation decisions survive reimport. Unavailable films remain in the
collection while their frames, palettes and cards are excluded from public
analysis, comparisons, charts and quizzes.

## Source review and local evidence

Source review is a separate, recorded quality step. Accepted trailers,
single-film promotional videos, featurettes and scene excerpts are labeled by
type. Their measurements describe only the retained source footage. The 2026-09-18
review excluded 162 additional frames containing promotional graphics,
comparison-film inserts or uncertain transitions, then recomputed palettes,
histograms, metrics and study cards with the existing extractor.

Each accepted decision is bound to a source checksum and exclusion recipe.
The normal extraction runner applies it automatically. The importer withholds
changed sources, unapplied decisions and evidence that still contains excluded
frames. Changing a recipe requires `--force` to restore the original samples;
replacing a video requires a fresh decision for its new checksum. An old
approval must never be copied to a replacement without checking its footage.

The automatic extractor has not been replaced or retrained. The full runnable
source and review inputs are preserved in
[`training/visual/`](../training/visual/README.md). To check the preserved code,
run `scripts/preserve_visual_extraction.py --check`.

| Location | Purpose |
| --- | --- |
| `data/phase8/trailer_manifest_500.json` | Original selection and ranks |
| `data/raw/trailers/<tmdb_id>.mp4` | User-supplied trailer files |
| `data/raw/trailers/_download_status.json` | Source URLs and video metadata |
| `data/phase8/source_audit.json` | Local source flags, including multi-film trailers and excerpts |
| `data/phase8/source_decisions.json` | Recorded acceptance or rejection with reasons |
| `training/visual/source-reviews.json` | Preserved review decisions and source checksums for handoff |
| `data/phase8/analysis/before-source-review/` | Original measurements before manual review exclusions |
| `data/phase8/analysis/<tmdb_id>.json` | Measurements, frame references, source digest and masks |
| `data/phase8/frames/<tmdb_id>/<digest>/` | Cached evidence JPEGs |
| `data/phase8/analysis/run.json` | Last extraction outcomes |
| `data/phase8/inventory-verification.json` | Whole-selection integrity, imported counts and unresolved sources |
| `data/phase8/api-verification.json` | Extraction and API test results |
| `data/phase8/browser-results.json` | Browser test results |
| `data/phase8/screenshots/` | Desktop and mobile verification screenshots |

Use `scripts/review_trailer_frames.py --tmdb-id <id>` to make a contact sheet from
the actual cached samples. A plausible title alone does not prove that a video
is a suitable single-film trailer. Multi-film compilation footage must not be
attributed to one film. Missing or unsuitable sources require a suitable supplied
replacement at the same movie path and updated source metadata before reanalysis.

## Verify the product

The backend verification covers source checksum/recipe guards, palette
recomputation after review exclusions, frame accounting, color separation, bar/card rejection, exclusion
of detected colored text, comparison validation, frame access, unavailable
evidence, pending contributions, staff approval, CSRF and quiz/spotlight behavior.
Temporary database test writes are rolled back.

Run the browser checks from `frontend`:

```powershell
npm.cmd run build
npm.cmd test
npm.cmd run test:e2e -- --config playwright.students.config.ts
```

The browser suite checks collection search, Parasite's color analysis, real frame
loading, text overlays, timestamp embed URLs, comparisons, charts, quiz answers,
withheld source evidence, the reviewed Lady Vanishes featurette and its scope,
the anonymous contribution gate and mobile horizontal
overflow after content loads. Third-party video streaming itself depends on the
source provider's availability and embed permissions. The configured
browser is the locally installed Chrome executable.

REST routes live under `/api/v1/cinematography/`: `films/`, `techniques/`, `cards/`,
`compare/`, `overview/`, `spotlight/`, `quiz/`, `tags/`, and `moderation/`.
Per-film detail, similar palettes and approved tags are available under
`films/<tmdb_id>/`. Swagger is at **http://127.0.0.1:8000/api/docs/**.

The final live counts and unresolved-source list are in the inventory receipt.
Large trailers, frames, analysis artifacts and local receipts are ignored by Git;
back them up separately when moving the project. No subsequent project phase is
started by these resume commands.
