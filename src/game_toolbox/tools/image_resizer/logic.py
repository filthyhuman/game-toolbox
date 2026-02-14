"""Pure image resizing logic — no GUI imports allowed."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from game_toolbox.core.datatypes import ImageData, ResizeResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".avif",
        ".bmp",
        ".tiff",
    }
)

RESAMPLE_FILTERS: dict[str, Image.Resampling] = {
    "lanczos": Image.Resampling.LANCZOS,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "nearest": Image.Resampling.NEAREST,
}

VALID_MODES: frozenset[str] = frozenset({"exact", "fit", "fill", "percent"})


# ── Input collection ──────────────────────────────────────────────────────


def collect_image_paths(inputs: list[Path]) -> list[Path]:
    """Collect image file paths from a mix of files and directories.

    Individual files are included directly (if they have a recognised image
    extension).  Directories are scanned non-recursively for image files.

    Args:
        inputs: A list of file and/or directory paths.

    Returns:
        A sorted, deduplicated list of image file paths.

    Raises:
        ToolError: If no image files are found after scanning all inputs.
    """
    found: set[Path] = set()
    for entry in inputs:
        entry = entry.resolve()
        if entry.is_file():
            if entry.suffix.lower() in IMAGE_EXTENSIONS:
                found.add(entry)
        elif entry.is_dir():
            for child in entry.iterdir():
                if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                    found.add(child)

    if not found:
        msg = "No image files found in the provided inputs"
        raise ToolError(msg)

    return sorted(found)


# ── Validation ────────────────────────────────────────────────────────────


def validate_resize_params(
    *,
    mode: str,
    width: int | None,
    height: int | None,
    percent: float | None,
    resample: str,
) -> None:
    """Validate resize parameters before processing.

    Args:
        mode: Resize mode (``exact``, ``fit``, ``fill``, ``percent``).
        width: Target width in pixels.
        height: Target height in pixels.
        percent: Scale percentage (for ``percent`` mode).
        resample: Resampling filter name.

    Raises:
        ValidationError: If parameters are invalid for the chosen mode.
    """
    if mode not in VALID_MODES:
        msg = f"Invalid mode '{mode}'. Choose from: {sorted(VALID_MODES)}"
        raise ValidationError(msg)

    if resample not in RESAMPLE_FILTERS:
        msg = f"Invalid resample filter '{resample}'. Choose from: {sorted(RESAMPLE_FILTERS)}"
        raise ValidationError(msg)

    if mode in {"exact", "fit", "fill"}:
        if width is None or height is None:
            msg = f"Mode '{mode}' requires both --width and --height"
            raise ValidationError(msg)
        if width < 1 or height < 1:
            msg = "Width and height must be at least 1"
            raise ValidationError(msg)

    if mode == "percent":
        if percent is None:
            msg = "Mode 'percent' requires --percent"
            raise ValidationError(msg)
        if not 1 <= percent <= 1000:
            msg = f"Percent must be between 1 and 1000, got {percent}"
            raise ValidationError(msg)


# ── Core resize logic ────────────────────────────────────────────────────


def _resize_exact(img: Image.Image, width: int, height: int, resample: Image.Resampling) -> Image.Image:
    """Resize to exact dimensions, ignoring aspect ratio."""
    return img.resize((width, height), resample=resample)


def _resize_fit(img: Image.Image, width: int, height: int, resample: Image.Resampling) -> Image.Image:
    """Resize to fit within the box, preserving aspect ratio."""
    img_copy = img.copy()
    img_copy.thumbnail((width, height), resample=resample)
    return img_copy


def _resize_fill(img: Image.Image, width: int, height: int, resample: Image.Resampling) -> Image.Image:
    """Resize to fill the box, cropping excess from center."""
    src_w, src_h = img.size
    scale = max(width / src_w, height / src_h)
    new_w = round(src_w * scale)
    new_h = round(src_h * scale)

    resized = img.resize((new_w, new_h), resample=resample)

    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _resize_percent(img: Image.Image, percent: float, resample: Image.Resampling) -> Image.Image:
    """Resize by a percentage factor."""
    factor = percent / 100.0
    new_w = max(1, round(img.width * factor))
    new_h = max(1, round(img.height * factor))
    return img.resize((new_w, new_h), resample=resample)


def resize_image(
    input_path: Path,
    output_path: Path,
    *,
    mode: str,
    width: int | None = None,
    height: int | None = None,
    percent: float | None = None,
    resample: str = "lanczos",
    event_bus: EventBus | None = None,
) -> ImageData:
    """Resize a single image file.

    Args:
        input_path: Path to the source image.
        output_path: Path where the resized image will be saved.
        mode: Resize mode (``exact``, ``fit``, ``fill``, ``percent``).
        width: Target width (required for exact/fit/fill).
        height: Target height (required for exact/fit/fill).
        percent: Scale percentage (required for percent mode).
        resample: Resampling filter name.
        event_bus: Optional event bus for progress events.

    Returns:
        An ``ImageData`` with the output path and dimensions.

    Raises:
        ToolError: If the image cannot be opened or saved.
        ValidationError: If parameters are invalid.
    """
    validate_resize_params(mode=mode, width=width, height=height, percent=percent, resample=resample)
    resample_filter = RESAMPLE_FILTERS[resample]

    try:
        img = Image.open(input_path)
    except Exception as exc:
        msg = f"Image '{input_path}' could not be opened"
        raise ToolError(msg) from exc

    match mode:
        case "exact":
            assert width is not None and height is not None
            result_img = _resize_exact(img, width, height, resample_filter)
        case "fit":
            assert width is not None and height is not None
            result_img = _resize_fit(img, width, height, resample_filter)
        case "fill":
            assert width is not None and height is not None
            result_img = _resize_fill(img, width, height, resample_filter)
        case "percent":
            assert percent is not None
            result_img = _resize_percent(img, percent, resample_filter)
        case _:  # pragma: no cover
            msg = f"Unknown mode '{mode}'"
            raise ToolError(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result_img.save(str(output_path))
    except Exception as exc:
        msg = f"Failed to save resized image to '{output_path}'"
        raise ToolError(msg) from exc

    fmt = output_path.suffix.lstrip(".").lower()

    return ImageData(
        path=output_path,
        width=result_img.width,
        height=result_img.height,
        format=fmt,
    )


def resize_batch(
    input_paths: list[Path],
    output_dir: Path | None,
    *,
    mode: str,
    width: int | None = None,
    height: int | None = None,
    percent: float | None = None,
    resample: str = "lanczos",
    event_bus: EventBus | None = None,
) -> ResizeResult:
    """Resize a batch of images.

    When ``output_dir`` is ``None`` the images are resized in-place,
    overwriting the originals.

    Args:
        input_paths: List of image file paths to resize.
        output_dir: Directory for resized images, or ``None`` for in-place.
        mode: Resize mode.
        width: Target width (for exact/fit/fill).
        height: Target height (for exact/fit/fill).
        percent: Scale percentage (for percent mode).
        resample: Resampling filter name.
        event_bus: Optional event bus for progress events.

    Returns:
        A ``ResizeResult`` summarising the operation.
    """
    validate_resize_params(mode=mode, width=width, height=height, percent=percent, resample=resample)

    results: list[ImageData] = []
    total = len(input_paths)

    for idx, input_path in enumerate(input_paths):
        out_path = output_dir / input_path.name if output_dir is not None else input_path

        image_data = resize_image(
            input_path,
            out_path,
            mode=mode,
            width=width,
            height=height,
            percent=percent,
            resample=resample,
        )
        results.append(image_data)

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="image_resizer",
                current=idx + 1,
                total=total,
                message=f"Resized {input_path.name} ({idx + 1}/{total})",
            )

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="image_resizer",
            message=f"Done — {len(results)} images resized",
        )

    return ResizeResult(
        images=tuple(results),
        count=len(results),
        in_place=output_dir is None,
    )
