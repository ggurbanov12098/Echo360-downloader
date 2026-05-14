# Echo360 Downloader

An automated tool to extract, download, and merge Echo360 lecture streams. Echo360 splits its media into separate audio and video `.m3u8` streams. This script uses a headless Playwright browser to automatically sniff the stream URLs, downloads them chunks in parallel, and merges them using `ffmpeg`.

## Features
- **Zero-Manual-Effort Automation:** Just paste the public Echo360 URL. No more opening Chrome DevTools to hunt for `.m3u8` links.
- **Bulk & Parallel Downloads:** Paste a list of lectures, and the script handles up to 4 concurrent downloads at once.
- **Isolated Folders:** Downloads and merges are neatly placed into their own isolated directories inside `downloads/` with readable names.
- **Automatic Merging:** Seamlessly stitches the high-quality lecture slide video and the instructor voiceover audio into one final `.mp4` file.

---

## Prerequisites

1. **Python 3.8+**
2. **FFmpeg**: You must have `ffmpeg` and `ffprobe` installed and available in your system's PATH.
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg`
   - **Windows**: Download from [FFmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/Echo360-downloader.git
   cd Echo360-downloader
   ```

2. **Set up a Virtual Environment:**
   *(Recommended to avoid PEP 668 system-package conflicts)*
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright Browsers:**
   This allows the script to open a headless browser to sniff the media requests:
   ```bash
   playwright install chromium
   ```

---

## Usage

Simply activate your virtual environment (if not already active) and run the main interactive script:

```bash
python main.py
```

You will see an interactive menu:

```text
--- Echo360 Downloader ---
1. Download Single Lecture
2. Download Bulk Lectures (Parallel)
--------------------------
Select an option (1/2): 
```

### Option 1: Single Download
Provide a single Echo360 public link and (optionally) a title. The script will automatically scrape the stream links, download the temporary chunks, merge them via FFmpeg, and export the finished `.mp4` to the `downloads/<Your Title>/` folder.

### Option 2: Bulk Download (Parallel)
You can copy-paste a continuous block of text mapping Titles to URLs, for example:

```text
Lecture 19 Sequence Models: https://echo360.org/media/xxxxx/public
Lecture 20 Backpropagation: https://echo360.org/media/yyyyy/public
Lecture 21 Transformers: https://echo360.org/media/zzzzz/public
```

Press **Enter twice** to kick off the process. The script will initialize parallel browser instances out-of-sight and rapidly process all of your lectures concurrently, keeping the workspace extremely clean.

---

## Output Structure

The root directory remains pristine. Files are exported exactly as:
```text
Echo360-downloader/
└── downloads/
    ├── Lecture 19 Sequence Models/
    │   ├── urls.txt
    │   ├── download.log
    │   ├── merge.log
    │   ├── video_lecture_slides.mp4
    │   ├── voiceOver.mp4
    │   └── video_lecture_with_voiceover.mp4   <-- (Final Merged Output!)
    └── Lecture 20 Backpropagation/
        └── ...
```

## Troubleshooting

- **No Active Play Button / Stream Blocked**: If Echo360 alters their player GUI or prompts an authentication screen, the headless browser might miss the m3u8 requests. Run the video link manually in your standard browser to ensure it is fully "public".
- **External Environment Error (`externally-managed-environment`)**: This happens on latest macOS/Linux builds when trying to install `pip` packages globally. Always create and use the `venv` as described in step 2.
- **FFmpeg Error**: Ensure `ffmpeg` and `ffprobe` commands work globally in your terminal.
