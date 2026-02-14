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

# Launch the GUI (not yet implemented)
uv run game-toolbox-gui
```

## Available Tools

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

## Architecture

Game Toolbox follows a layered architecture with strict separation of concerns:

```
Presentation (CLI / GUI / Library import)
        |
  Core Framework (Registry, Pipeline, EventBus, ConfigManager)
        |
    BaseTool ABC (Template Method pattern)
        |
  Concrete Tools (frame_extractor, image_resizer, ...)
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
│       └── image_resizer/
├── tests/             # Integration tests
├── docs/              # API reference documentation
└── pyproject.toml     # Single source of truth for build, lint, type check
```

## License

GPL-3.0-only
