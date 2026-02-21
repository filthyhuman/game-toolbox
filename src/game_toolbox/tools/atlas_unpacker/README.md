# Atlas Unpacker

Extracts individual sprites from Cocos2d texture atlas files. Parses
`.plist` atlas descriptors paired with `.pvr.ccz`, `.pvr`, or `.png`
textures.

Handles:

- **CCZ decompression** (zlib, bzip2, gzip, none)
- **PVR v2/v3** texture parsing (12+ pixel formats)
- **Sprite rotation** — un-rotates sprites packed 90° CW
- **Sprite trimming** — preserves original frame names

## CLI Usage

```bash
# Extract all sprites from a plist + pvr.ccz pair
uv run game-toolbox atlas-unpacker atlas.plist

# Custom output directory
uv run game-toolbox atlas-unpacker atlas.plist -o sprites/

# Skip already-extracted sprites
uv run game-toolbox atlas-unpacker atlas.plist --skip-existing

# Add @2x suffix for retina/HD assets
uv run game-toolbox atlas-unpacker atlas.plist --suffix @2x

# Dry run — show metadata without extracting
uv run game-toolbox atlas-unpacker atlas.plist --dry-run

# Use PVRTexToolCLI for PVRTC textures
uv run game-toolbox atlas-unpacker atlas.plist --pvrtextool /usr/local/bin/PVRTexToolCLI
```

## Parameters

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| `input` | positional | *required* | Path to the `.plist` atlas descriptor. |
| `output_dir` | `-o` | `unpacked/` | Output directory for extracted sprites. |
| `skip_existing` | `--skip-existing` | `false` | Skip sprites whose output file already exists. |
| `suffix` | `--suffix` | `""` | Suffix before `.png` extension (e.g. `@2x` for retina assets). |
| `pvrtextool` | `--pvrtextool` | | Path to PVRTexToolCLI (PVRTC textures only). |
| `dry_run` | `--dry-run` | `false` | Show atlas metadata without extracting. |

## Supported Texture Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| **PNG** | `.png` | Direct loading via Pillow. |
| **PVR v2** | `.pvr` | Supports RGBA8888, RGBA4444, RGBA5551, RGB565, RGB555, RGB888, I8, AI88, BGRA8888, A8. |
| **PVR v3** | `.pvr` | Uncompressed formats with 8-bit channels. |
| **PVR.CCZ** | `.pvr.ccz` | CCZ-compressed PVR (zlib/bzip2/gzip). |
| **PVRTC** | `.pvr` | GPU-compressed; requires PVRTexToolCLI. |

## Library Usage

```python
from pathlib import Path
from game_toolbox.tools.atlas_unpacker.logic import extract_atlas, probe_atlas

# Extract all sprites
result = extract_atlas(
    Path("GameObjects.plist"),
    Path("output/sprites"),
    suffix="@2x",  # optional: adds @2x before .png extension
)
print(f"Extracted {result.count} sprites to {result.output_dir}")

# Dry-run / preview
info = probe_atlas(Path("GameObjects.plist"))
print(f"Atlas has {info['frame_count']} frames")
print(f"Texture: {info['texture']}")
```
