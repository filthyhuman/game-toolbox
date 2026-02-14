# Chroma Key Remover

Remove solid-colour backgrounds (green screen, blue screen, etc.) from images
and replace them with transparency.

## How It Works

1. Open the image and convert to RGBA
2. Calculate the Euclidean RGB distance from each pixel to the target colour
3. Pixels within the **tolerance** threshold become fully transparent
4. Pixels in the **softness** transition band receive proportional alpha (anti-aliasing)
5. Save the result as PNG or WebP (formats that support alpha)

## CLI Usage

```bash
# Remove green background (default)
game-toolbox chroma-key sprites/

# Remove blue background
game-toolbox chroma-key -p blue screenshots/

# Custom colour with tight tolerance
game-toolbox chroma-key -c 128,64,32 -t 20 -s 5 image.png

# Output as WebP
game-toolbox chroma-key -f webp -o output/ sprites/

# In-place (overwrite originals)
game-toolbox chroma-key --in-place sprites/
```

## Library Usage

```python
from pathlib import Path
from game_toolbox.tools.chroma_key.logic import remove_chroma_key, chroma_key_batch

# Single image
result = remove_chroma_key(
    Path("input.png"),
    Path("output.png"),
    color=(0, 177, 64),
    tolerance=30.0,
    softness=10.0,
)

# Batch
result = chroma_key_batch(
    [Path("a.png"), Path("b.png")],
    Path("output/"),
    color=(0, 177, 64),
    output_format="png",
)
```

## Colour Presets

| Preset    | RGB           |
|-----------|---------------|
| `green`   | (0, 177, 64)  |
| `blue`    | (0, 71, 187)  |
| `magenta` | (255, 0, 255) |

## Parameters

| Parameter       | Type    | Default | Description                              |
|----------------|---------|---------|------------------------------------------|
| `color`        | R,G,B   | —       | Custom target colour (overrides preset)  |
| `preset`       | string  | green   | Colour preset: green, blue, magenta      |
| `tolerance`    | float   | 30.0    | Distance threshold for full transparency |
| `softness`     | float   | 10.0    | Transition band width for soft edges     |
| `output_format`| string  | png     | Output format (png or webp)              |
| `in_place`     | bool    | false   | Overwrite originals                      |
