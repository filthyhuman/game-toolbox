"""Shared value objects used across tools and pipelines."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PathList:
    """An immutable list of filesystem paths produced or consumed by tools."""

    paths: tuple[Path, ...]

    @property
    def count(self) -> int:
        """Return the number of paths in the list."""
        return len(self.paths)


@dataclass(frozen=True)
class ImageData:
    """Reference to an image file with metadata."""

    path: Path
    width: int
    height: int
    format: str


@dataclass(frozen=True)
class VideoData:
    """Reference to a video file with metadata."""

    path: Path
    fps: float
    frame_count: int
    duration_s: float


@dataclass(frozen=True)
class ExtractionResult:
    """Result of a frame extraction operation."""

    output_dir: Path
    frame_count: int
    paths: tuple[Path, ...] = field(default_factory=tuple)
