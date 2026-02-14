"""Pure sprite sheet generation logic — no GUI imports allowed."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from PIL import Image

from game_toolbox.core.datatypes import ImageData, SpriteFrame, SpriteSheetResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

VALID_METADATA_FORMATS: frozenset[str] = frozenset({"json", "css", "xml"})


# ── Validation ────────────────────────────────────────────────────────────


def validate_sprite_params(
    *,
    columns: int | None,
    padding: int,
    metadata_format: str,
    input_count: int,
) -> None:
    """Validate sprite sheet parameters before processing.

    Args:
        columns: Number of columns (``None`` for auto).
        padding: Pixel padding between frames.
        metadata_format: Metadata output format.
        input_count: Number of input images.

    Raises:
        ValidationError: If any parameter is out of range or unsupported.
    """
    if input_count < 1:
        msg = "At least 1 input image is required"
        raise ValidationError(msg)

    if columns is not None and columns < 1:
        msg = f"Columns must be >= 1, got {columns}"
        raise ValidationError(msg)

    if padding < 0:
        msg = f"Padding must be >= 0, got {padding}"
        raise ValidationError(msg)

    if metadata_format not in VALID_METADATA_FORMATS:
        msg = f"Metadata format must be one of {sorted(VALID_METADATA_FORMATS)}, got '{metadata_format}'"
        raise ValidationError(msg)


# ── Metadata generation ──────────────────────────────────────────────────


def _generate_json_metadata(
    sheet_path: Path,
    frames: list[SpriteFrame],
    columns: int,
    rows: int,
    padding: int,
) -> str:
    """Generate JSON metadata for the sprite sheet.

    Args:
        sheet_path: Path to the sprite sheet image.
        frames: List of frame definitions.
        columns: Number of columns in the grid.
        rows: Number of rows in the grid.
        padding: Pixel padding between frames.

    Returns:
        A JSON string with sprite sheet metadata.
    """
    data = {
        "sprite_sheet": sheet_path.name,
        "columns": columns,
        "rows": rows,
        "padding": padding,
        "frames": [
            {
                "name": f.name,
                "x": f.x,
                "y": f.y,
                "width": f.width,
                "height": f.height,
            }
            for f in frames
        ],
    }
    return json.dumps(data, indent=2)


def _generate_css_metadata(
    sheet_path: Path,
    frames: list[SpriteFrame],
) -> str:
    """Generate CSS metadata for the sprite sheet.

    Args:
        sheet_path: Path to the sprite sheet image.
        frames: List of frame definitions.

    Returns:
        A CSS string with sprite classes.
    """
    lines = [f".sprite {{ background-image: url('{sheet_path.name}'); }}"]
    for f in frames:
        lines.append(
            f".sprite.{f.name} {{ background-position: -{f.x}px -{f.y}px; width: {f.width}px; height: {f.height}px; }}"
        )
    return "\n".join(lines)


def _generate_xml_metadata(
    sheet_path: Path,
    frames: list[SpriteFrame],
    columns: int,
    rows: int,
) -> str:
    """Generate XML metadata for the sprite sheet.

    Args:
        sheet_path: Path to the sprite sheet image.
        frames: List of frame definitions.
        columns: Number of columns in the grid.
        rows: Number of rows in the grid.

    Returns:
        An XML string with sprite sheet metadata.
    """
    root = Element("sprite_sheet")
    root.set("image", sheet_path.name)
    root.set("columns", str(columns))
    root.set("rows", str(rows))

    for f in frames:
        frame_el = SubElement(root, "frame")
        frame_el.set("name", f.name)
        frame_el.set("x", str(f.x))
        frame_el.set("y", str(f.y))
        frame_el.set("width", str(f.width))
        frame_el.set("height", str(f.height))

    return tostring(root, encoding="unicode")


def _write_metadata(
    sheet_path: Path,
    frames: list[SpriteFrame],
    columns: int,
    rows: int,
    padding: int,
    metadata_format: str,
) -> Path:
    """Write metadata file next to the sprite sheet.

    Args:
        sheet_path: Path to the sprite sheet image.
        frames: List of frame definitions.
        columns: Number of columns.
        rows: Number of rows.
        padding: Pixel padding.
        metadata_format: Output format (json, css, xml).

    Returns:
        Path to the written metadata file.
    """
    meta_path = sheet_path.with_suffix(f".{metadata_format}")

    match metadata_format:
        case "json":
            content = _generate_json_metadata(sheet_path, frames, columns, rows, padding)
        case "css":
            content = _generate_css_metadata(sheet_path, frames)
        case "xml":
            content = _generate_xml_metadata(sheet_path, frames, columns, rows)
        case _:  # pragma: no cover
            msg = f"Unsupported metadata format: {metadata_format}"
            raise ToolError(msg)

    meta_path.write_text(content, encoding="utf-8")
    return meta_path


# ── Core logic ────────────────────────────────────────────────────────────


def generate_sprite_sheet(
    input_paths: list[Path],
    output_path: Path,
    *,
    columns: int | None = None,
    padding: int = 1,
    metadata_format: str = "json",
    event_bus: EventBus | None = None,
) -> SpriteSheetResult:
    """Pack multiple images into a single sprite sheet atlas.

    Images are laid out in a grid.  If *columns* is ``None``, the number of
    columns is chosen automatically as ``ceil(sqrt(n))``.

    Args:
        input_paths: List of image file paths to pack.
        output_path: Path where the sprite sheet image will be saved.
        columns: Number of columns in the grid (``None`` for auto).
        padding: Pixel padding between frames.
        metadata_format: Metadata output format (json, css, xml).
        event_bus: Optional event bus for progress events.

    Returns:
        A ``SpriteSheetResult`` with sheet metadata and frame positions.

    Raises:
        ToolError: If any image cannot be opened or the sheet cannot be saved.
        ValidationError: If parameters are invalid.
    """
    validate_sprite_params(
        columns=columns,
        padding=padding,
        metadata_format=metadata_format,
        input_count=len(input_paths),
    )

    # Load all images and record dimensions.
    images: list[Image.Image] = []
    for img_path in input_paths:
        try:
            img = Image.open(img_path).convert("RGBA")
            images.append(img)
        except Exception as exc:
            msg = f"Image '{img_path}' could not be opened"
            raise ToolError(msg) from exc

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="sprite_sheet",
                current=len(images),
                total=len(input_paths),
                message=f"Loaded {img_path.name} ({len(images)}/{len(input_paths)})",
            )

    n = len(images)
    cols = columns if columns is not None else math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    # Find maximum frame dimensions.
    max_w = max(img.width for img in images)
    max_h = max(img.height for img in images)

    canvas_w = cols * max_w + (cols - 1) * padding
    canvas_h = rows * max_h + (rows - 1) * padding
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    frames: list[SpriteFrame] = []

    for idx, img in enumerate(images):
        col = idx % cols
        row = idx // cols
        x = col * (max_w + padding)
        y = row * (max_h + padding)

        canvas.paste(img, (x, y), img)

        stem = input_paths[idx].stem
        frames.append(SpriteFrame(name=stem, x=x, y=y, width=img.width, height=img.height))

    # Save the sprite sheet.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        canvas.save(str(output_path))
    except Exception as exc:
        msg = f"Failed to save sprite sheet to '{output_path}'"
        raise ToolError(msg) from exc

    # Write metadata.
    meta_path = _write_metadata(output_path, frames, cols, rows, padding, metadata_format)

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="sprite_sheet",
            message=f"Done — {n} frames packed into {cols}x{rows} sheet",
        )

    fmt = output_path.suffix.lstrip(".").lower()

    return SpriteSheetResult(
        sheet=ImageData(path=output_path, width=canvas_w, height=canvas_h, format=fmt),
        frames=tuple(frames),
        columns=cols,
        rows=rows,
        padding=padding,
        metadata_path=meta_path,
    )
