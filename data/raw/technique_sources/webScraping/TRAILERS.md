# Download the 500 selected trailers

The downloader reads `data/phase8/trailer_manifest_500.json`. It uses the exact
TMDB-supplied YouTube links, never title searches or automatic replacements.
No API keys or Lightning account are needed.

## Run on this computer

Dependencies are already installed in Cinephilia's `.venv`. Open PowerShell:

```powershell
Set-Location 'C:\Users\ishan\Documents\CollegeProject\Cinephilia'
.\.venv\Scripts\python.exe data/raw/technique_sources/webScraping/download_trailers.py
```

This runs the full list. Files go to `data/raw/trailers/<tmdb_id>.mp4`.
The default maximum resolution is 720p; lower source resolutions are preserved
without upscaling. Use `--max-height 1080` if desired. Aspect ratios are preserved.

You can stop with Ctrl+C and rerun the same command. Readable completed MP4s are
skipped; interrupted download files remain under `_partial` for resumption.
Only one copy of the downloader can write to the destination at a time.

## Small batches and checks

```powershell
# Offline manifest validation; downloads nothing
.\.venv\Scripts\python.exe data/raw/technique_sources/webScraping/download_trailers.py --dry-run

# Process only the first 10 manifest entries, including already-completed entries
.\.venv\Scripts\python.exe data/raw/technique_sources/webScraping/download_trailers.py --limit 10

# One specific selected film
.\.venv\Scripts\python.exe data/raw/technique_sources/webScraping/download_trailers.py --tmdb-id 238
```

Progress and video identity/dimensions are saved after each film in
`data/raw/trailers/_download_status.json`. Per-film diagnostics are in
`data/raw/trailers/_download_logs/`. A failed entry does not discard other downloads.
Nonzero exit status means some attempted entries failed or lacked links.
An existing invalid MP4 is reported for manual review; it is never silently replaced.

## Install on another computer / update after a YouTube change

Use Python 3.11+ and Node.js 22+ (or Deno 2.3+):

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade -r data/raw/technique_sources/webScraping/trailer_requirements.txt
```

The imageio-ffmpeg dependency supplies FFmpeg if it is absent from PATH. The script
uses yt-dlp's bundled EJS support and the installed JavaScript runtime. It does not
read browser cookies automatically. An optional `--cookies <file>` accepts a local
Netscape-format cookie file if you choose to supply one; keep it out of Git and do
not share it. Private, removed, restricted or challenged videos can still fail.
Leave unavailable entries for review instead of substituting an unrelated upload.

## Actual verification, 17 September 2026

- All 500 manifest entries passed identity/filename/URL validation.
- Citizen Kane (TMDB 15) downloaded from its exact manifest link as `15.mp4`.
- Size: 14,166,261 bytes; duration: 226 seconds; source resolution: 640 x 480.
- Download plus validation took 20.8 seconds. This is one sample, not a forecast
  for all 500 videos.
- FFmpeg decoded a video frame from the completed MP4 successfully.
- Rerunning the same one-film command skipped the existing video in 0.2 seconds.

The script verifies the MP4 container and decodes a frame before accepting a new
file. This is a basic readability check, not a full-file corruption scan or a claim
that the trailer represents the editing of the entire film. No cinematography
analysis runs here, and no Lightning credits are used.

References: [yt-dlp](https://github.com/yt-dlp/yt-dlp),
[JavaScript runtime setup](https://github.com/yt-dlp/yt-dlp/wiki/EJS).
