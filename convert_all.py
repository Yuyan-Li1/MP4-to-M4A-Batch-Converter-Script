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
        m4a_path = mp4_path.with_suffix(".m4a")

        if dry_run:
            # Simulate processing with visible progress bar
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

        # Get media duration for real progress tracking
        total_duration = get_media_duration(mp4_path)

        # Create progress bar
        if total_duration:
            pbar = tqdm(
                total=100,
                desc=f"🔄 {filename[:40]}",
                unit="%",
                position=position,
                leave=False,
            )
        else:
            # Fallback to indeterminate progress
            pbar = tqdm(
                desc=f"🔄 {filename[:40]}",
                position=position,
                leave=False,
                bar_format="{desc}: {elapsed}",
            )

        try:
            # Run ffmpeg with progress output
            process = subprocess.Popen(
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
            )

            error_output = []
            last_progress = 0

            # Parse progress output in real-time
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
                        progress_pct = min(
                            100, int((current_seconds / total_duration) * 100)
                        )

                        # Update progress bar
                        if progress_pct > last_progress:
                            pbar.update(progress_pct - last_progress)
                            last_progress = progress_pct
                    except (ValueError, IndexError):
                        pass

            process.wait()
            pbar.close()

            duration = time.time() - start_time

            if process.returncode != 0:
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
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        return str(timedelta(seconds=int(seconds)))


def main():
    """Main conversion process."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Convert MP4 files to M4A (audio only) in parallel"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate conversion without actually processing files",
    )
    args = parser.parse_args()

    # Find all MP4 files in current directory
    mp4_files = list(Path.cwd().glob("*.mp4"))

    if not mp4_files:
        if not args.dry_run:
            print("⚠️  No MP4 files found in current directory")
            return 0
        # In dry-run mode with no files, create fake ones to demonstrate
        print("⚠️  No MP4 files found - creating simulated files for demonstration\n")
        mp4_files = [Path(f"sample_video_{i}.mp4") for i in range(1, 6)]

    # Get number of workers
    num_workers = get_cpu_count(len(mp4_files))

    if args.dry_run:
        print("🧪 DRY RUN MODE - No files will be converted or deleted")
        print(f"   CPU cores detected: {num_workers}\n")

    print(f"🎬 Found {len(mp4_files)} MP4 file(s) to convert")
    print(f"🚀 Using {num_workers} parallel workers\n")

    # Track results and timing
    successful = []
    failed = []
    file_times = {}
    overall_start = time.time()

    # Process files in parallel with individual progress bars per worker
    print("Starting conversions...\n")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Create overall progress bar at top
        with tqdm(
            total=len(mp4_files),
            desc="📊 Overall",
            unit="file",
            position=0,
            leave=True,
        ) as overall_pbar:
            # Submit all tasks with position tracking
            futures = {}
            for idx, mp4_file in enumerate(mp4_files):
                # Assign position based on worker slot (cycle through available positions)
                position = (idx % num_workers) + 1
                future = executor.submit(convert_file, mp4_file, args.dry_run, position)
                futures[future] = mp4_file

            # Process completed tasks
            for future in as_completed(futures):
                mp4_file = futures[future]
                success, filename, error_msg, duration = future.result()

                file_times[filename] = duration

                if success:
                    successful.append(filename)
                    overall_pbar.write(f"✅ {filename} ({format_time(duration)})")
                else:
                    failed.append((filename, error_msg))
                    overall_pbar.write(
                        f"❌ {filename}: {error_msg} ({format_time(duration)})"
                    )

                overall_pbar.update(1)

    overall_duration = time.time() - overall_start

    # Print summary
    print(f"\n{'='*60}")
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

    print(f"{'='*60}")

    if args.dry_run:
        print("\n🧪 Dry run complete - no files were modified")

    if failed:
        print("\n❌ Failed conversions:")
        for filename, error in failed:
            print(f"   • {filename}: {error}")
        return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
