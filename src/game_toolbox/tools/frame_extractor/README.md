# Frame Extractor

Extracts frames from video files at configurable time intervals.

## CLI Usage

```bash
# Extract every 500ms as WebP (default)
game-toolbox frame-extractor video.mp4

# Extract every 100ms as PNG
game-toolbox frame-extractor video.mp4 --interval 100 --format png

# Extract max 50 frames as JPG with quality 85
game-toolbox frame-extractor video.mp4 -i 1000 -f jpg -q 85 --max 50
```

Frames are saved in a `frames-YYYYMMDD_HHMMSS/` directory next to the input video.

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| **webp** | `.webp` | Default. Best quality/size ratio. |
| **png** | `.png` | Lossless, large files. |
| **jpg** | `.jpg` | Lossy, small files, no transparency. |
| **avif** | `.avif` | Best compression, requires Pillow AVIF support. |

## Library Usage

```python
from pathlib import Path
from game_toolbox.tools.frame_extractor.logic import extract_frames

result = extract_frames(
    video_path=Path("gameplay.mp4"),
    output_dir=Path("output/frames"),
    interval_ms=500,
    fmt="webp",
)
print(f"Extracted {result.frame_count} frames")
```

## Parameters

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `video_path` | `Path` | *required* | Path to the input video file. |
| `output_dir` | `Path` | *required* | Directory for extracted frames. |
| `interval_ms` | `int` | `500` | Interval between frames in milliseconds. |
| `fmt` | `str` | `"webp"` | Output image format. |
| `quality` | `int\|None` | `None` | Quality 1-100. Uses format default if unset. |
| `max_frames` | `int\|None` | `None` | Max frames to extract. `None` = all. |
