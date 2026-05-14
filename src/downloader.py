import concurrent.futures
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# Maps stream keys to required output file names.
STREAM_TARGETS = {
    "s0q1": "voiceOver.mp4",
    "s1q1": "video_lecture_slides.mp4",
    "s2q1": "video_lecture.mp4",
}

STREAM_ORDER = ("s0q1", "s1q1", "s2q1")

# Extra grace period above expected duration before considering ffmpeg stuck.
FFMPEG_TIMEOUT_GRACE_SECONDS = 120


def prompt_stream_url(stream_key: str) -> str:
    """Prompt user for a single stream URL and validate basic expected shape."""
    output_name = STREAM_TARGETS[stream_key]
    expected_name = f"{stream_key}.m3u8"

    while True:
        print(
            f"\nEnter URL for {stream_key} (saves as {output_name})"
        )
        print(
            "Expected pattern: https://.../"
            f"{expected_name}?<signed-query-params>"
        )
        value = input("URL: ").strip()

        if not value:
            print("URL cannot be empty.")
            continue
        if not value.startswith(("http://", "https://")):
            print("URL must start with http:// or https://")
            continue
        if ".m3u8" not in value:
            print("URL must contain .m3u8")
            continue
        if expected_name not in value:
            print(
                f"This URL does not include {expected_name}. "
                "Please paste the matching stream URL."
            )
            continue
        if "?" not in value:
            print("URL must include signed query parameters after ?")
            continue

        return value


def get_stream_urls(urls_file: Path) -> Dict[str, str]:
    """Read URLs from a file if it exists, otherwise fallback to prompt."""
    urls: Dict[str, str] = {}
    if urls_file.exists():
        print(f"Reading URLs from {urls_file.name}...")
        for line in urls_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for key in STREAM_ORDER:
                if f"{key}.m3u8" in line:
                    urls[key] = line
                    break

    for key in STREAM_ORDER:
        if key not in urls:
            urls[key] = prompt_stream_url(key)
            
    return urls


def build_fixed_playlist(url: str, output_playlist: Path) -> None:
    """Download m3u8 and rewrite segment/map lines to include auth query params."""
    if "?" not in url:
        raise ValueError(f"URL has no query token: {url}")

    base_url_path, query_string = url.split("?", 1)
    base_path = base_url_path.rsplit("/", 1)[0] + "/"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    new_lines: List[str] = []
    for raw_line in response.text.splitlines():
        line = raw_line.strip()

        if line.startswith("#EXT-X-MAP") and 'URI="' in line:
            prefix, rest = line.split('URI="', 1)
            filename, suffix = rest.split('"', 1)
            full_map_url = f"{base_path}{filename}?{query_string}"
            new_lines.append(f'{prefix}URI="{full_map_url}"{suffix}')
        elif line.endswith((".mp4", ".m4s", ".ts")):
            if line.startswith("http"):
                sep = "&" if "?" in line else "?"
                new_lines.append(f"{line}{sep}{query_string}")
            else:
                new_lines.append(f"{base_path}{line}?{query_string}")
        else:
            new_lines.append(line)

    output_playlist.write_text("\n".join(new_lines), encoding="utf-8")


def get_playlist_info(playlist_path: Path) -> Tuple[float, bool]:
    """Return (estimated duration seconds, has_endlist)."""
    duration = 0.0
    has_endlist = False

    for raw_line in playlist_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if line == "#EXT-X-ENDLIST":
            has_endlist = True

        if line.startswith("#EXTINF:"):
            value = line.split(":", 1)[1].split(",", 1)[0].strip()
            try:
                duration += float(value)
            except ValueError:
                continue

    return duration, has_endlist


def run_ffmpeg(
    playlist_path: Path,
    output_file: Path,
    total_seconds: float,
    force_duration_limit: bool,
    progress_position: int,
    progress_label: str,
    show_progress: bool,
) -> Tuple[int, str]:
    """Run ffmpeg and return (exit_code, combined_output) with optional live progress."""
    cmd = [
        "ffmpeg",
        "-y",
        "-nostats",
        "-progress",
        "pipe:1",
        "-protocol_whitelist",
        "file,http,https,tcp,tls,crypto",
        "-i",
        str(playlist_path),
    ]

    # If playlist has no ENDLIST, ffmpeg may wait forever for future segments.
    # In that case, cap runtime to the expected media duration.
    if force_duration_limit and total_seconds > 0:
        cmd += ["-t", f"{total_seconds:.3f}"]

    cmd += [
        "-c",
        "copy",
        str(output_file),
    ]

    progress_bar = None
    if show_progress and tqdm is not None and total_seconds > 0:
        progress_bar = tqdm(
            total=total_seconds,
            desc=progress_label,
            unit="s",
            position=progress_position,
            leave=True,
            dynamic_ncols=True,
        )

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    log_lines: List[str] = []
    last_seconds = 0.0
    start_time = time.monotonic()
    max_runtime: float | None = None
    if total_seconds > 0:
        max_runtime = total_seconds + FFMPEG_TIMEOUT_GRACE_SECONDS

    try:
        if process.stdout is not None:
            for raw_line in process.stdout:
                log_lines.append(raw_line)
                line = raw_line.strip()
                if not line.startswith("out_time_ms="):
                    continue

                try:
                    out_time_ms = int(line.split("=", 1)[1])
                except ValueError:
                    continue

                current_seconds = out_time_ms / 1_000_000.0
                if progress_bar is not None and current_seconds >= last_seconds:
                    progress_bar.update(current_seconds - last_seconds)
                    last_seconds = current_seconds

                if max_runtime is not None:
                    elapsed = time.monotonic() - start_time
                    if elapsed > max_runtime:
                        process.kill()
                        log_lines.append(
                            "\n[timeout] ffmpeg exceeded expected runtime and was terminated.\n"
                        )
                        break

        process.wait()
    finally:
        if progress_bar is not None:
            if total_seconds > last_seconds:
                progress_bar.update(total_seconds - last_seconds)
            progress_bar.close()

    return process.returncode, "".join(log_lines)


def download_one(
    stream_key: str,
    stream_url: str,
    work_dir: Path,
    progress_position: int,
    show_progress: bool,
) -> Tuple[bool, str]:
    """Prepare fixed playlist and download one stream."""
    output_file = work_dir / STREAM_TARGETS[stream_key]
    playlist_file = work_dir / f"fixed_{stream_key}.m3u8"

    try:
        build_fixed_playlist(stream_url, playlist_file)
        duration, has_endlist = get_playlist_info(playlist_file)

        if duration <= 0:
            return (
                False,
                f"{stream_key} failed: unable to estimate playlist duration.",
            )

        code, logs = run_ffmpeg(
            playlist_file,
            output_file,
            total_seconds=duration,
            force_duration_limit=not has_endlist,
            progress_position=progress_position,
            progress_label=f"{stream_key} -> {output_file.name}",
            show_progress=show_progress,
        )
        if code == 0:
            return True, f"{stream_key} -> {output_file.name}"
        return False, f"{stream_key} failed with ffmpeg exit {code}.\n{logs}"
    except Exception as exc:
        return False, f"{stream_key} failed: {exc}"


def run_parallel(
    urls: Dict[str, str],
    work_dir: Path,
    show_progress: bool,
) -> Dict[str, Tuple[bool, str]]:
    """Run all downloads in parallel."""
    results: Dict[str, Tuple[bool, str]] = {}

    positions = {key: idx for idx, key in enumerate(STREAM_ORDER)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls)) as pool:
        future_map = {
            pool.submit(
                download_one,
                key,
                stream_url,
                work_dir,
                positions[key],
                show_progress,
            ): key
            for key, stream_url in urls.items()
        }

        for future in concurrent.futures.as_completed(future_map):
            key = future_map[future]
            results[key] = future.result()

    return results


def run_sequential(
    urls: Dict[str, str],
    work_dir: Path,
    show_progress: bool,
) -> Dict[str, Tuple[bool, str]]:
    """Run downloads in deterministic order."""
    results: Dict[str, Tuple[bool, str]] = {}
    positions = {key: idx for idx, key in enumerate(STREAM_ORDER)}
    for key in STREAM_ORDER:
        if key in urls:
            results[key] = download_one(
                key,
                urls[key],
                work_dir,
                positions[key],
                show_progress,
            )
    return results


def print_results(results: Dict[str, Tuple[bool, str]]) -> None:
    for key in STREAM_ORDER:
        ok, message = results[key]
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {message}")


def main(target_dir: Path = None) -> int:
    print("--- Echo360 Multi-Stream Downloader ---")

    if target_dir:
        script_dir = target_dir
    else:
        script_dir = Path.cwd()
        
    urls_file = script_dir / "urls.txt"
    urls = get_stream_urls(urls_file)
    print("Starting parallel download...")

    show_progress = True
    if tqdm is None:
        show_progress = False
        print("tqdm is not installed; running without progress bars.")

    parallel_results = run_parallel(urls, script_dir, show_progress=show_progress)
    print_results(parallel_results)

    if all(ok for ok, _ in parallel_results.values()):
        print("\nAll streams downloaded in parallel.")
        return 0

    print("\nParallel mode had failures. Retrying failed streams sequentially...")

    failed_urls = {
        key: urls[key]
        for key, (ok, _) in parallel_results.items()
        if not ok
    }

    sequential_results = run_sequential(
        failed_urls,
        script_dir,
        show_progress=show_progress,
    )

    # Merge retry results into original result map.
    for key, value in sequential_results.items():
        parallel_results[key] = value

    print_results(parallel_results)

    if all(ok for ok, _ in parallel_results.values()):
        print("\nCompleted after sequential retry.")
        return 0

    print("\nSome streams still failed. See logs above.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
