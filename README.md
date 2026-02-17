# Game Toolbox

A modular, extensible Python toolbox that collects standalone media and game-dev
tools (video frame extraction, image processing, audio slicing, sprite-sheet
generation, asset conversion) under one unified GUI. Tools can run independently
or be chained into pipelines.

## Installation

Requires **Python 3.11+** and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/filthyhuman/game-toolbox.git
cd game-toolbox
uv sync --extra dev
```

## Quick Start

```bash
# Show all available tools
uv run game-toolbox --help

# Extract frames from a video (default: every 500ms, WebP format)
uv run game-toolbox frame-extractor gameplay.mp4

# Launch the GUI
uv run game-toolbox-gui
```

## GUI

Launch the graphical interface with:

```bash
uv run game-toolbox-gui
```

The window presents all tools in a sidebar grouped by category (Image, Video,
Pipelines). Selecting a tool shows an auto-generated parameter form, a **Run**
button, a live progress bar, and a scrollable log area.

- **Auto-generated forms** — fields are created from each tool's
  `define_parameters()` schema (dropdowns, spin boxes, checkboxes, text fields).
- **Threaded execution** — tools run in a background `QThread` so the UI stays
  responsive.  Progress and log events from `EventBus` are bridged to Qt
  signals for thread-safe updates.
- **Pipeline Editor** — placeholder page for a future visual node-graph canvas.

## Available Tools

| Tool | Description |
|------|-------------|
| **Frame Extractor** | Extracts frames from video files at configurable time intervals. |
| **Image Resizer** | Resizes images using exact, fit, fill, or percent modes. |
| **Chroma Key Remover** | Removes solid-colour backgrounds and replaces them with transparency. |
| **Animation Cropper** | Analyses animation frames, computes a union bounding box, and centre-crops to a target size. |
| **Sprite Sheet Generator** | Packs multiple images into a single sprite sheet atlas with metadata. |
| **Sprite Extractor** | Extracts individual sprites from a sprite sheet using grid, auto-detect, or metadata modes. |

### Frame Extractor

Extracts frames from video files at configurable time intervals. Frames are
saved in a timestamped directory (`frames-YYYYMMDD_HHMMSS/`) next to the
input video.

#### CLI Usage

```bash
# Extract every 500ms as WebP (default)
uv run game-toolbox frame-extractor video.mp4

# Extract every 100ms as PNG
uv run game-toolbox frame-extractor video.mp4 --interval 100 --format png

# Extract max 50 frames as JPG with quality 85
uv run game-toolbox frame-extractor video.mp4 -i 1000 -f jpg -q 85 --max 50
```

#### CLI Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--interval` | `-i` | `500` | Interval between frames in milliseconds. |
| `--format` | `-f` | `webp` | Output format: `png`, `webp`, `jpg`, `avif`. |
| `--quality` | `-q` | *auto* | Quality 1-100. Uses format default if omitted. |
| `--max` | | *all* | Maximum number of frames to extract. |

#### Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| **webp** | `.webp` | Default. Best quality/size ratio. |
| **png** | `.png` | Lossless, large files. |
| **jpg** | `.jpg` | Lossy, small files, no transparency. |
| **avif** | `.avif` | Best compression, requires Pillow AVIF support. |

#### Library Usage

```python
from pathlib import Path
from game_toolbox.tools.frame_extractor.logic import extract_frames

result = extract_frames(
    video_path=Path("gameplay.mp4"),
    output_dir=Path("output/frames"),
    interval_ms=500,
    fmt="webp",
)
print(f"Extracted {result.frame_count} frames to {result.output_dir}")
```

See the [Frame Extractor README](src/game_toolbox/tools/frame_extractor/README.md)
for detailed parameter documentation.

### Image Resizer

Resizes images using four modes: **exact** (force dimensions), **fit** (preserve
aspect ratio within a box), **fill** (fill box and crop excess), and **percent**
(scale by percentage). Accepts single files, directories, or a mix of both.

#### CLI Usage

```bash
# Resize to exact 256x256
uv run game-toolbox image-resizer photo.png -m exact -W 256 -H 256

# Fit all images in a directory into a 512x512 box
uv run game-toolbox image-resizer ./sprites/ -m fit -W 512 -H 512

# Scale down to 50%, overwriting originals
uv run game-toolbox image-resizer *.png -m percent -p 50 --in-place

# Custom output directory and resample filter
uv run game-toolbox image-resizer input/ -m fill -W 128 -H 128 -o output/ -r bicubic
```

#### CLI Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--mode` | `-m` | *required* | Resize mode: `exact`, `fit`, `fill`, `percent`. |
| `--width` | `-W` | | Target width in pixels (required for exact/fit/fill). |
| `--height` | `-H` | | Target height in pixels (required for exact/fit/fill). |
| `--percent` | `-p` | | Scale percentage 1-1000 (required for percent mode). |
| `--output` | `-o` | `resized/` | Output directory. Default: `resized/` next to first input. |
| `--in-place` | | `false` | Overwrite original files instead of writing to output dir. |
| `--resample` | `-r` | `lanczos` | Resampling filter: `lanczos`, `bilinear`, `bicubic`, `nearest`. |

#### Library Usage

```python
from pathlib import Path
from game_toolbox.tools.image_resizer.logic import resize_image, resize_batch, collect_image_paths

# Resize a single image
result = resize_image(
    Path("photo.png"),
    Path("output/photo.png"),
    mode="fit",
    width=256,
    height=256,
)
print(f"Resized to {result.width}x{result.height}")

# Batch resize a directory
paths = collect_image_paths([Path("sprites/")])
result = resize_batch(paths, Path("output/"), mode="percent", percent=50)
print(f"Resized {result.count} images")
```

See the [Image Resizer README](src/game_toolbox/tools/image_resizer/README.md)
for detailed parameter documentation.

### Chroma Key Remover

Removes solid-colour backgrounds (green screen, blue screen, custom colours)
from images and replaces them with transparency. Uses NumPy for fast
pixel-level Euclidean distance calculations with configurable tolerance and
soft-edge transition.

#### CLI Usage

```bash
# Remove green background (default)
uv run game-toolbox chroma-key sprites/

# Remove blue background
uv run game-toolbox chroma-key -p blue screenshots/

# Custom colour with tight tolerance
uv run game-toolbox chroma-key -c 128,64,32 -t 20 -s 5 image.png

# Output as WebP
uv run game-toolbox chroma-key -f webp -o output/ sprites/
```

#### CLI Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--preset` | `-p` | `green` | Colour preset: `green`, `blue`, `magenta`. |
| `--color` | `-c` | | Custom RGB colour as `R,G,B` (overrides preset). |
| `--tolerance` | `-t` | `30.0` | Euclidean distance threshold for transparency (0-255). |
| `--softness` | `-s` | `10.0` | Soft-edge transition band width. |
| `--format` | `-f` | `png` | Output format: `png`, `webp` (must support alpha). |
| `--output` | `-o` | `keyed/` | Output directory. Default: `keyed/` next to first input. |
| `--in-place` | | `false` | Overwrite original files. |

#### Library Usage

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
)
```

See the [Chroma Key README](src/game_toolbox/tools/chroma_key/README.md)
for detailed parameter documentation.

### Animation Cropper

Analyses transparent animation frames, computes the union bounding box of all
non-transparent content across all frames, suggests an optimal power-of-two crop
size, and centre-crops all frames to a user-specified size. If the crop window
exceeds the source dimensions, frames are padded with transparency.

#### CLI Usage

```bash
# Analyse only (prints suggested crop size)
uv run game-toolbox animation-cropper frames/

# Crop all frames to 128x128
uv run game-toolbox animation-cropper frames/ -W 128 -H 128

# Custom output directory and WebP format
uv run game-toolbox animation-cropper frames/ -W 64 -H 64 -o trimmed/ -f webp
```

#### CLI Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--width` | `-W` | | Crop width in pixels. Omit for analyse-only mode. |
| `--height` | `-H` | | Crop height in pixels. Omit for analyse-only mode. |
| `--output` | `-o` | `cropped/` | Output directory. Default: `cropped/` next to first input. |
| `--format` | `-f` | `png` | Output format: `png`, `webp` (must support transparency). |

#### Library Usage

```python
from pathlib import Path
from game_toolbox.tools.animation_cropper.logic import analyze_only, crop_batch

# Analyse only
result = analyze_only([Path("frame_01.png"), Path("frame_02.png")])
print(f"Suggested: {result.suggested_width}x{result.suggested_height}")

# Crop all frames
result = crop_batch(
    input_paths=[Path("frame_01.png"), Path("frame_02.png")],
    output_dir=Path("cropped"),
    width=128,
    height=128,
)
print(f"Cropped {result.count} frames")
```

See the [Animation Cropper README](src/game_toolbox/tools/animation_cropper/README.md)
for detailed parameter documentation.

### Sprite Sheet Generator

Packs multiple images into a single sprite sheet atlas with metadata. Supports
JSON, CSS, and XML metadata formats. Images are laid out in a grid with
configurable columns and padding.

#### CLI Usage

```bash
# Auto-layout from a directory
uv run game-toolbox sprite-sheet sprites/

# Custom columns and padding
uv run game-toolbox sprite-sheet -c 8 -p 2 frames/

# Output with CSS metadata
uv run game-toolbox sprite-sheet -m css -o atlas.png sprites/
```

#### CLI Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `sprite_sheet.png` | Output file path. |
| `--columns` | `-c` | *auto* | Number of columns (default: `ceil(sqrt(n))`). |
| `--padding` | `-p` | `1` | Pixel padding between frames. |
| `--metadata` | `-m` | `json` | Metadata format: `json`, `css`, `xml`. |

#### Library Usage

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
print(f"Metadata: {result.metadata_path}")
```

See the [Sprite Sheet README](src/game_toolbox/tools/sprite_sheet/README.md)
for detailed parameter documentation.

### Sprite Extractor

Extracts individual sprites from a sprite sheet image. Inverse of the Sprite
Sheet Generator. Supports three extraction modes: grid-based (frame size or
column/row count), auto-detect (alpha-based connected components via OpenCV),
and metadata-based (JSON from the Sprite Sheet Generator).

#### CLI Usage

```bash
# Grid mode: extract 32x32 sprites
uv run game-toolbox sprite-extractor sheet.png -m grid -W 32 -H 32

# Grid mode: extract from a 4x4 grid
uv run game-toolbox sprite-extractor sheet.png -m grid -c 4 -r 4

# Auto-detect sprites by alpha
uv run game-toolbox sprite-extractor sheet.png -m auto

# Use metadata from sprite-sheet tool
uv run game-toolbox sprite-extractor sheet.png -m metadata --metadata sheet.json

# Custom output directory and format
uv run game-toolbox sprite-extractor sheet.png -m grid -W 32 -H 32 -f webp -o output/
```

#### CLI Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--name` | `-n` | input stem | Base filename for output sprites. |
| `--mode` | `-m` | `grid` | Extraction mode: `grid`, `auto`, `metadata`. |
| `--width` | `-W` | | Frame width (grid mode, with `-H`). |
| `--height` | `-H` | | Frame height (grid mode, with `-W`). |
| `--columns` | `-c` | | Columns (grid mode, with `-r`). |
| `--rows` | `-r` | | Rows (grid mode, with `-c`). |
| `--format` | `-f` | `png` | Output format: `bmp`, `png`, `tiff`, `webp`. |
| `--output` | `-o` | `sprites/` | Output directory. |
| `--metadata` | | | JSON metadata file (metadata mode). |

#### Library Usage

```python
from pathlib import Path
from game_toolbox.tools.sprite_extractor.logic import (
    extract_grid,
    extract_auto_detect,
    extract_from_metadata,
)

# Grid extraction by frame size
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

See the [Sprite Extractor README](src/game_toolbox/tools/sprite_extractor/README.md)
for detailed parameter documentation.

## Architecture

Game Toolbox follows a layered architecture with strict separation of concerns:

```
Presentation (CLI / GUI / Library import)
        |
  Core Framework (Registry, Pipeline, EventBus, ConfigManager)
        |
    BaseTool ABC (Template Method pattern)
        |
  Concrete Tools (frame_extractor, image_resizer, chroma_key, sprite_sheet, sprite_extractor, animation_cropper, ...)
```

Each tool is a self-contained sub-package under `src/game_toolbox/tools/` with
its own `logic.py` (pure computation), `tool.py` (BaseTool adapter), and
`tests/` directory. New tools are auto-discovered at startup with zero changes
to existing code.

For full API documentation, see [docs/api.md](docs/api.md).

## Development

### Running Quality Checks

```bash
uv run ruff check src/ tests/         # lint
uv run ruff format --check src/ tests/ # format check
uv run mypy src/                       # type check (strict)
uv run pytest -v                       # run all tests
uv run pytest --cov=game_toolbox       # with coverage report
```

### Adding a New Tool

1. Create `src/game_toolbox/tools/<tool_name>/` with `__init__.py`, `tool.py`,
   `logic.py`, `README.md`, and a `tests/` directory.
2. Subclass `BaseTool` in `tool.py` and implement all abstract methods.
3. Put pure computation in `logic.py` (no GUI imports).
4. Write tests (minimum 3: happy path, edge case, error case).
5. The tool appears automatically in the CLI and GUI on next startup.

### Project Structure

```
game-toolbox/
├── src/game_toolbox/
│   ├── core/          # Framework: BaseTool ABC, Registry, Pipeline, EventBus
│   ├── cli/           # Click-based CLI layer
│   ├── gui/           # PySide6 GUI layer
│   └── tools/         # Tool sub-packages (auto-discovered)
│       ├── frame_extractor/
│       ├── image_resizer/
│       ├── chroma_key/
│       ├── sprite_sheet/
│       ├── sprite_extractor/
│       └── animation_cropper/
├── tests/             # Integration tests
├── docs/              # API reference documentation
└── pyproject.toml     # Single source of truth for build, lint, type check
```

## License

GPL-3.0-only
