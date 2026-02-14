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


@dataclass(frozen=True)
class ResizeResult:
    """Result of an image resize operation."""

    images: tuple[ImageData, ...]
    count: int
    in_place: bool


@dataclass(frozen=True)
class ChromaKeyResult:
    """Result of a chroma key removal operation."""

    images: tuple[ImageData, ...]
    count: int
    in_place: bool


@dataclass(frozen=True)
class SpriteFrame:
    """Position and size of a single frame within a sprite sheet."""

    name: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SpriteSheetResult:
    """Result of a sprite sheet generation operation."""

    sheet: ImageData
    frames: tuple[SpriteFrame, ...]
    columns: int
    rows: int
    padding: int
    metadata_path: Path
