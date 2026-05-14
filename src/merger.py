import shutil
import subprocess
import sys
from pathlib import Path


def ensure_tool(name: str) -> None:
    if shutil.which(name) is None:
        print(f"Error: '{name}' is not installed or not in PATH.")
        sys.exit(1)


def run_ffprobe_has_audio(file_path: Path) -> bool:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(file_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode == 0 and proc.stdout.strip() != ""


def merge(video_file: Path, voiceover_file: Path, output_file: Path) -> int:
    # Keep video from video_lecture, replace audio with audio from voiceOver.
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_file),
        "-i",
        str(voiceover_file),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output_file),
    ]

    print("Running ffmpeg merge...")
    proc = subprocess.run(cmd)
    return proc.returncode


def main(target_dir: Path = None) -> int:
    if target_dir:
        base_dir = target_dir
    else:
        base_dir = Path.cwd()
        
    video_file = base_dir / "video_lecture.mp4"
    voiceover_file = base_dir / "voiceOver.mp4"
    output_file = base_dir / "video_lecture_with_voiceover.mp4"

    ensure_tool("ffmpeg")
    ensure_tool("ffprobe")

    if not video_file.exists():
        print(f"Error: missing file: {video_file.name}")
        return 1

    if not voiceover_file.exists():
        print(f"Error: missing file: {voiceover_file.name}")
        return 1

    if not run_ffprobe_has_audio(voiceover_file):
        print("Error: voiceOver.mp4 does not appear to contain an audio stream.")
        return 1

    code = merge(video_file, voiceover_file, output_file)
    if code != 0:
        print("Merge failed.")
        return code

    print(f"Done. Output file: {output_file.name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Interrupted.")
        sys.exit(130)
