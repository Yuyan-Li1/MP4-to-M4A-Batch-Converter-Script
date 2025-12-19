# MP4 to M4A Batch Converter Script

A fast, parallel MP4 to M4A audio converter script with real-time progress tracking. Perfect for extracting audio from video files in bulk.

## Features

- 🚀 **Parallel Processing** - Automatically utilizes all CPU cores for maximum speed
- 📊 **Real-time Progress** - Individual and overall progress bars for all conversions
- 🎯 **Automatic Cleanup** - Removes original MP4 files after successful conversion
- 🧪 **Dry Run Mode** - Test the conversion process without modifying files
- ⚡ **Smart Progress Tracking** - Uses ffprobe to calculate accurate progress percentages

## Requirements

- Python 3.6+
- [FFmpeg](https://ffmpeg.org/) with `ffmpeg` and `ffprobe` in your PATH
- `tqdm` (auto-installed if missing)

## Usage

### Basic Conversion

Convert all MP4 files in the current directory:

```bash
python convert_all.py
```

### Dry Run Mode

Preview what would be converted without modifying any files:

```bash
python convert_all.py --dry-run
```

## How It Works

1. **Scans** the current directory for all `.mp4` files
2. **Analyzes** each file to determine its duration (for progress tracking)
3. **Converts** files in parallel using all available CPU cores
4. **Tracks** real-time conversion progress with individual progress bars per file
5. **Removes** original MP4 files after successful conversion
6. **Reports** detailed statistics including timing and success/failure rates

## Output Format

The script converts MP4 files to M4A using:

- **Audio codec**: AAC
- **Quality**: High quality (q:a=2)
- **No video stream** - audio only

## Example Output

```text
🎬 Found 5 MP4 file(s) to convert
🚀 Using 8 parallel workers

Starting conversions...

📊 Overall: 100%|████████████████████| 5/5 [00:23<00:00,  4.6s/file]
✅ episode_1.mp4 (4.2s)
✅ episode_2.mp4 (5.1s)
✅ episode_3.mp4 (3.8s)
✅ episode_4.mp4 (4.9s)
✅ episode_5.mp4 (5.3s)

============================================================
📊 Conversion Summary:
   ✅ Successful: 5
   ❌ Failed: 0
   ⏱️  Total time: 23.4s
   📈 Avg time per file: 4.7s
   🐇 Fastest: episode_3.mp4 (3.8s)
   🐢 Slowest: episode_5.mp4 (5.3s)
============================================================
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Simulate conversion without processing files |
| `--help` | Show help message and exit |

## Technical Details

- **Parallelization**: Uses Python's `ThreadPoolExecutor` with worker count based on CPU cores
- **Progress Tracking**: Parses FFmpeg's progress output (`out_time_ms`) for accurate percentage calculation
- **Error Handling**: Captures and reports FFmpeg errors with detailed messages
- **File Safety**: Only deletes original MP4 files after successful conversion

## Exit Codes

- `0` - Success (all files converted successfully)
- `1` - Partial or complete failure (one or more files failed to convert)
- `130` - Interrupted by user (Ctrl+C)

## License

This project is provided as-is for personal use.
