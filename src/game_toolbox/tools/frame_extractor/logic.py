"""Pure frame extraction logic — no GUI imports allowed."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
from PIL import Image

from game_toolbox.core.datatypes import ExtractionResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError

logger = logging.getLogger(__name__)

# ── Supported output formats ──────────────────────────────────────────────

SUPPORTED_FORMATS: dict[str, dict[str, Any]] = {
    "png": {
        "ext": ".png",
        "cv2_params": [cv2.IMWRITE_PNG_COMPRESSION, 6],
    },
    "webp": {
        "ext": ".webp",
        "cv2_params": [cv2.IMWRITE_WEBP_QUALITY, 90],
    },
    "jpg": {
        "ext": ".jpg",
        "cv2_params": [cv2.IMWRITE_JPEG_QUALITY, 92],
    },
    "avif": {
        "ext": ".avif",
        "cv2_params": None,
    },
}

DEFAULT_QUALITY: dict[str, int] = {
    "png": 6,
    "webp": 90,
    "jpg": 92,
    "avif": 75,
}


@dataclass(frozen=True)
class VideoInfo:
    """Metadata extracted from a video file before processing."""

    fps: float
    total_frames: int
    duration_s: float


def probe_video(video_path: Path) -> VideoInfo:
    """Open a video file and read its metadata.

    Args:
        video_path: Path to the input video.

    Returns:
        A ``VideoInfo`` with fps, frame count, and duration.

    Raises:
        ToolError: If the video cannot be opened.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        msg = f"Video '{video_path}' could not be opened"
        raise ToolError(msg)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_s = total_frames / fps if fps > 0 else 0.0
    finally:
        cap.release()
    return VideoInfo(fps=fps, total_frames=total_frames, duration_s=duration_s)


def _build_cv2_params(fmt: str, quality: int | None) -> list[int] | None:
    """Build the OpenCV imwrite parameter list for a given format.

    Args:
        fmt: Output format key (``"png"``, ``"webp"``, ``"jpg"``, ``"avif"``).
        quality: Optional quality override (1-100).

    Returns:
        A list of OpenCV parameters, or ``None`` for AVIF (uses Pillow).
    """
    if fmt == "avif":
        return None

    format_info = SUPPORTED_FORMATS[fmt]
    raw_params = format_info["cv2_params"]
    base_params: list[int] = list(raw_params) if raw_params is not None else []

    if quality is None:
        return base_params

    if fmt == "jpg":
        return [cv2.IMWRITE_JPEG_QUALITY, quality]
    if fmt == "webp":
        return [cv2.IMWRITE_WEBP_QUALITY, quality]
    if fmt == "png":
        compression = min(9, max(0, (100 - quality) // 10))
        return [cv2.IMWRITE_PNG_COMPRESSION, compression]

    return base_params


def _save_frame_avif(frame: Any, filepath: Path, quality: int) -> None:
    """Save a single frame as AVIF via Pillow.

    Args:
        frame: A BGR numpy array from OpenCV.
        filepath: Destination file path.
        quality: AVIF quality (1-100).
    """
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    img.save(str(filepath), format="AVIF", quality=quality)


def extract_frames(
    video_path: Path,
    output_dir: Path,
    *,
    interval_ms: int = 500,
    fmt: str = "webp",
    quality: int | None = None,
    max_frames: int | None = None,
    event_bus: EventBus | None = None,
) -> ExtractionResult:
    """Extract frames from a video at regular time intervals.

    Args:
        video_path: Path to the input video file.
        output_dir: Directory where extracted frames will be saved.
        interval_ms: Time interval between frames in milliseconds.
        fmt: Output image format (``png``, ``webp``, ``jpg``, ``avif``).
        quality: Quality override (1-100).  Uses format default if ``None``.
        max_frames: Stop after this many frames.  ``None`` means extract all.
        event_bus: Optional event bus for progress events.

    Returns:
        An ``ExtractionResult`` with the output directory, count, and paths.

    Raises:
        ToolError: If the video cannot be opened.
        ValidationError: If the format is unsupported.
    """
    if fmt not in SUPPORTED_FORMATS:
        msg = f"Unsupported format '{fmt}'. Choose from: {list(SUPPORTED_FORMATS.keys())}"
        raise ToolError(msg)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        msg = f"Video '{video_path}' could not be opened"
        raise ToolError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)

    ext = SUPPORTED_FORMATS[fmt]["ext"]
    cv2_params = _build_cv2_params(fmt, quality)
    effective_quality = quality if quality is not None else DEFAULT_QUALITY.get(fmt, 75)

    frame_count = 0
    current_ms = 0.0
    saved_paths: list[Path] = []

    try:
        while True:
            if max_frames is not None and frame_count >= max_frames:
                break

            cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
            ret, frame = cap.read()
            if not ret:
                break

            timestamp_s = current_ms / 1000.0
            filename = f"frame_{frame_count:05d}_{timestamp_s:.3f}s{ext}"
            filepath = output_dir / filename

            if fmt == "avif":
                _save_frame_avif(frame, filepath, effective_quality)
            elif cv2_params is not None:
                cv2.imwrite(str(filepath), frame, cv2_params)

            saved_paths.append(filepath)
            frame_count += 1
            current_ms += interval_ms

            if event_bus is not None:
                event_bus.emit(
                    "progress",
                    tool="frame_extractor",
                    current=frame_count,
                    message=f"Extracted {filename}",
                )
    finally:
        cap.release()

    if event_bus is not None:
        event_bus.emit(
            "completed",
            tool="frame_extractor",
            message=f"Done — {frame_count} frames extracted to '{output_dir}'",
        )

    return ExtractionResult(
        output_dir=output_dir,
        frame_count=frame_count,
        paths=tuple(saved_paths),
    )
