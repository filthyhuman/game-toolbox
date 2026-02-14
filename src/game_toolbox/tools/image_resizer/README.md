# Image Resizer

Resize images using four modes: **exact**, **fit**, **fill**, or **percent**.

## Resize Modes

| Mode | Description |
|------|-------------|
| `exact` | Force target dimensions, ignoring aspect ratio |
| `fit` | Fit within a bounding box, preserving aspect ratio |
| `fill` | Fill the bounding box, cropping excess from center |
| `percent` | Scale by a percentage (e.g. 50 = half size) |

## CLI Usage

```bash
# Resize a single image to exact dimensions
game-toolbox image-resizer photo.png -m exact -W 256 -H 256

# Fit all images in a directory into a 512x512 box
game-toolbox image-resizer ./sprites/ -m fit -W 512 -H 512

# Scale down to 50% in-place
game-toolbox image-resizer *.png -m percent -p 50 --in-place

# Custom output directory and resample filter
game-toolbox image-resizer input/ -m fill -W 128 -H 128 -o output/ -r bicubic
```

## Options

| Option | Description |
|--------|-------------|
| `-m / --mode` | Resize mode: exact, fit, fill, percent (required) |
| `-W / --width` | Target width in pixels |
| `-H / --height` | Target height in pixels |
| `-p / --percent` | Scale percentage (1-1000) |
| `-o / --output` | Output directory (default: `resized/` next to first input) |
| `--in-place` | Overwrite original files |
| `-r / --resample` | Resampling filter: lanczos (default), bilinear, bicubic, nearest |

## Pipeline

The Image Resizer accepts `PathList` input (e.g. from Frame Extractor) and produces `PathList` output.

```python
from game_toolbox.core.pipeline import Pipeline

pipeline = Pipeline(name="video-to-thumbnails")
pipeline.add_stage("frame_extractor", params={"interval_ms": 1000, "format": "webp"})
pipeline.add_stage("image_resizer", params={"mode": "fit", "width": 256, "height": 256})
pipeline.run(input_data=Path("gameplay.mp4"))
```
