"""Pure animation cropping logic — no GUI imports allowed."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from game_toolbox.core.datatypes import CropResult, ImageData
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError

logger = logging.getLogger(__name__)

# ── Bounding box analysis ────────────────────────────────────────────────


def analyze_bounding_box(image_path: Path) -> tuple[int, int, int, int]:
    """Compute the bounding box of non-transparent content in an RGBA image.

    The image is opened and converted to RGBA.  Rows and columns with any
    non-zero alpha are identified to derive the tightest axis-aligned
    bounding box.

    Args:
        image_path: Path to an image file.

    Returns:
        A tuple ``(x, y, width, height)`` of the bounding box.  Returns
        ``(0, 0, 0, 0)`` for fully transparent images.

    Raises:
        ToolError: If the image cannot be opened.
    """
    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as exc:
        msg = f"Image '{image_path}' could not be opened"
        raise ToolError(msg) from exc

    alpha = np.array(img)[:, :, 3]

    rows_with_content = np.any(alpha > 0, axis=1)
    cols_with_content = np.any(alpha > 0, axis=0)

    if not np.any(rows_with_content):
        return (0, 0, 0, 0)

    row_indices = np.where(rows_with_content)[0]
    col_indices = np.where(cols_with_content)[0]

    y_min = int(row_indices[0])
    y_max = int(row_indices[-1])
    x_min = int(col_indices[0])
    x_max = int(col_indices[-1])

    return (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)


def compute_union_bbox(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    """Compute the union bounding box of multiple bounding boxes.

    Empty bounding boxes ``(0, 0, 0, 0)`` are skipped.

    Args:
        bboxes: List of ``(x, y, width, height)`` tuples.

    Returns:
        The union ``(x, y, width, height)``.  Returns ``(0, 0, 0, 0)`` if
        all inputs are empty or the list is empty.
    """
    non_empty = [(x, y, w, h) for x, y, w, h in bboxes if w > 0 and h > 0]
    if not non_empty:
        return (0, 0, 0, 0)

    x_min = min(x for x, _y, _w, _h in non_empty)
    y_min = min(y for _x, y, _w, _h in non_empty)
    x_max = max(x + w for x, _y, w, _h in non_empty)
    y_max = max(y + h for _x, y, _w, h in non_empty)

    return (x_min, y_min, x_max - x_min, y_max - y_min)


def _suggest_size(union_w: int, union_h: int) -> tuple[int, int]:
    """Round up the union bounding box to the next power-of-two-friendly size.

    Uses the smallest multiple of 2 that is ≥ the dimension (capped at
    rounding up to the next even number for small values).

    Args:
        union_w: Union bounding box width.
        union_h: Union bounding box height.

    Returns:
        A ``(width, height)`` tuple with suggested crop dimensions.
    """
    if union_w == 0 or union_h == 0:
        return (0, 0)

    def _next_power_of_two(n: int) -> int:
        if n <= 0:
            return 1
        return 1 << (n - 1).bit_length()

    return (_next_power_of_two(union_w), _next_power_of_two(union_h))


# ── Crop operations ──────────────────────────────────────────────────────


def crop_frame(
    image_path: Path,
    output_path: Path,
    width: int,
    height: int,
    output_format: str = "png",
) -> ImageData:
    """Center-crop a single frame to the given dimensions.

    The crop region is centred on the image centre.  If the crop window
    exceeds the source dimensions, the source is pasted onto a transparent
    canvas of the target size.

    Args:
        image_path: Path to the source image.
        output_path: Path where the cropped image will be saved.
        width: Target crop width in pixels.
        height: Target crop height in pixels.
        output_format: Output format (``"png"`` or ``"webp"``).

    Returns:
        An ``ImageData`` with the output path and dimensions.

    Raises:
        ToolError: If the image cannot be opened or saved.
    """
    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as exc:
        msg = f"Image '{image_path}' could not be opened"
        raise ToolError(msg) from exc

    src_w, src_h = img.size

    # Centre of the source image.
    cx, cy = src_w / 2, src_h / 2

    # Crop box relative to source (may extend outside).
    left = cx - width / 2
    top = cy - height / 2

    # Create transparent canvas at target size.
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # Compute where to paste the source onto the canvas.
    paste_x = int(max(0, -left))
    paste_y = int(max(0, -top))

    # Compute the crop region within the source.
    src_left = int(max(0, left))
    src_top = int(max(0, top))
    src_right = int(min(src_w, left + width))
    src_bottom = int(min(src_h, top + height))

    if src_right > src_left and src_bottom > src_top:
        cropped = img.crop((src_left, src_top, src_right, src_bottom))
        canvas.paste(cropped, (paste_x, paste_y))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        canvas.save(str(output_path), format=output_format.upper())
    except Exception as exc:
        msg = f"Failed to save cropped image to '{output_path}'"
        raise ToolError(msg) from exc

    fmt = output_path.suffix.lstrip(".").lower()
    return ImageData(path=output_path, width=width, height=height, format=fmt)


# ── Batch operations ─────────────────────────────────────────────────────


def analyze_only(
    input_paths: list[Path],
    event_bus: EventBus | None = None,
) -> CropResult:
    """Analyse all frames and return the suggested crop size without writing files.

    Args:
        input_paths: List of image file paths to analyse.
        event_bus: Optional event bus for progress events.

    Returns:
        A ``CropResult`` with zero images and the suggested dimensions.
    """
    bboxes: list[tuple[int, int, int, int]] = []
    total = len(input_paths)

    for idx, path in enumerate(input_paths):
        bbox = analyze_bounding_box(path)
        bboxes.append(bbox)

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="animation_cropper",
                current=idx + 1,
                total=total,
                message=f"Analysed {path.name} ({idx + 1}/{total})",
            )

    union = compute_union_bbox(bboxes)
    suggested_w, suggested_h = _suggest_size(union[2], union[3])

    if event_bus is not None:
        event_bus.emit(
            "log",
            tool="animation_cropper",
            message=(
                f"Union bounding box: {union[2]}x{union[3]} at ({union[0]}, {union[1]}). "
                f"Suggested crop size: {suggested_w}x{suggested_h}"
            ),
        )
        event_bus.emit(
            "completed",
            tool="animation_cropper",
            message=f"Analysis complete — suggested size: {suggested_w}x{suggested_h}",
        )

    return CropResult(
        images=(),
        count=0,
        suggested_width=suggested_w,
        suggested_height=suggested_h,
    )


def crop_batch(
    input_paths: list[Path],
    output_dir: Path,
    width: int,
    height: int,
    output_format: str = "png",
    event_bus: EventBus | None = None,
) -> CropResult:
    """Analyse all frames for the suggested size, then centre-crop them all.

    This is a two-pass operation: first all frames are analysed to compute
    the union bounding box and suggested size, then each frame is cropped.

    Args:
        input_paths: List of image file paths to process.
        output_dir: Directory for cropped images.
        width: Target crop width.
        height: Target crop height.
        output_format: Output format (``"png"`` or ``"webp"``).
        event_bus: Optional event bus for progress events.

    Returns:
        A ``CropResult`` with cropped image metadata and suggested size.
    """
    # Pass 1: analyse.
    bboxes: list[tuple[int, int, int, int]] = []
    total = len(input_paths)

    for idx, path in enumerate(input_paths):
        bbox = analyze_bounding_box(path)
        bboxes.append(bbox)

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="animation_cropper",
                current=idx + 1,
                total=total * 2,
                message=f"Analysing {path.name} ({idx + 1}/{total})",
            )

    union = compute_union_bbox(bboxes)
    suggested_w, suggested_h = _suggest_size(union[2], union[3])

    if event_bus is not None:
        event_bus.emit(
            "log",
            tool="animation_cropper",
            message=(
                f"Union bounding box: {union[2]}x{union[3]} at ({union[0]}, {union[1]}). "
                f"Suggested crop size: {suggested_w}x{suggested_h}. "
                f"Cropping to {width}x{height}."
            ),
        )

    # Pass 2: crop.
    results: list[ImageData] = []
    for idx, path in enumerate(input_paths):
        out_name = f"{path.stem}.{output_format}"
        out_path = output_dir / out_name

        image_data = crop_frame(path, out_path, width, height, output_format)
        results.append(image_data)

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="animation_cropper",
                current=total + idx + 1,
                total=total * 2,
                message=f"Cropped {path.name} ({idx + 1}/{total})",
            )

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="animation_cropper",
            message=f"Done — {len(results)} frames cropped to {width}x{height}",
        )

    return CropResult(
        images=tuple(results),
        count=len(results),
        suggested_width=suggested_w,
        suggested_height=suggested_h,
    )
