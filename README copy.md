# Echo360 Multi-Stream Downloader

This project downloads three Echo360 HLS streams (`s0q1`, `s1q1`, `s2q1`) and saves them as three separate MP4 files.

## Output Files

The downloader maps stream keys to file names as follows:

- `s0q1` -> `voiceOver.mp4`
- `s1q1` -> `video_lecture_slides.mp4`
- `s2q1` -> `video_lecture.mp4`

These files are written to the same directory as the script.

## Why This Script Exists

Echo360 links are signed URLs. The top-level playlist URL includes auth query parameters (`Policy`, `Signature`, etc.), but segment lines inside the playlist are often relative paths and do not include those parameters.

The script solves this by:

1. Downloading each `.m3u8` playlist.
2. Rewriting media segment URLs and `#EXT-X-MAP` URIs so each segment carries the auth query string.
3. Running `ffmpeg` to mux each stream directly into MP4 (`-c copy`, no re-encode).
4. Running all three streams in parallel, with sequential retry for failures.

## Repository Structure

- `download_lecture.py`: main downloader implementation.
- `requirements.txt`: Python dependencies.
- `fixed_s0q1.m3u8`, `fixed_s1q1.m3u8`, `fixed_s2q1.m3u8`: generated rewritten playlists.
- Output files: `voiceOver.mp4`, `video_lecture_slides.mp4`, `video_lecture.mp4`.

## Requirements

### System Requirements

- macOS/Linux/Windows with Python 3.9+
- `ffmpeg` available in `PATH`

Check ffmpeg:

```bash
ffmpeg -version
```

### Python Dependencies

Install:

```bash
python3 -m pip install -r requirements.txt
```

Dependencies:

- `requests`: HTTP playlist fetch
- `tqdm`: concurrent progress bars (optional but recommended)

If `tqdm` is missing, downloads still run, but without progress bars.

## Input Format (Terminal Prompts)

At runtime, the script asks for three URLs in this exact order:

- `s0q1` (saved as `voiceOver.mp4`)
- `s1q1` (saved as `video_lecture_slides.mp4`)
- `s2q1` (saved as `video_lecture.mp4`)

Each URL must:

- start with `http://` or `https://`
- include `.m3u8`
- contain the expected stream name (`s0q1.m3u8`, `s1q1.m3u8`, `s2q1.m3u8`)
- include signed query parameters after `?`

Example pattern:

- `https://content.echo360.org/.../s0q1.m3u8?x-uid=...&Policy=...&Signature=...`

## How It Works (Detailed)

### 1) URL Extraction

Function: `prompt_stream_urls(...)` and `prompt_stream_url(...)`

- Prompts the user in terminal for each stream URL.
- Shows expected stream key, target output filename, and expected URL shape.
- Validates input format and repeats prompt until valid.

### 2) Playlist Rewrite

Function: `build_fixed_playlist(...)`

For each playlist:

- Splits URL into:
  - base path (`.../1/`)
  - query string (`x-uid=...&Policy=...&Signature=...`)
- Downloads original playlist text.
- Rewrites:
  - `#EXT-X-MAP:URI="..."` entries to full absolute signed URLs.
  - Relative media segment lines (`.mp4`, `.m4s`, `.ts`) to full signed URLs.
  - Absolute segment URLs also receive query params if missing.
- Saves rewritten playlist to `fixed_<stream>.m3u8`.

### 3) Duration Estimation

Function: `get_playlist_duration_seconds(...)`

- Sums all `#EXTINF:<seconds>` values in rewritten playlist.
- Returns estimated stream duration.
- Used only for progress visualization.

### 4) ffmpeg Execution + Live Progress

Function: `run_ffmpeg(...)`

- Runs ffmpeg with:
  - `-progress pipe:1` for machine-readable progress lines
  - `-nostats` to reduce noisy output
  - `-c copy` for direct remux without quality loss
- Parses `out_time_ms=<value>` lines.
- Converts to seconds and updates per-stream `tqdm` progress bar.
- Captures full logs for error reporting.

### 5) Parallel Download

Function: `run_parallel(...)`

- Starts one worker thread per stream.
- Each thread runs full flow for one stream:
  - rewrite playlist
  - estimate duration
  - ffmpeg download
- Displays simultaneous bars (one console row per stream).

### 6) Sequential Fallback

Function: `run_sequential(...)`

- If parallel mode has failures, retries only failed streams in deterministic order (`s0q1`, `s1q1`, `s2q1`).

### 7) Exit Behavior

Function: `main()`

- Exit `0`: all streams downloaded successfully.
- Exit `1`: one or more streams still failed after retry.
- Exit `130`: user interrupted (`Ctrl+C`).

## Running the Script

From project root:

```bash
python3 download_lecture.py
```

Successful run prints per-stream `[OK]` messages and creates all three MP4s.

## Logging and Troubleshooting

### Common Failure: Expired Signed URL

Symptoms:

- HTTP 403/401 while fetching playlist or segments
- ffmpeg exits non-zero quickly

Fix:

- Refresh links in `instructions.md` and rerun.

### Common Failure: ffmpeg Not Found

Symptoms:

- shell error or subprocess failure before processing

Fix:

- Install ffmpeg and ensure it is in `PATH`.

### Common Failure: Missing Label in `instructions.md`

Symptoms:

- startup error: `Missing URLs in instructions.md for: ...`

Fix:

- Ensure all three labels exist and are formatted exactly.

### Progress Bars Not Showing

Symptoms:

- script prints `tqdm is not installed; running without progress bars.`

Fix:

```bash
python3 -m pip install tqdm
```

## Development Notes

### Code Entry Points

- Main entrypoint: `main()` in `download_lecture.py`.
- One-stream unit of work: `download_one(...)`.

### Safe Refactor Areas

- Stream-to-filename mapping: `STREAM_TARGETS`
- Expected processing order: `STREAM_ORDER`
- URL parsing regex in `read_stream_urls(...)`

### Adding More Streams

To add another stream key:

1. Add key/name pair to `STREAM_TARGETS`.
2. Add key to `STREAM_ORDER`.
3. Add corresponding label+URL in `instructions.md`.

No other logic changes should be required.

## Security Notes

- Signed Echo360 URLs include sensitive tokens in query params.
- Do not commit fresh tokens to public repositories.
- Prefer short-lived local files for active sessions.

## Performance Notes

- Parallel mode improves total wall-clock time when network bandwidth allows.
- Sequential fallback reduces transient parallel-network failures.
- `-c copy` is fast because no video/audio re-encoding is performed.

## Maintainer Checklist

When debugging user reports:

1. Verify user is pasting fresh signed URLs for all 3 prompted streams.
2. Verify `ffmpeg -version` works in user shell.
3. Run `python3 -m py_compile download_lecture.py` for syntax sanity.
4. Run `python3 download_lecture.py` and inspect per-stream status.
5. If one stream fails repeatedly, inspect generated `fixed_<stream>.m3u8`.
