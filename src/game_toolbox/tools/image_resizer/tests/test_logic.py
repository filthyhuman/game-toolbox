"""Tests for image resizer logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.datatypes import ImageData, ResizeResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError
from game_toolbox.tools.image_resizer.logic import (
    collect_image_paths,
    resize_batch,
    resize_image,
    validate_resize_params,
)

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def sample_image(tmp_path: Path) -> Path:
    """Create a 100x80 RGB test image."""
    img_path = tmp_path / "sample.png"
    img = Image.new("RGB", (100, 80), color=(255, 0, 0))
    img.save(str(img_path))
    return img_path


@pytest.fixture()
def image_dir(tmp_path: Path) -> Path:
    """Create a directory with multiple test images."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    for name in ("a.png", "b.jpg", "c.webp"):
        img = Image.new("RGB", (100, 80), color=(0, 128, 255))
        img.save(str(img_dir / name))
    # Non-image file should be ignored.
    (img_dir / "readme.txt").write_text("not an image")
    return img_dir


# ── TestCollectImagePaths ──────────────────────────────────────────────────


class TestCollectImagePaths:
    """Tests for the ``collect_image_paths`` function."""

    def test_collects_single_file(self, sample_image: Path) -> None:
        """A single image file is collected."""
        result = collect_image_paths([sample_image])
        assert len(result) == 1
        assert result[0] == sample_image.resolve()

    def test_collects_from_directory(self, image_dir: Path) -> None:
        """All image files in a directory are collected, non-images skipped."""
        result = collect_image_paths([image_dir])
        assert len(result) == 3
        extensions = {p.suffix for p in result}
        assert extensions == {".png", ".jpg", ".webp"}

    def test_collects_mixed_inputs(self, sample_image: Path, image_dir: Path) -> None:
        """Files and directories can be mixed."""
        result = collect_image_paths([sample_image, image_dir])
        assert len(result) == 4  # 1 standalone + 3 in directory

    def test_raises_on_empty(self, tmp_path: Path) -> None:
        """ToolError is raised when no images are found."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(ToolError, match="No image files found"):
            collect_image_paths([empty_dir])

    def test_deduplicates_paths(self, sample_image: Path) -> None:
        """Duplicate inputs yield unique paths."""
        result = collect_image_paths([sample_image, sample_image])
        assert len(result) == 1


# ── TestValidateResizeParams ───────────────────────────────────────────────


class TestValidateResizeParams:
    """Tests for the ``validate_resize_params`` function."""

    def test_invalid_mode_raises(self) -> None:
        """An unknown mode raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid mode"):
            validate_resize_params(mode="zoom", width=100, height=100, percent=None, resample="lanczos")

    def test_exact_requires_dimensions(self) -> None:
        """Exact mode without width/height raises ValidationError."""
        with pytest.raises(ValidationError, match="requires both"):
            validate_resize_params(mode="exact", width=None, height=100, percent=None, resample="lanczos")

    def test_percent_requires_percent(self) -> None:
        """Percent mode without percent value raises ValidationError."""
        with pytest.raises(ValidationError, match="requires --percent"):
            validate_resize_params(mode="percent", width=None, height=None, percent=None, resample="lanczos")

    def test_invalid_resample_raises(self) -> None:
        """An unknown resample filter raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid resample"):
            validate_resize_params(mode="exact", width=100, height=100, percent=None, resample="magic")

    def test_percent_out_of_range_raises(self) -> None:
        """Percent outside 1-1000 raises ValidationError."""
        with pytest.raises(ValidationError, match="between 1 and 1000"):
            validate_resize_params(mode="percent", width=None, height=None, percent=0, resample="lanczos")


# ── TestResizeImage ────────────────────────────────────────────────────────


class TestResizeImage:
    """Tests for the ``resize_image`` function."""

    def test_exact_mode(self, sample_image: Path, tmp_path: Path) -> None:
        """Exact mode resizes to the specified dimensions."""
        out = tmp_path / "out" / "resized.png"
        result = resize_image(sample_image, out, mode="exact", width=50, height=40)

        assert isinstance(result, ImageData)
        assert result.width == 50
        assert result.height == 40
        assert out.exists()

    def test_fit_mode_preserves_aspect(self, sample_image: Path, tmp_path: Path) -> None:
        """Fit mode preserves aspect ratio and fits within the box."""
        out = tmp_path / "fit.png"
        # Original is 100x80 (5:4), fitting into 50x50 → 50x40.
        result = resize_image(sample_image, out, mode="fit", width=50, height=50)

        assert result.width == 50
        assert result.height == 40

    def test_fill_mode_crops_to_box(self, sample_image: Path, tmp_path: Path) -> None:
        """Fill mode fills the box exactly, cropping excess."""
        out = tmp_path / "fill.png"
        result = resize_image(sample_image, out, mode="fill", width=50, height=50)

        assert result.width == 50
        assert result.height == 50

    def test_percent_mode(self, sample_image: Path, tmp_path: Path) -> None:
        """Percent mode scales by the given percentage."""
        out = tmp_path / "half.png"
        result = resize_image(sample_image, out, mode="percent", percent=50)

        assert result.width == 50
        assert result.height == 40

    def test_raises_on_invalid_file(self, tmp_path: Path) -> None:
        """ToolError is raised for a non-image file."""
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(ToolError, match="could not be opened"):
            resize_image(bad, tmp_path / "out.png", mode="exact", width=10, height=10)

    def test_creates_output_directory(self, sample_image: Path, tmp_path: Path) -> None:
        """Output directory is created if it does not exist."""
        out = tmp_path / "deep" / "nested" / "resized.png"
        resize_image(sample_image, out, mode="exact", width=10, height=10)
        assert out.exists()


# ── TestResizeBatch ────────────────────────────────────────────────────────


class TestResizeBatch:
    """Tests for the ``resize_batch`` function."""

    def test_batch_to_output_dir(self, image_dir: Path, tmp_path: Path) -> None:
        """Batch resize writes to the output directory."""
        paths = collect_image_paths([image_dir])
        out_dir = tmp_path / "batch_out"

        result = resize_batch(paths, out_dir, mode="exact", width=32, height=32)

        assert isinstance(result, ResizeResult)
        assert result.count == 3
        assert not result.in_place
        assert all(img.width == 32 and img.height == 32 for img in result.images)

    def test_batch_in_place(self, tmp_path: Path) -> None:
        """In-place resize overwrites the originals."""
        img_path = tmp_path / "inplace.png"
        Image.new("RGB", (200, 100)).save(str(img_path))

        result = resize_batch([img_path], None, mode="percent", percent=50)

        assert result.in_place is True
        assert result.count == 1
        # Verify the original file was overwritten with new dimensions.
        reopened = Image.open(img_path)
        assert reopened.size == (100, 50)

    def test_batch_emits_events(self, sample_image: Path, tmp_path: Path) -> None:
        """EventBus receives progress and completed events during batch."""
        bus = EventBus()
        progress_events: list[dict[str, Any]] = []
        completed_events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: progress_events.append(kw))
        bus.subscribe("completed", lambda **kw: completed_events.append(kw))

        resize_batch(
            [sample_image],
            tmp_path / "out",
            mode="exact",
            width=10,
            height=10,
            event_bus=bus,
        )

        assert len(progress_events) == 1
        assert progress_events[0]["current"] == 1
        assert progress_events[0]["tool"] == "image_resizer"
        assert len(completed_events) == 1
