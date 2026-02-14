"""Tests for sprite sheet generation logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import fromstring

import pytest
from PIL import Image

from game_toolbox.core.datatypes import SpriteSheetResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError
from game_toolbox.tools.sprite_sheet.logic import generate_sprite_sheet, validate_sprite_params

# Pillow's getpixel() returns a broad union; cast for mypy.
_Pixel = tuple[int, ...]


def _px(img: Image.Image, xy: tuple[int, int]) -> _Pixel:
    """Return the pixel value at *xy* as a typed tuple."""
    val = img.getpixel(xy)
    assert isinstance(val, tuple)
    return val


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def four_images(tmp_path: Path) -> list[Path]:
    """Create four 32x32 RGBA test images with distinct colours."""
    colours = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    paths: list[Path] = []
    for i, colour in enumerate(colours):
        img_path = tmp_path / f"frame_{i:05d}.png"
        img = Image.new("RGBA", (32, 32), color=colour)
        img.save(str(img_path))
        paths.append(img_path)
    return paths


@pytest.fixture()
def mixed_size_images(tmp_path: Path) -> list[Path]:
    """Create images with different dimensions."""
    sizes = [(32, 32), (64, 48), (16, 24)]
    paths: list[Path] = []
    for i, size in enumerate(sizes):
        img_path = tmp_path / f"mixed_{i}.png"
        img = Image.new("RGBA", size, color=(128, 128, 128, 255))
        img.save(str(img_path))
        paths.append(img_path)
    return paths


# ── TestGenerateSpriteSheet ───────────────────────────────────────────────


class TestGenerateSpriteSheet:
    """Tests for the ``generate_sprite_sheet`` function."""

    def test_four_images_auto_grid(self, four_images: list[Path], tmp_path: Path) -> None:
        """Four images auto-arrange into a 2x2 grid."""
        out = tmp_path / "sheet.png"
        result = generate_sprite_sheet(four_images, out)

        assert isinstance(result, SpriteSheetResult)
        assert result.columns == 2
        assert result.rows == 2
        assert len(result.frames) == 4
        assert out.exists()

        sheet = Image.open(out)
        assert sheet.mode == "RGBA"

    def test_custom_columns(self, four_images: list[Path], tmp_path: Path) -> None:
        """Custom column count overrides auto-calculation."""
        out = tmp_path / "sheet.png"
        result = generate_sprite_sheet(four_images, out, columns=4)

        assert result.columns == 4
        assert result.rows == 1

    def test_single_column(self, four_images: list[Path], tmp_path: Path) -> None:
        """Single column produces a vertical strip."""
        out = tmp_path / "strip.png"
        result = generate_sprite_sheet(four_images, out, columns=1)

        assert result.columns == 1
        assert result.rows == 4

    def test_padding_affects_size(self, four_images: list[Path], tmp_path: Path) -> None:
        """Padding increases the total sheet dimensions."""
        out_no_pad = tmp_path / "no_pad.png"
        out_pad = tmp_path / "pad.png"

        r1 = generate_sprite_sheet(four_images, out_no_pad, columns=2, padding=0)
        r2 = generate_sprite_sheet(four_images, out_pad, columns=2, padding=10)

        assert r2.sheet.width > r1.sheet.width
        assert r2.sheet.height > r1.sheet.height

    def test_preserves_rgba_transparency(self, tmp_path: Path) -> None:
        """RGBA transparency is preserved in the sprite sheet."""
        img_path = tmp_path / "transparent.png"
        img = Image.new("RGBA", (32, 32), color=(0, 0, 0, 0))
        img.save(str(img_path))

        out = tmp_path / "sheet.png"
        generate_sprite_sheet([img_path], out)

        sheet = Image.open(out)
        assert _px(sheet, (0, 0))[3] == 0

    def test_mixed_sizes_use_max(self, mixed_size_images: list[Path], tmp_path: Path) -> None:
        """Mixed-size images are placed in cells sized to the largest frame."""
        out = tmp_path / "mixed.png"
        result = generate_sprite_sheet(mixed_size_images, out, columns=3, padding=0)

        # Max dimensions are 64x48.  3 columns, 1 row.
        assert result.sheet.width == 3 * 64
        assert result.sheet.height == 48

    def test_frame_positions_are_correct(self, four_images: list[Path], tmp_path: Path) -> None:
        """Frame positions in the result match the grid layout."""
        out = tmp_path / "sheet.png"
        result = generate_sprite_sheet(four_images, out, columns=2, padding=1)

        f0 = result.frames[0]
        f1 = result.frames[1]
        f2 = result.frames[2]

        assert f0.x == 0 and f0.y == 0
        assert f1.x == 33  # 32 + 1 padding
        assert f2.x == 0 and f2.y == 33

    def test_raises_on_invalid_image(self, tmp_path: Path) -> None:
        """ToolError is raised for an unreadable image file."""
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(ToolError, match="could not be opened"):
            generate_sprite_sheet([bad], tmp_path / "sheet.png")

    def test_creates_output_directory(self, four_images: list[Path], tmp_path: Path) -> None:
        """Output directory is created if it does not exist."""
        out = tmp_path / "deep" / "nested" / "sheet.png"
        generate_sprite_sheet(four_images, out)
        assert out.exists()

    def test_emits_events(self, four_images: list[Path], tmp_path: Path) -> None:
        """EventBus receives progress and completed events."""
        bus = EventBus()
        progress_events: list[dict[str, Any]] = []
        completed_events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: progress_events.append(kw))
        bus.subscribe("completed", lambda **kw: completed_events.append(kw))

        generate_sprite_sheet(four_images, tmp_path / "sheet.png", event_bus=bus)

        assert len(progress_events) == 4
        assert progress_events[0]["tool"] == "sprite_sheet"
        assert len(completed_events) == 1


# ── TestMetadata ──────────────────────────────────────────────────────────


class TestMetadata:
    """Tests for metadata generation in different formats."""

    def test_json_metadata(self, four_images: list[Path], tmp_path: Path) -> None:
        """JSON metadata file is valid and contains expected fields."""
        out = tmp_path / "sheet.png"
        result = generate_sprite_sheet(four_images, out, metadata_format="json", columns=2)

        meta_path = result.metadata_path
        assert meta_path.suffix == ".json"
        assert meta_path.exists()

        data = json.loads(meta_path.read_text())
        assert data["columns"] == 2
        assert data["rows"] == 2
        assert len(data["frames"]) == 4
        assert data["frames"][0]["name"] == "frame_00000"

    def test_css_metadata(self, four_images: list[Path], tmp_path: Path) -> None:
        """CSS metadata file contains sprite classes."""
        out = tmp_path / "sheet.png"
        result = generate_sprite_sheet(four_images, out, metadata_format="css")

        meta_path = result.metadata_path
        assert meta_path.suffix == ".css"
        content = meta_path.read_text()
        assert ".sprite {" in content
        assert ".sprite.frame_00000 {" in content
        assert "background-position:" in content

    def test_xml_metadata(self, four_images: list[Path], tmp_path: Path) -> None:
        """XML metadata file is well-formed and contains expected elements."""
        out = tmp_path / "sheet.png"
        result = generate_sprite_sheet(four_images, out, metadata_format="xml")

        meta_path = result.metadata_path
        assert meta_path.suffix == ".xml"

        root = fromstring(meta_path.read_text())
        assert root.tag == "sprite_sheet"
        assert root.get("image") == "sheet.png"
        frame_els = root.findall("frame")
        assert len(frame_els) == 4


# ── TestValidation ────────────────────────────────────────────────────────


class TestValidation:
    """Tests for the ``validate_sprite_params`` function."""

    def test_zero_images_raises(self) -> None:
        """At least 1 image is required."""
        with pytest.raises(ValidationError, match="At least 1"):
            validate_sprite_params(columns=None, padding=0, metadata_format="json", input_count=0)

    def test_invalid_columns_raises(self) -> None:
        """Columns < 1 raises ValidationError."""
        with pytest.raises(ValidationError, match="Columns"):
            validate_sprite_params(columns=0, padding=0, metadata_format="json", input_count=4)

    def test_negative_padding_raises(self) -> None:
        """Negative padding raises ValidationError."""
        with pytest.raises(ValidationError, match="Padding"):
            validate_sprite_params(columns=None, padding=-1, metadata_format="json", input_count=4)

    def test_invalid_format_raises(self) -> None:
        """An unknown metadata format raises ValidationError."""
        with pytest.raises(ValidationError, match="Metadata format"):
            validate_sprite_params(columns=None, padding=0, metadata_format="yaml", input_count=4)

    def test_valid_params_pass(self) -> None:
        """Valid parameters do not raise."""
        validate_sprite_params(columns=4, padding=1, metadata_format="json", input_count=4)
