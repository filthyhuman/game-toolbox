"""Tests for chroma key removal logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.datatypes import ChromaKeyResult, ImageData
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError
from game_toolbox.tools.chroma_key.logic import (
    COLOR_PRESETS,
    chroma_key_batch,
    remove_chroma_key,
    validate_chroma_params,
)

# Pillow's getpixel() returns a broad union; cast for mypy.
_Pixel = tuple[int, ...]


def _px(img: Image.Image, xy: tuple[int, int]) -> _Pixel:
    """Return the pixel value at *xy* as a typed tuple."""
    val = img.getpixel(xy)
    assert isinstance(val, tuple)
    return val


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def green_bg_image(tmp_path: Path) -> Path:
    """Create an image with a green background and red foreground square."""
    img = Image.new("RGB", (100, 100), color=COLOR_PRESETS["green"])
    # Paint a red 40x40 square in the centre.
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (255, 0, 0))
    img_path = tmp_path / "green_bg.png"
    img.save(str(img_path))
    return img_path


@pytest.fixture()
def blue_bg_image(tmp_path: Path) -> Path:
    """Create an image with a blue background."""
    img = Image.new("RGB", (60, 40), color=COLOR_PRESETS["blue"])
    img_path = tmp_path / "blue_bg.png"
    img.save(str(img_path))
    return img_path


@pytest.fixture()
def image_dir(tmp_path: Path) -> Path:
    """Create a directory with multiple green-background test images."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    for name in ("a.png", "b.png", "c.png"):
        img = Image.new("RGB", (50, 50), color=COLOR_PRESETS["green"])
        img.save(str(img_dir / name))
    return img_dir


# ── TestRemoveChromaKey ───────────────────────────────────────────────────


class TestRemoveChromaKey:
    """Tests for the ``remove_chroma_key`` function."""

    def test_removes_green_background(self, green_bg_image: Path, tmp_path: Path) -> None:
        """Green background pixels become transparent, red foreground is kept."""
        out = tmp_path / "out" / "keyed.png"
        result = remove_chroma_key(green_bg_image, out, color=COLOR_PRESETS["green"])

        assert isinstance(result, ImageData)
        assert out.exists()

        img = Image.open(out)
        assert img.mode == "RGBA"
        # Green corner should be transparent.
        assert _px(img, (0, 0))[3] == 0
        # Red centre should be opaque.
        assert _px(img, (50, 50))[3] == 255

    def test_removes_blue_background(self, blue_bg_image: Path, tmp_path: Path) -> None:
        """Blue background pixels become transparent."""
        out = tmp_path / "keyed_blue.png"
        result = remove_chroma_key(blue_bg_image, out, color=COLOR_PRESETS["blue"])

        assert isinstance(result, ImageData)
        img = Image.open(out)
        assert _px(img, (0, 0))[3] == 0

    def test_custom_colour(self, tmp_path: Path) -> None:
        """A custom colour key works correctly."""
        custom = (128, 128, 0)
        img = Image.new("RGB", (40, 40), color=custom)
        src = tmp_path / "custom.png"
        img.save(str(src))

        out = tmp_path / "keyed_custom.png"
        remove_chroma_key(src, out, color=custom, tolerance=10.0)

        result_img = Image.open(out)
        assert _px(result_img, (20, 20))[3] == 0

    def test_softness_creates_transition(self, green_bg_image: Path, tmp_path: Path) -> None:
        """Softness > 0 produces semi-transparent pixels at colour boundaries."""
        out = tmp_path / "soft.png"
        remove_chroma_key(green_bg_image, out, color=COLOR_PRESETS["green"], tolerance=10.0, softness=100.0)

        img = Image.open(out)
        # Green corner should still be transparent (close to key colour).
        assert _px(img, (0, 0))[3] == 0
        # Red centre should be opaque (far from key colour).
        assert _px(img, (50, 50))[3] == 255

    def test_zero_softness_hard_edge(self, green_bg_image: Path, tmp_path: Path) -> None:
        """Zero softness produces a hard binary alpha mask."""
        out = tmp_path / "hard.png"
        remove_chroma_key(green_bg_image, out, color=COLOR_PRESETS["green"], tolerance=30.0, softness=0.0)

        img = Image.open(out)
        alpha = _px(img, (0, 0))[3]
        assert alpha == 0
        alpha_fg = _px(img, (50, 50))[3]
        assert alpha_fg == 255

    def test_raises_on_invalid_file(self, tmp_path: Path) -> None:
        """ToolError is raised for an unreadable file."""
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(ToolError, match="could not be opened"):
            remove_chroma_key(bad, tmp_path / "out.png", color=(0, 177, 64))

    def test_creates_output_directory(self, green_bg_image: Path, tmp_path: Path) -> None:
        """Output directory is created if it does not exist."""
        out = tmp_path / "deep" / "nested" / "keyed.png"
        remove_chroma_key(green_bg_image, out, color=COLOR_PRESETS["green"])
        assert out.exists()


# ── TestChromaKeyBatch ────────────────────────────────────────────────────


class TestChromaKeyBatch:
    """Tests for the ``chroma_key_batch`` function."""

    def test_batch_to_output_dir(self, image_dir: Path, tmp_path: Path) -> None:
        """Batch processing writes keyed images to the output directory."""
        from game_toolbox.tools.image_resizer.logic import collect_image_paths

        paths = collect_image_paths([image_dir])
        out_dir = tmp_path / "batch_out"

        result = chroma_key_batch(paths, out_dir, color=COLOR_PRESETS["green"])

        assert isinstance(result, ChromaKeyResult)
        assert result.count == 3
        assert not result.in_place
        assert all(img.format == "png" for img in result.images)

    def test_batch_in_place(self, tmp_path: Path) -> None:
        """In-place processing overwrites the originals."""
        img_path = tmp_path / "inplace.png"
        Image.new("RGB", (50, 50), color=COLOR_PRESETS["green"]).save(str(img_path))

        result = chroma_key_batch([img_path], None, color=COLOR_PRESETS["green"])

        assert result.in_place is True
        assert result.count == 1
        reopened = Image.open(img_path)
        assert reopened.mode == "RGBA"
        assert _px(reopened, (0, 0))[3] == 0

    def test_batch_emits_events(self, green_bg_image: Path, tmp_path: Path) -> None:
        """EventBus receives progress and completed events during batch."""
        bus = EventBus()
        progress_events: list[dict[str, Any]] = []
        completed_events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: progress_events.append(kw))
        bus.subscribe("completed", lambda **kw: completed_events.append(kw))

        chroma_key_batch(
            [green_bg_image],
            tmp_path / "out",
            color=COLOR_PRESETS["green"],
            event_bus=bus,
        )

        assert len(progress_events) == 1
        assert progress_events[0]["current"] == 1
        assert progress_events[0]["tool"] == "chroma_key"
        assert len(completed_events) == 1

    def test_batch_webp_output(self, green_bg_image: Path, tmp_path: Path) -> None:
        """Batch processing can output WebP format."""
        result = chroma_key_batch(
            [green_bg_image],
            tmp_path / "out",
            color=COLOR_PRESETS["green"],
            output_format="webp",
        )

        assert result.images[0].format == "webp"
        assert result.images[0].path.suffix == ".webp"


# ── TestValidation ────────────────────────────────────────────────────────


class TestValidation:
    """Tests for the ``validate_chroma_params`` function."""

    def test_invalid_tolerance_raises(self) -> None:
        """Tolerance outside 0-255 raises ValidationError."""
        with pytest.raises(ValidationError, match="Tolerance"):
            validate_chroma_params(color=(0, 177, 64), tolerance=300, softness=10, output_format="png")

    def test_negative_softness_raises(self) -> None:
        """Negative softness raises ValidationError."""
        with pytest.raises(ValidationError, match="Softness"):
            validate_chroma_params(color=(0, 177, 64), tolerance=30, softness=-5, output_format="png")

    def test_invalid_format_raises(self) -> None:
        """A format that does not support alpha raises ValidationError."""
        with pytest.raises(ValidationError, match="alpha"):
            validate_chroma_params(color=(0, 177, 64), tolerance=30, softness=10, output_format="jpg")

    def test_invalid_colour_channel_raises(self) -> None:
        """Colour channel outside 0-255 raises ValidationError."""
        with pytest.raises(ValidationError, match="Colour channel"):
            validate_chroma_params(color=(300, 0, 0), tolerance=30, softness=10, output_format="png")

    def test_valid_params_pass(self) -> None:
        """Valid parameters do not raise."""
        validate_chroma_params(color=(0, 177, 64), tolerance=30, softness=10, output_format="png")
