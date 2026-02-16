"""Pure sprite extraction logic — no GUI imports allowed."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from game_toolbox.core.datatypes import ImageData, SpriteExtractionResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

VALID_OUTPUT_FORMATS: frozenset[str] = frozenset({"png", "webp", "bmp", "tiff"})


# ── Helpers ───────────────────────────────────────────────────────────────


def _format_index(index: int, total: int) -> str:
    """Return a zero-padded 1-based index string.

    Uses 2 digits when *total* < 100, 3 digits otherwise.

    Args:
        index: Zero-based index.
        total: Total number of items (determines padding width).

    Returns:
        A zero-padded string representing the 1-based index.
    """
    width = 3 if total >= 100 else 2
    return str(index + 1).zfill(width)


def _extract_and_save(
    sheet: Image.Image,
    region: tuple[int, int, int, int],
    output_path: Path,
    output_format: str,
) -> ImageData:
    """Crop a region from a sprite sheet and save it to disk.

    Args:
        sheet: The source sprite sheet PIL Image (RGBA).
        region: ``(x, y, width, height)`` rectangle to extract.
        output_path: Destination file path.
        output_format: Image format string (e.g. ``"png"``).

    Returns:
        An ``ImageData`` describing the saved sprite.

    Raises:
        ToolError: If the region extends outside the sheet bounds or saving fails.
    """
    x, y, w, h = region
    if x < 0 or y < 0 or x + w > sheet.width or y + h > sheet.height:
        msg = f"Region ({x}, {y}, {w}, {h}) extends outside sheet bounds ({sheet.width}x{sheet.height})"
        raise ToolError(msg)

    cropped = sheet.crop((x, y, x + w, y + h))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        cropped.save(str(output_path))
    except Exception as exc:
        msg = f"Failed to save sprite to '{output_path}'"
        raise ToolError(msg) from exc

    return ImageData(path=output_path, width=w, height=h, format=output_format)


# ── Validation ────────────────────────────────────────────────────────────


def validate_extraction_params(
    *,
    mode: str,
    output_format: str,
    frame_width: int | None = None,
    frame_height: int | None = None,
    columns: int | None = None,
    rows: int | None = None,
    metadata_path: Path | None = None,
) -> None:
    """Validate sprite extraction parameters before processing.

    Args:
        mode: Extraction mode (``"grid"``, ``"auto"``, ``"metadata"``).
        output_format: Output image format.
        frame_width: Frame width for grid mode.
        frame_height: Frame height for grid mode.
        columns: Column count for grid mode.
        rows: Row count for grid mode.
        metadata_path: Metadata file path for metadata mode.

    Raises:
        ValidationError: If parameters are invalid for the chosen mode.
    """
    valid_modes = {"grid", "auto", "metadata"}
    if mode not in valid_modes:
        msg = f"Mode must be one of {sorted(valid_modes)}, got '{mode}'"
        raise ValidationError(msg)

    if output_format not in VALID_OUTPUT_FORMATS:
        msg = f"Output format must be one of {sorted(VALID_OUTPUT_FORMATS)}, got '{output_format}'"
        raise ValidationError(msg)

    if mode == "grid":
        # Reject partial pairs first.
        if (frame_width is not None) != (frame_height is not None):
            msg = "Both frame_width and frame_height must be provided together"
            raise ValidationError(msg)
        if (columns is not None) != (rows is not None):
            msg = "Both columns and rows must be provided together"
            raise ValidationError(msg)

        has_frame_size = frame_width is not None and frame_height is not None
        has_grid_dims = columns is not None and rows is not None

        if has_frame_size and has_grid_dims:
            msg = "Grid mode requires either (frame_width + frame_height) or (columns + rows), not both"
            raise ValidationError(msg)
        if not has_frame_size and not has_grid_dims:
            msg = "Grid mode requires either (frame_width + frame_height) or (columns + rows)"
            raise ValidationError(msg)

    if mode == "metadata" and metadata_path is None:
        msg = "Metadata mode requires a metadata_path"
        raise ValidationError(msg)


# ── Core extraction functions ─────────────────────────────────────────────


def extract_grid(
    sheet_path: Path,
    output_dir: Path,
    base_name: str,
    *,
    frame_width: int | None = None,
    frame_height: int | None = None,
    columns: int | None = None,
    rows: int | None = None,
    output_format: str = "png",
    event_bus: EventBus | None = None,
) -> SpriteExtractionResult:
    """Extract sprites from a sheet using a regular grid layout.

    Provide either ``(frame_width, frame_height)`` to specify the cell size
    directly, or ``(columns, rows)`` to compute cell size from sheet dimensions.

    Args:
        sheet_path: Path to the sprite sheet image.
        output_dir: Directory to write extracted sprites.
        base_name: Base filename for output sprites.
        frame_width: Width of each grid cell in pixels.
        frame_height: Height of each grid cell in pixels.
        columns: Number of columns in the grid.
        rows: Number of rows in the grid.
        output_format: Output image format.
        event_bus: Optional event bus for progress reporting.

    Returns:
        A ``SpriteExtractionResult`` with extracted sprite metadata.

    Raises:
        ToolError: If the image cannot be opened.
    """
    try:
        sheet = Image.open(sheet_path).convert("RGBA")
    except Exception as exc:
        msg = f"Image '{sheet_path}' could not be opened"
        raise ToolError(msg) from exc

    if columns is not None and rows is not None:
        fw = sheet.width // columns
        fh = sheet.height // rows
        cols = columns
        rws = rows
    else:
        assert frame_width is not None and frame_height is not None
        fw = frame_width
        fh = frame_height
        cols = sheet.width // fw
        rws = sheet.height // fh

    total = cols * rws
    images: list[ImageData] = []

    for idx in range(total):
        col = idx % cols
        row = idx // cols
        x = col * fw
        y = row * fh

        padded = _format_index(idx, total)
        out_path = output_dir / f"{base_name}_{padded}.{output_format}"
        img_data = _extract_and_save(sheet, (x, y, fw, fh), out_path, output_format)
        images.append(img_data)

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="sprite_extractor",
                current=idx + 1,
                total=total,
                message=f"Extracted sprite {idx + 1}/{total}",
            )

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="sprite_extractor",
            message=f"Done — {total} sprites extracted from {cols}x{rws} grid",
        )

    return SpriteExtractionResult(
        output_dir=output_dir,
        images=tuple(images),
        count=len(images),
    )


def extract_from_metadata(
    sheet_path: Path,
    metadata_path: Path,
    output_dir: Path,
    base_name: str,
    *,
    output_format: str = "png",
    event_bus: EventBus | None = None,
) -> SpriteExtractionResult:
    """Extract sprites using metadata from the sprite_sheet tool.

    The metadata JSON must contain a ``"frames"`` key with a list of objects,
    each having ``"x"``, ``"y"``, ``"width"``, and ``"height"`` fields.

    Args:
        sheet_path: Path to the sprite sheet image.
        metadata_path: Path to the JSON metadata file.
        output_dir: Directory to write extracted sprites.
        base_name: Base filename for output sprites.
        output_format: Output image format.
        event_bus: Optional event bus for progress reporting.

    Returns:
        A ``SpriteExtractionResult`` with extracted sprite metadata.

    Raises:
        ToolError: If the image or metadata cannot be read, or if the
            metadata structure is invalid.
    """
    try:
        sheet = Image.open(sheet_path).convert("RGBA")
    except Exception as exc:
        msg = f"Image '{sheet_path}' could not be opened"
        raise ToolError(msg) from exc

    try:
        raw = metadata_path.read_text(encoding="utf-8")
        meta: dict[str, Any] = json.loads(raw)
    except Exception as exc:
        msg = f"Metadata file '{metadata_path}' could not be read as JSON"
        raise ToolError(msg) from exc

    if "frames" not in meta:
        msg = f"Metadata file '{metadata_path}' is missing the 'frames' key"
        raise ToolError(msg)

    frames: list[dict[str, Any]] = meta["frames"]
    total = len(frames)
    images: list[ImageData] = []

    for idx, frame in enumerate(frames):
        x = int(frame["x"])
        y = int(frame["y"])
        w = int(frame["width"])
        h = int(frame["height"])

        padded = _format_index(idx, total)
        name = frame.get("name", f"{base_name}_{padded}")
        out_path = output_dir / f"{name}.{output_format}"

        img_data = _extract_and_save(sheet, (x, y, w, h), out_path, output_format)
        images.append(img_data)

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="sprite_extractor",
                current=idx + 1,
                total=total,
                message=f"Extracted sprite {idx + 1}/{total}",
            )

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="sprite_extractor",
            message=f"Done — {total} sprites extracted from metadata",
        )

    return SpriteExtractionResult(
        output_dir=output_dir,
        images=tuple(images),
        count=len(images),
    )


def extract_auto_detect(
    sheet_path: Path,
    output_dir: Path,
    base_name: str,
    *,
    output_format: str = "png",
    min_area: int = 16,
    event_bus: EventBus | None = None,
) -> SpriteExtractionResult:
    """Auto-detect and extract sprites using alpha-based connected components.

    Uses OpenCV ``connectedComponents`` on a binary alpha mask to identify
    individual sprites. Regions smaller than *min_area* pixels are filtered
    out as noise. Results are sorted top-to-bottom, left-to-right.

    Args:
        sheet_path: Path to the sprite sheet image.
        output_dir: Directory to write extracted sprites.
        base_name: Base filename for output sprites.
        output_format: Output image format.
        min_area: Minimum bounding-box area to keep (filters noise).
        event_bus: Optional event bus for progress reporting.

    Returns:
        A ``SpriteExtractionResult`` with extracted sprite metadata.

    Raises:
        ToolError: If the image cannot be opened.
    """
    try:
        sheet = Image.open(sheet_path).convert("RGBA")
    except Exception as exc:
        msg = f"Image '{sheet_path}' could not be opened"
        raise ToolError(msg) from exc

    alpha = np.array(sheet)[:, :, 3]
    mask = (alpha > 0).astype(np.uint8)

    num_labels, labels = cv2.connectedComponents(mask)

    # Compute bounding boxes for each labelled region (skip label 0 = background).
    regions: list[tuple[int, int, int, int]] = []
    for label_id in range(1, num_labels):
        ys, xs = np.where(labels == label_id)
        x_min = int(xs.min())
        x_max = int(xs.max())
        y_min = int(ys.min())
        y_max = int(ys.max())
        w = x_max - x_min + 1
        h = y_max - y_min + 1
        if w * h >= min_area:
            regions.append((x_min, y_min, w, h))

    # Sort top-to-bottom, left-to-right using median height as row threshold.
    if regions:
        heights = [r[3] for r in regions]
        median_h = sorted(heights)[len(heights) // 2]
        regions.sort(key=lambda r: (r[1] // max(median_h, 1), r[0]))

    total = len(regions)
    images: list[ImageData] = []

    for idx, region in enumerate(regions):
        padded = _format_index(idx, total)
        out_path = output_dir / f"{base_name}_{padded}.{output_format}"
        img_data = _extract_and_save(sheet, region, out_path, output_format)
        images.append(img_data)

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="sprite_extractor",
                current=idx + 1,
                total=total,
                message=f"Extracted sprite {idx + 1}/{total}",
            )

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="sprite_extractor",
            message=f"Done — {total} sprites auto-detected and extracted",
        )

    return SpriteExtractionResult(
        output_dir=output_dir,
        images=tuple(images),
        count=len(images),
    )
