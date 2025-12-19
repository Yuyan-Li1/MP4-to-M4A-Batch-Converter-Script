#!/usr/bin/env python3
"""
Convert MP4 files to M4A (audio only) in parallel with progress tracking.
"""

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from typing import Optional, Tuple

try:
    from tqdm import tqdm
except ImportError:
    print("📦 Installing required package: tqdm")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm"])
    from tqdm import tqdm


def get_cpu_count(num_files: int) -> int:
    """Get the number of CPU cores."""
    try:
        # macOS
        result = subprocess.run(
            ["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True, check=True
        )
        return max(int(result.stdout.strip()), num_files)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to Python's os module
        return max(os.cpu_count() or 4, num_files)


def get_media_duration(file_path: Path) -> Optional[float]:
    """Get the duration of a media file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (ValueError, FileNotFoundError):
        pass
    return None


def _simulate_dry_run(
    filename: str, position: int, start_time: float
) -> Tuple[bool, str, str, float]:
    """Simulate file conversion in dry-run mode."""
    with tqdm(
        total=100,
        desc=f"🔄 {filename[:40]}",
        unit="%",
        position=position,
        leave=False,
    ) as pbar:
        for _ in range(100):
            time.sleep(0.005)  # Simulate work
            pbar.update(1)
    duration = time.time() - start_time
    return True, filename, "", duration


def _create_progress_bar(filename: str, position: int, total_duration: Optional[float]):
    """Create a progress bar based on whether duration is available."""
    if total_duration:
        return tqdm(
            total=100,
            desc=f"🔄 {filename[:40]}",
            unit="%",
            position=position,
            leave=False,
        )
    # Fallback to indeterminate progress
    return tqdm(
        desc=f"🔄 {filename[:40]}",
        position=position,
        leave=False,
        bar_format="{desc}: {elapsed}",
    )


def _parse_ffmpeg_progress(process, pbar, total_duration: Optional[float]) -> list:
    """Parse ffmpeg progress output and update progress bar."""
    error_output = []
    last_progress = 0

    for line in process.stderr:
        line = line.strip()

        # Collect error messages
        if line and not line.startswith("out_time_ms=") and "=" not in line:
            error_output.append(line)

        # Parse time progress
        if total_duration and line.startswith("out_time_ms="):
            try:
                time_ms = int(line.split("=")[1])
                current_seconds = time_ms / 1_000_000
                progress_pct = min(100, int((current_seconds / total_duration) * 100))

                # Update progress bar
                if progress_pct > last_progress:
                    pbar.update(progress_pct - last_progress)
                    last_progress = progress_pct
            except (ValueError, IndexError):
                pass

    return error_output


def _run_ffmpeg_conversion(
    mp4_path: Path, m4a_path: Path, pbar, total_duration: Optional[float]
) -> Tuple[int, list]:
    """Run ffmpeg conversion process."""
    with subprocess.Popen(
        [
            "ffmpeg",
            "-i",
            str(mp4_path),
            "-vn",
            "-c:a",
            "aac",
            "-q:a",
            "2",
            "-progress",
            "pipe:2",
            "-nostats",
            "-loglevel",
            "error",
            str(m4a_path),
        ],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    ) as process:
        error_output = _parse_ffmpeg_progress(process, pbar, total_duration)
        process.wait()
        return process.returncode, error_output


def convert_file(
    mp4_path: Path, dry_run: bool = False, position: int = 0
) -> Tuple[bool, str, str, float]:
    """
    Convert a single MP4 file to M4A with individual progress bar.

    Returns:
        Tuple of (success: bool, input_filename: str, error_message: str, duration: float)
    """
    start_time = time.time()
    filename = mp4_path.name

    try:
        if dry_run:
            return _simulate_dry_run(filename, position, start_time)

        m4a_path = mp4_path.with_suffix(".m4a")
        total_duration = get_media_duration(mp4_path)
        pbar = _create_progress_bar(filename, position, total_duration)

        try:
            returncode, error_output = _run_ffmpeg_conversion(
                mp4_path, m4a_path, pbar, total_duration
            )
            pbar.close()

            duration = time.time() - start_time

            if returncode != 0:
                error_msg = "\n".join(error_output) if error_output else "FFmpeg error"
                return False, filename, f"FFmpeg error: {error_msg}", duration

            # Remove original file
            mp4_path.unlink()
            return True, filename, "", duration

        finally:
            if pbar:
                pbar.close()

    except (OSError, subprocess.SubprocessError, ValueError) as e:
        duration = time.time() - start_time
        return False, filename, str(e), duration


def format_time(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return str(timedelta(seconds=int(seconds)))


def _get_mp4_files(dry_run: bool) -> list:
    """Find MP4 files or create simulated ones in dry-run mode."""
    mp4_files = list(Path.cwd().glob("*.mp4"))

    if not mp4_files:
        if not dry_run:
            print("⚠️  No MP4 files found in current directory")
            return []
        # In dry-run mode with no files, create fake ones to demonstrate
        print("⚠️  No MP4 files found - creating simulated files for demonstration\n")
        return [Path(f"sample_video_{i}.mp4") for i in range(1, 6)]

    return mp4_files


def _submit_conversion_tasks(
    executor, mp4_files: list, num_workers: int, dry_run: bool
) -> dict:
    """Submit all conversion tasks to the executor."""
    futures = {}
    for idx, mp4_file in enumerate(mp4_files):
        position = (idx % num_workers) + 1
        future = executor.submit(convert_file, mp4_file, dry_run, position)
        futures[future] = mp4_file
    return futures


def _handle_conversion_result(
    result_tuple: Tuple[bool, str, str, float],
    overall_pbar,
    successful: list,
    failed: list,
    file_times: dict,
):
    """Handle a single conversion result."""
    success, filename, error_msg, duration = result_tuple
    file_times[filename] = duration

    if success:
        successful.append(filename)
        overall_pbar.write(f"✅ {filename} ({format_time(duration)})")
    else:
        failed.append((filename, error_msg))
        overall_pbar.write(f"❌ {filename}: {error_msg} ({format_time(duration)})")


def _process_conversions(
    mp4_files: list, num_workers: int, dry_run: bool
) -> Tuple[list, list, dict]:
    """Process file conversions in parallel."""
    successful = []
    failed = []
    file_times = {}

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = _submit_conversion_tasks(executor, mp4_files, num_workers, dry_run)

        with tqdm(
            total=len(mp4_files),
            desc="📊 Overall",
            unit="file",
            position=0,
            leave=True,
        ) as overall_pbar:
            for future in as_completed(futures):
                result = future.result()
                _handle_conversion_result(
                    result, overall_pbar, successful, failed, file_times
                )
                overall_pbar.update(1)

    return successful, failed, file_times


def _print_summary(
    successful: list,
    failed: list,
    file_times: dict,
    overall_duration: float,
    dry_run: bool,
):
    """Print conversion summary statistics."""
    print(f"\n{'=' * 60}")
    print("📊 Conversion Summary:")
    print(f"   ✅ Successful: {len(successful)}")
    print(f"   ❌ Failed: {len(failed)}")
    print(f"   ⏱️  Total time: {format_time(overall_duration)}")

    if successful:
        avg_time = sum(file_times[f] for f in successful) / len(successful)
        fastest = min((file_times[f], f) for f in successful)
        slowest = max((file_times[f], f) for f in successful)
        print(f"   📈 Avg time per file: {format_time(avg_time)}")
        print(f"   🐇 Fastest: {fastest[1]} ({format_time(fastest[0])})")
        print(f"   🐢 Slowest: {slowest[1]} ({format_time(slowest[0])})")

    print(f"{'=' * 60}")

    if dry_run:
        print("\n🧪 Dry run complete - no files were modified")

    if failed:
        print("\n❌ Failed conversions:")
        for filename, error in failed:
            print(f"   • {filename}: {error}")


def main():
    """Main conversion process."""
    parser = argparse.ArgumentParser(
        description="Convert MP4 files to M4A (audio only) in parallel"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate conversion without actually processing files",
    )
    args = parser.parse_args()

    mp4_files = _get_mp4_files(args.dry_run)
    if not mp4_files:
        return 0

    num_workers = get_cpu_count(len(mp4_files))

    if args.dry_run:
        print("🧪 DRY RUN MODE - No files will be converted or deleted")
        print(f"   CPU cores detected: {num_workers}\n")

    print(f"🎬 Found {len(mp4_files)} MP4 file(s) to convert")
    print(f"🚀 Using {num_workers} parallel workers\n")
    print("Starting conversions...\n")

    overall_start = time.time()
    successful, failed, file_times = _process_conversions(
        mp4_files, num_workers, args.dry_run
    )
    overall_duration = time.time() - overall_start

    _print_summary(successful, failed, file_times, overall_duration, args.dry_run)

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
