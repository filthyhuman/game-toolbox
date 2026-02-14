"""Pure chroma key removal logic — no GUI imports allowed."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from game_toolbox.core.datatypes import ChromaKeyResult, ImageData
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

COLOR_PRESETS: dict[str, tuple[int, int, int]] = {
    "green": (0, 177, 64),
    "blue": (0, 71, 187),
    "magenta": (255, 0, 255),
}

ALPHA_FORMATS: frozenset[str] = frozenset({"png", "webp"})


# ── Validation ────────────────────────────────────────────────────────────


def validate_chroma_params(
    *,
    color: tuple[int, int, int],
    tolerance: float,
    softness: float,
    output_format: str,
) -> None:
    """Validate chroma key parameters before processing.

    Args:
        color: Target RGB colour to remove.
        tolerance: Euclidean distance threshold (0-255).
        softness: Width of the soft-edge transition band.
        output_format: Output image format (must support alpha).

    Raises:
        ValidationError: If any parameter is out of range or unsupported.
    """
    for i, channel in enumerate(color):
        if not 0 <= channel <= 255:
            msg = f"Colour channel {i} must be 0-255, got {channel}"
            raise ValidationError(msg)

    if not 0 <= tolerance <= 255:
        msg = f"Tolerance must be between 0 and 255, got {tolerance}"
        raise ValidationError(msg)

    if softness < 0:
        msg = f"Softness must be >= 0, got {softness}"
        raise ValidationError(msg)

    if output_format not in ALPHA_FORMATS:
        msg = f"Output format must support alpha ({sorted(ALPHA_FORMATS)}), got '{output_format}'"
        raise ValidationError(msg)


# ── Core logic ────────────────────────────────────────────────────────────


def remove_chroma_key(
    input_path: Path,
    output_path: Path,
    *,
    color: tuple[int, int, int],
    tolerance: float = 30.0,
    softness: float = 10.0,
    event_bus: EventBus | None = None,
) -> ImageData:
    """Remove a chroma key colour from a single image.

    Pixels whose Euclidean RGB distance to *color* is within *tolerance*
    become fully transparent.  Pixels in the transition band between
    *tolerance* and *tolerance + softness* receive proportional alpha.

    Args:
        input_path: Path to the source image.
        output_path: Path where the keyed image will be saved.
        color: Target RGB colour to remove.
        tolerance: Euclidean distance threshold for full transparency.
        softness: Width of the soft-edge transition band.
        event_bus: Optional event bus for progress events.

    Returns:
        An ``ImageData`` with the output path and dimensions.

    Raises:
        ToolError: If the image cannot be opened or saved.
    """
    try:
        img = Image.open(input_path).convert("RGBA")
    except Exception as exc:
        msg = f"Image '{input_path}' could not be opened"
        raise ToolError(msg) from exc

    pixels = np.array(img, dtype=np.float64)
    rgb = pixels[:, :, :3]

    target = np.array(color, dtype=np.float64)
    distance = np.sqrt(np.sum((rgb - target) ** 2, axis=2))

    # Build alpha channel based on distance.
    if softness > 0:
        alpha = np.clip((distance - tolerance) / softness, 0.0, 1.0)
    else:
        alpha = np.where(distance <= tolerance, 0.0, 1.0)

    pixels[:, :, 3] = alpha * 255.0
    result_img = Image.fromarray(pixels.astype(np.uint8), "RGBA")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result_img.save(str(output_path))
    except Exception as exc:
        msg = f"Failed to save keyed image to '{output_path}'"
        raise ToolError(msg) from exc

    fmt = output_path.suffix.lstrip(".").lower()

    return ImageData(
        path=output_path,
        width=result_img.width,
        height=result_img.height,
        format=fmt,
    )


def chroma_key_batch(
    input_paths: list[Path],
    output_dir: Path | None,
    *,
    color: tuple[int, int, int],
    tolerance: float = 30.0,
    softness: float = 10.0,
    output_format: str = "png",
    event_bus: EventBus | None = None,
) -> ChromaKeyResult:
    """Remove chroma key from a batch of images.

    When *output_dir* is ``None`` the images are processed in-place,
    overwriting the originals.

    Args:
        input_paths: List of image file paths to process.
        output_dir: Directory for keyed images, or ``None`` for in-place.
        color: Target RGB colour to remove.
        tolerance: Euclidean distance threshold.
        softness: Width of the soft-edge transition band.
        output_format: Output image format (must support alpha).
        event_bus: Optional event bus for progress events.

    Returns:
        A ``ChromaKeyResult`` summarising the operation.
    """
    validate_chroma_params(color=color, tolerance=tolerance, softness=softness, output_format=output_format)

    results: list[ImageData] = []
    total = len(input_paths)

    for idx, input_path in enumerate(input_paths):
        if output_dir is not None:
            stem = input_path.stem
            out_path = output_dir / f"{stem}.{output_format}"
        else:
            out_path = input_path.with_suffix(f".{output_format}")

        image_data = remove_chroma_key(
            input_path,
            out_path,
            color=color,
            tolerance=tolerance,
            softness=softness,
        )
        results.append(image_data)

        if event_bus is not None:
            event_bus.emit(
                "progress",
                tool="chroma_key",
                current=idx + 1,
                total=total,
                message=f"Keyed {input_path.name} ({idx + 1}/{total})",
            )

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="chroma_key",
            message=f"Done — {len(results)} images keyed",
        )

    return ChromaKeyResult(
        images=tuple(results),
        count=len(results),
        in_place=output_dir is None,
    )
