"""Pure atlas extraction logic — no GUI imports allowed.

Integrates the plist parser, CCZ decompressor, and PVR decoder to extract
individual sprite PNG files from Cocos2d texture atlas pairs.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from PIL import Image

from game_toolbox.core.datatypes import AtlasUnpackResult, ImageData
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError
from game_toolbox.tools.atlas_unpacker._ccz import decompress_ccz, is_ccz
from game_toolbox.tools.atlas_unpacker._plist import AtlasSpriteFrame, load_plist, plist_metadata
from game_toolbox.tools.atlas_unpacker._pvr import parse_pvr

logger = logging.getLogger(__name__)

# Texture file suffixes tried in order when locating the atlas texture.
_TEXTURE_SUFFIXES = (".pvr.ccz", ".pvr", ".png")


# ── Validation ────────────────────────────────────────────────────────────


def validate_atlas_params(*, plist_path: Path | None, output_dir: Path | None) -> None:
    """Validate atlas unpack parameters before processing.

    Args:
        plist_path: Path to the .plist descriptor file.
        output_dir: Output directory for extracted sprites.

    Raises:
        ValidationError: If the plist path is missing or invalid.
    """
    if plist_path is None:
        msg = "A .plist file path is required"
        raise ValidationError(msg)
    if not plist_path.exists():
        msg = f"Plist file does not exist: '{plist_path}'"
        raise ValidationError(msg)
    if plist_path.suffix.lower() != ".plist":
        msg = f"Expected a .plist file, got: '{plist_path.name}'"
        raise ValidationError(msg)


# ── Public API ────────────────────────────────────────────────────────────


def extract_atlas(
    plist_path: Path,
    output_dir: Path,
    *,
    suffix: str = "",
    skip_existing: bool = False,
    pvrtextool: Path | None = None,
    event_bus: EventBus | None = None,
) -> AtlasUnpackResult:
    """Extract all sprite frames from a Cocos2d .plist + texture atlas pair.

    Args:
        plist_path: Path to the Cocos2d .plist sprite sheet descriptor.
        output_dir: Directory where individual PNG files will be written.
            Created automatically if it does not exist.
        suffix: String appended before the ``.png`` extension in each output
            filename.  For example, ``"@2x"`` produces ``sprite@2x.png``.
        skip_existing: When True, skip frames whose output file already exists.
        pvrtextool: Optional path to the PVRTexToolCLI binary. Required only
            when the atlas uses PVRTC GPU compression.
        event_bus: Optional event bus for progress reporting.

    Returns:
        An ``AtlasUnpackResult`` with output directory, image metadata, and count.

    Raises:
        ToolError: If the texture cannot be found, loaded, or parsed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve PVRTexToolCLI
    tool = pvrtextool or _pvrtextool_from_env()

    # Load atlas image
    texture_path = _find_texture(plist_path)
    atlas_image = _load_texture(texture_path, pvrtextool=tool)

    # Load frame descriptors
    frames = load_plist(plist_path)

    total = len(frames)
    images: list[ImageData] = []

    for idx, (name, frame) in enumerate(frames.items()):
        stem = name[:-4] if name.lower().endswith(".png") else name
        out_name = stem + suffix + ".png"
        out_path = output_dir / out_name

        if skip_existing and out_path.exists():
            if event_bus is not None:
                event_bus.emit(
                    "progress",
                    tool="atlas_unpacker",
                    current=idx + 1,
                    total=total,
                    message=f"Skipped (exists) {out_name}",
                )
            continue

        sprite = _crop_sprite(atlas_image, frame)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sprite.save(str(out_path), "PNG")

        images.append(
            ImageData(
                path=out_path,
                width=sprite.width,
                height=sprite.height,
                format="png",
            )
        )

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="atlas_unpacker",
                current=idx + 1,
                total=total,
                message=f"Extracted {out_name} ({idx + 1}/{total})",
            )

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="atlas_unpacker",
            message=f"Done — {len(images)} sprites extracted from '{plist_path.name}'",
        )

    return AtlasUnpackResult(
        output_dir=output_dir,
        images=tuple(images),
        count=len(images),
    )


def probe_atlas(plist_path: Path) -> dict[str, Any]:
    """Return metadata about an atlas without extracting any images.

    Useful for dry-run / preview in a GUI toolbox panel.

    Args:
        plist_path: Path to the .plist descriptor file.

    Returns:
        A dict with keys: ``plist``, ``texture``, ``frame_count``,
        ``frame_names``, ``metadata``.
    """
    try:
        texture_path: Path | None = _find_texture(plist_path)
    except ToolError:
        texture_path = None

    frames = load_plist(plist_path)
    meta = plist_metadata(plist_path)

    return {
        "plist": plist_path.resolve(),
        "texture": texture_path.resolve() if texture_path else None,
        "frame_count": len(frames),
        "frame_names": list(frames.keys()),
        "metadata": meta,
    }


# ── Internal helpers ──────────────────────────────────────────────────────


def _pvrtextool_from_env() -> Path | None:
    """Read PVRTexToolCLI path from the environment variable.

    Returns:
        A Path to the tool, or None if the variable is not set.
    """
    value = os.environ.get("PVRTEXTOOL")
    return Path(value) if value else None


def _find_texture(plist_path: Path) -> Path:
    """Locate the matching texture file next to the plist.

    Args:
        plist_path: Path to the .plist file.

    Returns:
        Path to the texture file.

    Raises:
        ToolError: If no matching texture file is found.
    """
    stem = plist_path.stem
    for suffix in _TEXTURE_SUFFIXES:
        candidate = plist_path.with_name(stem + suffix)
        if candidate.exists():
            return candidate
    tried = ", ".join(stem + s for s in _TEXTURE_SUFFIXES)
    msg = f"No texture found for '{plist_path.name}'. Tried: {tried}"
    raise ToolError(msg)


def _load_texture(path: Path, *, pvrtextool: Path | None) -> Image.Image:
    """Decompress and parse the atlas texture into a PIL Image.

    Args:
        path: Path to the texture file (.png, .pvr, or .pvr.ccz).
        pvrtextool: Optional path to PVRTexToolCLI for PVRTC decoding.

    Returns:
        An RGBA PIL Image of the full atlas.

    Raises:
        ToolError: If the texture cannot be read or decoded.
    """
    if path.suffix.lower() == ".png":
        try:
            return Image.open(path).convert("RGBA")
        except Exception as exc:
            msg = f"Failed to open texture image: '{path}'"
            raise ToolError(msg) from exc

    raw = path.read_bytes()

    # Decompress CCZ wrapper if present
    if is_ccz(raw):
        raw = decompress_ccz(raw)

    return parse_pvr(raw, pvrtextool=pvrtextool)


def _crop_sprite(atlas: Image.Image, frame: AtlasSpriteFrame) -> Image.Image:
    """Crop one sprite frame from the atlas, un-rotating if necessary.

    Coordinate conventions:
        1. **Y-axis**: Cocos2d plist frame rects use bottom-left origin
           (OpenGL convention).  PIL uses top-left, so we flip::

               y_pil = atlas.height - frame.y - packed_h

        2. **Vertical flip**: PVR texture data is stored bottom-to-top.
           PIL's ``frombytes`` puts row 0 of the data at the top of the
           image, visually inverting all rows.  ``FLIP_TOP_BOTTOM`` corrects
           this.

    Rotated sprites (``rotated=True``):
        TexturePacker packs some sprites 90 deg CW to save space.  In the
        plist, ``frame.w`` and ``frame.h`` are the **original** (unrotated)
        sprite dimensions.  The sprite occupies ``(frame.h x frame.w)``
        pixels in the atlas.

        To recover the original orientation::

            crop h x w  ->  FLIP_TOP_BOTTOM  ->  rotate 90 deg CCW

    Args:
        atlas: The full atlas PIL Image.
        frame: The sprite frame descriptor.

    Returns:
        The cropped (and optionally un-rotated) sprite Image.
    """
    if frame.rotated:
        # Packed 90° CW in atlas: packed_w = original h, packed_h = original w
        packed_w, packed_h = frame.h, frame.w
        y = atlas.height - frame.y - packed_h
        region = atlas.crop((frame.x, y, frame.x + packed_w, y + packed_h))
        region = region.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        region = region.rotate(90, expand=True)
    else:
        y = atlas.height - frame.y - frame.h
        region = atlas.crop((frame.x, y, frame.x + frame.w, y + frame.h))
        region = region.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return region
