"""Tests for animation cropper logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.datatypes import CropResult, ImageData
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError
from game_toolbox.tools.animation_cropper.logic import (
    analyze_bounding_box,
    analyze_only,
    compute_union_bbox,
    crop_batch,
    crop_frame,
)

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def partial_alpha_image(tmp_path: Path) -> Path:
    """Create a 100x100 RGBA image with content only in a 20x30 region."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    # Draw a non-transparent block at (10, 20) sized 20x30.
    for x in range(10, 30):
        for y in range(20, 50):
            img.putpixel((x, y), (255, 0, 0, 255))
    path = tmp_path / "partial.png"
    img.save(str(path))
    return path


@pytest.fixture()
def fully_transparent_image(tmp_path: Path) -> Path:
    """Create a fully transparent 50x50 image."""
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    path = tmp_path / "transparent.png"
    img.save(str(path))
    return path


@pytest.fixture()
def fully_opaque_image(tmp_path: Path) -> Path:
    """Create a fully opaque 60x40 image."""
    img = Image.new("RGBA", (60, 40), (128, 64, 32, 255))
    path = tmp_path / "opaque.png"
    img.save(str(path))
    return path


@pytest.fixture()
def sample_frames(tmp_path: Path) -> list[Path]:
    """Create three 100x100 RGBA frames with content in different regions."""
    frames: list[Path] = []
    regions = [
        (10, 10, 30, 30),  # frame 0: content at (10,10)-(39,39)
        (50, 50, 20, 20),  # frame 1: content at (50,50)-(69,69)
        (30, 20, 40, 60),  # frame 2: content at (30,20)-(69,79)
    ]
    for i, (rx, ry, rw, rh) in enumerate(regions):
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        for x in range(rx, rx + rw):
            for y in range(ry, ry + rh):
                img.putpixel((x, y), (255, 128, 0, 200))
        path = tmp_path / f"frame_{i:03d}.png"
        img.save(str(path))
        frames.append(path)
    return frames


# ── TestAnalyzeBoundingBox ─────────────────────────────────────────────────


class TestAnalyzeBoundingBox:
    """Tests for the ``analyze_bounding_box`` function."""

    def test_partial_content(self, partial_alpha_image: Path) -> None:
        """Bounding box matches the non-transparent region."""
        x, y, w, h = analyze_bounding_box(partial_alpha_image)
        assert (x, y, w, h) == (10, 20, 20, 30)

    def test_fully_transparent(self, fully_transparent_image: Path) -> None:
        """Fully transparent image returns (0, 0, 0, 0)."""
        assert analyze_bounding_box(fully_transparent_image) == (0, 0, 0, 0)

    def test_fully_opaque(self, fully_opaque_image: Path) -> None:
        """Fully opaque image returns the full image dimensions."""
        x, y, w, h = analyze_bounding_box(fully_opaque_image)
        assert (x, y, w, h) == (0, 0, 60, 40)

    def test_corrupt_file_raises(self, tmp_path: Path) -> None:
        """ToolError is raised for an unreadable file."""
        bad = tmp_path / "corrupt.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(ToolError, match="could not be opened"):
            analyze_bounding_box(bad)


# ── TestComputeUnionBbox ───────────────────────────────────────────────────


class TestComputeUnionBbox:
    """Tests for the ``compute_union_bbox`` function."""

    def test_overlapping_boxes(self) -> None:
        """Overlapping bounding boxes produce a tight union."""
        result = compute_union_bbox([(10, 10, 20, 20), (20, 20, 20, 20)])
        assert result == (10, 10, 30, 30)

    def test_disjoint_boxes(self) -> None:
        """Disjoint bounding boxes produce a union spanning both."""
        result = compute_union_bbox([(0, 0, 10, 10), (90, 90, 10, 10)])
        assert result == (0, 0, 100, 100)

    def test_single_box(self) -> None:
        """A single box returns itself."""
        result = compute_union_bbox([(5, 10, 20, 30)])
        assert result == (5, 10, 20, 30)

    def test_all_empty(self) -> None:
        """All-empty bounding boxes return (0, 0, 0, 0)."""
        result = compute_union_bbox([(0, 0, 0, 0), (0, 0, 0, 0)])
        assert result == (0, 0, 0, 0)

    def test_empty_list(self) -> None:
        """Empty input list returns (0, 0, 0, 0)."""
        assert compute_union_bbox([]) == (0, 0, 0, 0)

    def test_mixed_empty_and_valid(self) -> None:
        """Empty bounding boxes are skipped in the union."""
        result = compute_union_bbox([(0, 0, 0, 0), (10, 10, 20, 20)])
        assert result == (10, 10, 20, 20)


# ── TestCropFrame ──────────────────────────────────────────────────────────


class TestCropFrame:
    """Tests for the ``crop_frame`` function."""

    def test_smaller_crop(self, partial_alpha_image: Path, tmp_path: Path) -> None:
        """Cropping smaller than source trims the edges."""
        out = tmp_path / "out" / "cropped.png"
        result = crop_frame(partial_alpha_image, out, width=40, height=40)

        assert isinstance(result, ImageData)
        assert result.width == 40
        assert result.height == 40
        assert out.exists()

    def test_larger_crop_pads_with_transparency(self, partial_alpha_image: Path, tmp_path: Path) -> None:
        """Cropping larger than source pads with transparent pixels."""
        out = tmp_path / "padded.png"
        result = crop_frame(partial_alpha_image, out, width=200, height=200)

        assert result.width == 200
        assert result.height == 200

        # Verify corners are transparent.
        img = Image.open(out)
        pixel_tl = img.getpixel((0, 0))
        pixel_br = img.getpixel((199, 199))
        assert isinstance(pixel_tl, tuple)
        assert isinstance(pixel_br, tuple)
        assert pixel_tl[3] == 0
        assert pixel_br[3] == 0

    def test_exact_size(self, partial_alpha_image: Path, tmp_path: Path) -> None:
        """Cropping to exact source size is a no-op (same dimensions)."""
        out = tmp_path / "exact.png"
        result = crop_frame(partial_alpha_image, out, width=100, height=100)

        assert result.width == 100
        assert result.height == 100

    def test_corrupt_input_raises(self, tmp_path: Path) -> None:
        """ToolError is raised for an unreadable input file."""
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(ToolError, match="could not be opened"):
            crop_frame(bad, tmp_path / "out.png", width=10, height=10)

    def test_auto_creates_output_dir(self, partial_alpha_image: Path, tmp_path: Path) -> None:
        """Output directory is created if it does not exist."""
        out = tmp_path / "deep" / "nested" / "cropped.png"
        crop_frame(partial_alpha_image, out, width=50, height=50)
        assert out.exists()

    def test_webp_format(self, partial_alpha_image: Path, tmp_path: Path) -> None:
        """WebP output format works correctly."""
        out = tmp_path / "cropped.webp"
        result = crop_frame(partial_alpha_image, out, width=50, height=50, output_format="webp")
        assert result.format == "webp"
        assert out.exists()


# ── TestCropBatch ──────────────────────────────────────────────────────────


class TestCropBatch:
    """Tests for the ``crop_batch`` and ``analyze_only`` functions."""

    def test_crop_batch_happy_path(self, sample_frames: list[Path], tmp_path: Path) -> None:
        """Batch crop produces the expected number of output files."""
        out_dir = tmp_path / "batch_out"
        result = crop_batch(sample_frames, out_dir, width=64, height=64)

        assert isinstance(result, CropResult)
        assert result.count == 3
        assert len(result.images) == 3
        assert all(img.width == 64 and img.height == 64 for img in result.images)

    def test_suggested_size_populated(self, sample_frames: list[Path], tmp_path: Path) -> None:
        """Suggested size fields are populated from the union bbox analysis."""
        result = crop_batch(sample_frames, tmp_path / "out", width=128, height=128)

        # Union bbox spans from (10,10) to (70,80) → 60x70.
        # Next power of two: 64x128.
        assert result.suggested_width == 64
        assert result.suggested_height == 128

    def test_event_emission(self, sample_frames: list[Path], tmp_path: Path) -> None:
        """EventBus receives progress and completed events during batch crop."""
        bus = EventBus()
        progress_events: list[dict[str, Any]] = []
        completed_events: list[dict[str, Any]] = []
        log_events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: progress_events.append(kw))
        bus.subscribe("completed", lambda **kw: completed_events.append(kw))
        bus.subscribe("log", lambda **kw: log_events.append(kw))

        crop_batch(sample_frames, tmp_path / "out", width=64, height=64, event_bus=bus)

        # 3 analyse + 3 crop = 6 progress events.
        assert len(progress_events) == 6
        assert progress_events[0]["tool"] == "animation_cropper"
        assert len(completed_events) == 1
        assert len(log_events) == 1

    def test_analyze_only_mode(self, sample_frames: list[Path]) -> None:
        """Analyse-only returns zero images with suggested dimensions."""
        result = analyze_only(sample_frames)

        assert isinstance(result, CropResult)
        assert result.count == 0
        assert len(result.images) == 0
        assert result.suggested_width > 0
        assert result.suggested_height > 0

    def test_analyze_only_events(self, sample_frames: list[Path]) -> None:
        """Analyse-only emits progress and completed events."""
        bus = EventBus()
        progress_events: list[dict[str, Any]] = []
        completed_events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: progress_events.append(kw))
        bus.subscribe("completed", lambda **kw: completed_events.append(kw))

        analyze_only(sample_frames, event_bus=bus)

        assert len(progress_events) == 3
        assert len(completed_events) == 1

    def test_analyze_all_transparent(self, tmp_path: Path) -> None:
        """All-transparent frames yield zero suggested size."""
        frames: list[Path] = []
        for i in range(2):
            img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
            path = tmp_path / f"empty_{i}.png"
            img.save(str(path))
            frames.append(path)

        result = analyze_only(frames)
        assert result.suggested_width == 0
        assert result.suggested_height == 0
