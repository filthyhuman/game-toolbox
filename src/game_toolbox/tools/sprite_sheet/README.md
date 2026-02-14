# Sprite Sheet Generator

Pack multiple images into a single sprite sheet atlas with metadata.

## How It Works

1. Load all input images and record their dimensions
2. Calculate the grid layout: if `columns` is set, use it; otherwise auto-calculate as `ceil(sqrt(n))`
3. Create a transparent RGBA canvas sized to fit the grid with padding
4. Paste each image into its grid cell
5. Save the sprite sheet as PNG or WebP
6. Generate metadata in JSON, CSS, or XML format

## CLI Usage

```bash
# Auto-layout from a directory
game-toolbox sprite-sheet sprites/

# Custom columns and padding
game-toolbox sprite-sheet -c 8 -p 2 frames/

# Output with CSS metadata
game-toolbox sprite-sheet -m css -o atlas.png sprites/

# Explicit output path
game-toolbox sprite-sheet -o assets/sheet.png -c 4 frames/
```

## Library Usage

```python
from pathlib import Path
from game_toolbox.tools.sprite_sheet.logic import generate_sprite_sheet

result = generate_sprite_sheet(
    [Path("frame_0.png"), Path("frame_1.png"), Path("frame_2.png")],
    Path("output/sheet.png"),
    columns=3,
    padding=1,
    metadata_format="json",
)

print(f"Sheet: {result.sheet.width}x{result.sheet.height}")
print(f"Frames: {len(result.frames)}")
print(f"Metadata: {result.metadata_path}")
```

## Metadata Formats

### JSON (default)

```json
{
  "sprite_sheet": "sheet.png",
  "columns": 4,
  "rows": 3,
  "padding": 1,
  "frames": [
    {"name": "frame_00000", "x": 0, "y": 0, "width": 64, "height": 64}
  ]
}
```

### CSS

```css
.sprite { background-image: url('sheet.png'); }
.sprite.frame_00000 { background-position: -0px -0px; width: 64px; height: 64px; }
```

### XML

```xml
<sprite_sheet image="sheet.png" columns="4" rows="3">
  <frame name="frame_00000" x="0" y="0" width="64" height="64"/>
</sprite_sheet>
```

## Parameters

| Parameter         | Type   | Default          | Description                             |
|-------------------|--------|------------------|-----------------------------------------|
| `output`          | path   | sprite_sheet.png | Output sprite sheet file path           |
| `columns`         | int    | auto             | Number of columns (auto = ceil(sqrt(n)))|
| `padding`         | int    | 1                | Pixel padding between frames            |
| `metadata_format` | string | json             | Metadata format: json, css, xml         |
