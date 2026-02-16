# Animation Cropper

Analyses transparent animation frames, computes the union bounding box of all
non-transparent content, suggests an optimal crop size, and centre-crops all
frames to a user-specified size.

## Features

- **Union bounding box analysis** — finds the smallest rectangle that encloses
  all non-transparent pixels across all frames.
- **Suggested size** — rounds up the union bbox to the next power-of-two for
  game-engine-friendly dimensions.
- **Centre crop** — crops from the image centre. If the crop window exceeds the
  source dimensions, the frame is padded with transparency.
- **Analyse-only mode** — omit width/height to get the suggested size without
  writing any files.

## CLI Usage

```bash
# Analyse only (prints suggested size)
game-toolbox animation-cropper frames/

# Crop all frames to 128x128
game-toolbox animation-cropper frames/ -W 128 -H 128

# Custom output directory and format
game-toolbox animation-cropper frames/ -W 64 -H 64 -o trimmed/ -f webp
```

## Library Usage

```python
from pathlib import Path
from game_toolbox.tools.animation_cropper.logic import analyze_only, crop_batch

# Analyse
result = analyze_only([Path("frame_01.png"), Path("frame_02.png")])
print(f"Suggested: {result.suggested_width}x{result.suggested_height}")

# Crop
result = crop_batch(
    input_paths=[Path("frame_01.png"), Path("frame_02.png")],
    output_dir=Path("cropped"),
    width=128,
    height=128,
)
```
