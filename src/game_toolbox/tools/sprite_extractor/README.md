# Sprite Extractor

Extracts individual sprites from a sprite sheet image. Supports three
extraction modes:

- **Grid** — split by regular grid (frame size or column/row count).
- **Auto** — detect sprites via alpha-based connected components (OpenCV).
- **Metadata** — use JSON metadata from the Sprite Sheet Generator tool.

## CLI Usage

```bash
# Grid mode: extract 32x32 sprites
uv run game-toolbox sprite-extractor sheet.png -m grid -W 32 -H 32

# Grid mode: extract from a 4x4 grid
uv run game-toolbox sprite-extractor sheet.png -m grid -c 4 -r 4

# Auto-detect mode
uv run game-toolbox sprite-extractor sheet.png -m auto

# Metadata mode
uv run game-toolbox sprite-extractor sheet.png -m metadata --metadata sheet.json
```

## Parameters

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| `input` | positional | *required* | Path to the sprite sheet image. |
| `output_dir` | `-o` | `sprites/` | Output directory for extracted sprites. |
| `base_name` | `-n` | input stem | Base filename for output sprites. |
| `mode` | `-m` | `grid` | Extraction mode: `grid`, `auto`, `metadata`. |
| `frame_width` | `-W` | | Frame width (grid mode, with `-H`). |
| `frame_height` | `-H` | | Frame height (grid mode, with `-W`). |
| `columns` | `-c` | | Columns (grid mode, with `-r`). |
| `rows` | `-r` | | Rows (grid mode, with `-c`). |
| `output_format` | `-f` | `png` | Output format: `bmp`, `png`, `tiff`, `webp`. |
| `metadata_path` | `--metadata` | | JSON metadata file (metadata mode). |

## Library Usage

```python
from pathlib import Path
from game_toolbox.tools.sprite_extractor.logic import (
    extract_grid,
    extract_auto_detect,
    extract_from_metadata,
)

# Grid extraction
result = extract_grid(
    Path("sheet.png"),
    Path("output/"),
    "sprite",
    frame_width=32,
    frame_height=32,
)
print(f"Extracted {result.count} sprites")

# Auto-detection
result = extract_auto_detect(Path("sheet.png"), Path("output/"), "sprite")
print(f"Detected {result.count} sprites")
```
