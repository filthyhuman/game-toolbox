"""Tests for atlas unpacker internal modules and extraction logic."""

from __future__ import annotations

import plistlib
import struct
import zlib
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.datatypes import AtlasUnpackResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError
from game_toolbox.tools.atlas_unpacker._ccz import decompress_ccz, is_ccz
from game_toolbox.tools.atlas_unpacker._plist import (
    AtlasSpriteFrame,
    _parse_point,
    _parse_rect,
    load_plist,
    plist_metadata,
)
from game_toolbox.tools.atlas_unpacker._pvr import describe_pvr, parse_pvr
from game_toolbox.tools.atlas_unpacker.logic import (
    extract_atlas,
    probe_atlas,
    validate_atlas_params,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_plist(path: Path, frames: dict[str, dict[str, Any]], metadata: dict[str, Any] | None = None) -> Path:
    """Create a binary plist file at *path* with the given frame data."""
    data: dict[str, Any] = {"frames": frames}
    if metadata:
        data["metadata"] = metadata
    with path.open("wb") as fh:
        plistlib.dump(data, fh)
    return path


def _make_png_atlas(path: Path, width: int = 64, height: int = 64) -> Path:
    """Create a simple RGBA PNG atlas with coloured quadrants."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    colours = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    half_w, half_h = width // 2, height // 2
    for i, colour in enumerate(colours):
        col, row = i % 2, i // 2
        tile = Image.new("RGBA", (half_w, half_h), colour)
        img.paste(tile, (col * half_w, row * half_h))
    img.save(str(path))
    return path


def _make_pvr_rgba8888(width: int, height: int) -> bytes:
    """Build a minimal PVRv2 RGBA_8888 file in memory."""
    pixel_data = bytes([255, 0, 0, 255] * (width * height))
    # PVRv2 header: 13 x uint32 = 52 bytes
    header = struct.pack(
        "<13I",
        52,  # header length
        height,
        width,
        0,  # mipmaps
        0x12,  # flags (RGBA_8888)
        len(pixel_data),  # data length
        32,  # bpp
        0xFF000000,  # bitmask R
        0x00FF0000,  # bitmask G
        0x0000FF00,  # bitmask B
        0x000000FF,  # bitmask A
        0x21525650,  # PVR! tag
        1,  # surfaces
    )
    return header + pixel_data


def _make_ccz(payload: bytes, comp_type: int = 0) -> bytes:
    """Wrap *payload* in a CCZ container with zlib compression."""
    compressed = zlib.compress(payload) if comp_type == 0 else payload
    header = struct.pack(">4sHHII", b"CCZ!", comp_type, 2, 0, len(payload))
    return header + compressed


# ── Tests: _plist ─────────────────────────────────────────────────────────


class TestParseRect:
    """Tests for the ``_parse_rect`` helper."""

    def test_flat_format(self) -> None:
        """Parses ``{x,y,w,h}`` flat format."""
        assert _parse_rect("{10,20,30,40}") == (10, 20, 30, 40)

    def test_nested_format(self) -> None:
        """Parses ``{{x,y},{w,h}}`` Cocos2d format 2."""
        assert _parse_rect("{{100,200},{32,48}}") == (100, 200, 32, 48)

    def test_space_separated(self) -> None:
        """Parses space-separated fallback."""
        assert _parse_rect("5 10 15 20") == (5, 10, 15, 20)

    def test_raises_on_bad_input(self) -> None:
        """Raises ToolError for unparseable input."""
        with pytest.raises(ToolError, match="Cannot parse rect"):
            _parse_rect("{1,2}")


class TestParsePoint:
    """Tests for the ``_parse_point`` helper."""

    def test_normal(self) -> None:
        """Parses ``{x,y}`` point."""
        assert _parse_point("{10,20}") == (10, 20)

    def test_negative(self) -> None:
        """Handles negative offsets."""
        assert _parse_point("{-5,-10}") == (-5, -10)

    def test_raises_on_bad_input(self) -> None:
        """Raises ToolError for unparseable input."""
        with pytest.raises(ToolError, match="Cannot parse point"):
            _parse_point("{1}")


class TestLoadPlist:
    """Tests for ``load_plist``."""

    def test_loads_frames(self, tmp_path: Path) -> None:
        """Parses frame entries from a valid plist."""
        plist = _make_plist(
            tmp_path / "atlas.plist",
            frames={
                "hero.png": {
                    "frame": "{{0,0},{32,32}}",
                    "rotated": False,
                    "sourceSize": "{32,32}",
                    "offset": "{0,0}",
                },
                "enemy.png": {
                    "frame": "{{32,0},{16,24}}",
                    "rotated": True,
                    "sourceSize": "{24,16}",
                    "offset": "{2,-1}",
                },
            },
        )
        result = load_plist(plist)

        assert len(result) == 2
        assert "hero.png" in result
        hero = result["hero.png"]
        assert isinstance(hero, AtlasSpriteFrame)
        assert (hero.x, hero.y, hero.w, hero.h) == (0, 0, 32, 32)
        assert hero.rotated is False

        enemy = result["enemy.png"]
        assert enemy.rotated is True
        assert enemy.offset_x == 2
        assert enemy.offset_y == -1

    def test_natural_dimensions_unrotated(self) -> None:
        """Natural dimensions match w/h when not rotated."""
        frame = AtlasSpriteFrame("f.png", 0, 0, 32, 48, rotated=False, source_w=32, source_h=48, offset_x=0, offset_y=0)
        assert frame.natural_w == 32
        assert frame.natural_h == 48

    def test_natural_dimensions_rotated(self) -> None:
        """Natural dimensions are swapped when rotated."""
        frame = AtlasSpriteFrame("f.png", 0, 0, 32, 48, rotated=True, source_w=48, source_h=32, offset_x=0, offset_y=0)
        assert frame.natural_w == 48
        assert frame.natural_h == 32

    def test_raises_on_invalid_file(self, tmp_path: Path) -> None:
        """Raises ToolError for unreadable plist."""
        bad = tmp_path / "bad.plist"
        bad.write_bytes(b"not a plist")
        with pytest.raises(ToolError, match="Failed to read plist"):
            load_plist(bad)

    def test_empty_frames(self, tmp_path: Path) -> None:
        """An empty frames dict returns an empty result."""
        plist = _make_plist(tmp_path / "empty.plist", frames={})
        result = load_plist(plist)
        assert result == {}


class TestPlistMetadata:
    """Tests for ``plist_metadata``."""

    def test_returns_metadata(self, tmp_path: Path) -> None:
        """Returns the metadata section of the plist."""
        plist = _make_plist(
            tmp_path / "meta.plist",
            frames={},
            metadata={"textureFileName": "atlas.pvr.ccz", "size": "{1024,1024}"},
        )
        meta = plist_metadata(plist)
        assert meta["textureFileName"] == "atlas.pvr.ccz"

    def test_missing_metadata(self, tmp_path: Path) -> None:
        """Returns empty dict when metadata section is absent."""
        plist = _make_plist(tmp_path / "no_meta.plist", frames={})
        meta = plist_metadata(plist)
        assert meta == {}


# ── Tests: _ccz ───────────────────────────────────────────────────────────


class TestCCZ:
    """Tests for ``decompress_ccz`` and ``is_ccz``."""

    def test_decompress_zlib(self) -> None:
        """Decompresses a zlib-compressed CCZ payload."""
        payload = b"Hello, World!" * 100
        ccz_data = _make_ccz(payload, comp_type=0)

        result = decompress_ccz(ccz_data)
        assert result == payload

    def test_decompress_none(self) -> None:
        """Handles uncompressed (type 3) CCZ."""
        payload = b"raw data"
        header = struct.pack(">4sHHII", b"CCZ!", 3, 2, 0, len(payload))
        ccz_data = header + payload

        result = decompress_ccz(ccz_data)
        assert result == payload

    def test_rejects_bad_magic(self) -> None:
        """Raises ToolError for non-CCZ data."""
        with pytest.raises(ToolError, match="Not a CCZ file"):
            decompress_ccz(b"NOT!" + b"\x00" * 20)

    def test_rejects_short_data(self) -> None:
        """Raises ToolError for data shorter than CCZ header."""
        with pytest.raises(ToolError, match="too short"):
            decompress_ccz(b"CCZ!")

    def test_rejects_unknown_compression(self) -> None:
        """Raises ToolError for unknown compression type."""
        header = struct.pack(">4sHHII", b"CCZ!", 99, 2, 0, 10)
        with pytest.raises(ToolError, match="Unknown CCZ compression"):
            decompress_ccz(header + b"\x00" * 20)

    def test_is_ccz_true(self) -> None:
        """Recognises CCZ magic bytes."""
        assert is_ccz(b"CCZ!" + b"\x00" * 20) is True

    def test_is_ccz_false(self) -> None:
        """Rejects non-CCZ data."""
        assert is_ccz(b"PNG\x00" + b"\x00" * 20) is False
        assert is_ccz(b"") is False


# ── Tests: _pvr ───────────────────────────────────────────────────────────


class TestPVR:
    """Tests for ``parse_pvr`` and ``describe_pvr``."""

    def test_parse_rgba8888_v2(self) -> None:
        """Parses a PVRv2 RGBA8888 texture."""
        pvr_data = _make_pvr_rgba8888(4, 4)

        img = parse_pvr(pvr_data)
        assert img.size == (4, 4)
        assert img.mode == "RGBA"
        # All pixels should be red
        assert img.getpixel((0, 0)) == (255, 0, 0, 255)

    def test_rejects_short_data(self) -> None:
        """Raises ToolError for data shorter than 52 bytes."""
        with pytest.raises(ToolError, match="too short"):
            parse_pvr(b"\x00" * 10)

    def test_rejects_unknown_format(self) -> None:
        """Raises ToolError for data that is neither PVRv2 nor PVRv3."""
        data = b"\x00" * 60
        with pytest.raises(ToolError, match="Unknown PVR format"):
            parse_pvr(data)

    def test_describe_v2(self) -> None:
        """Describe returns version, dimensions, and format for PVRv2."""
        pvr_data = _make_pvr_rgba8888(8, 4)
        info = describe_pvr(pvr_data)
        assert info["version"] == 2
        assert info["width"] == 8
        assert info["height"] == 4

    def test_describe_unknown(self) -> None:
        """Describe returns unknown version for unrecognised data."""
        info = describe_pvr(b"\x00" * 60)
        assert info["version"] == "unknown"


# ── Tests: logic ──────────────────────────────────────────────────────────


@pytest.fixture()
def atlas_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Create a matching .plist + .png atlas pair for testing.

    The atlas is 64x64 with 4 coloured 32x32 quadrants (PIL top-left origin):

    - (0, 0): RED     (top-left)
    - (32, 0): GREEN  (top-right)
    - (0, 32): BLUE   (bottom-left)
    - (32, 32): YELLOW (bottom-right)

    Plist coordinates use Cocos2d bottom-left origin (y=0 at bottom):

    - RED at PIL y=0    → Cocos y = 64 - 0 - 32 = 32
    - GREEN at PIL y=0  → Cocos y = 32
    - BLUE at PIL y=32  → Cocos y = 64 - 32 - 32 = 0
    - YELLOW at PIL y=32 → Cocos y = 0
    """
    # Create a 64x64 atlas PNG with 4 coloured quadrants
    png_path = _make_png_atlas(tmp_path / "sprites.png", 64, 64)

    # Create a plist referencing 4 sprites using Cocos2d bottom-left coords
    plist_path = _make_plist(
        tmp_path / "sprites.plist",
        frames={
            "red.png": {
                "frame": "{{0,32},{32,32}}",
                "rotated": False,
                "sourceSize": "{32,32}",
                "offset": "{0,0}",
            },
            "green.png": {
                "frame": "{{32,32},{32,32}}",
                "rotated": False,
                "sourceSize": "{32,32}",
                "offset": "{0,0}",
            },
            "blue.png": {
                "frame": "{{0,0},{32,32}}",
                "rotated": False,
                "sourceSize": "{32,32}",
                "offset": "{0,0}",
            },
            "yellow.png": {
                "frame": "{{32,0},{32,32}}",
                "rotated": False,
                "sourceSize": "{32,32}",
                "offset": "{0,0}",
            },
        },
        metadata={"textureFileName": "sprites.png"},
    )
    return plist_path, png_path


class TestValidateAtlasParams:
    """Tests for ``validate_atlas_params``."""

    def test_rejects_none_path(self) -> None:
        """Raises ValidationError when plist_path is None."""
        with pytest.raises(ValidationError, match="required"):
            validate_atlas_params(plist_path=None, output_dir=None)

    def test_rejects_nonexistent_file(self, tmp_path: Path) -> None:
        """Raises ValidationError for a missing plist file."""
        with pytest.raises(ValidationError, match="does not exist"):
            validate_atlas_params(plist_path=tmp_path / "missing.plist", output_dir=None)

    def test_rejects_wrong_extension(self, tmp_path: Path) -> None:
        """Raises ValidationError for a non-.plist file."""
        txt = tmp_path / "data.txt"
        txt.write_text("hello")
        with pytest.raises(ValidationError, match=r"Expected a \.plist"):
            validate_atlas_params(plist_path=txt, output_dir=None)

    def test_valid_params(self, atlas_pair: tuple[Path, Path]) -> None:
        """Valid parameters pass without error."""
        plist_path, _ = atlas_pair
        validate_atlas_params(plist_path=plist_path, output_dir=None)


class TestExtractAtlas:
    """Tests for ``extract_atlas``."""

    def test_happy_path(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Extracts all sprites from a valid atlas pair."""
        plist_path, _ = atlas_pair
        out = tmp_path / "out"

        result = extract_atlas(plist_path, out)

        assert isinstance(result, AtlasUnpackResult)
        assert result.count == 4
        assert result.output_dir == out
        assert len(result.images) == 4

        # Check output files exist
        names = {img.path.name for img in result.images}
        assert "red.png" in names
        assert "green.png" in names
        assert "blue.png" in names
        assert "yellow.png" in names

    def test_sprite_colours(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Extracted sprites have the correct colours."""
        plist_path, _ = atlas_pair
        out = tmp_path / "colour_out"

        extract_atlas(plist_path, out)

        red_img = Image.open(out / "red.png").convert("RGBA")
        r, g, b, _a = red_img.getpixel((16, 16))  # type: ignore[misc]
        assert (r, g, b) == (255, 0, 0)

        green_img = Image.open(out / "green.png").convert("RGBA")
        r, g, b, _a = green_img.getpixel((16, 16))  # type: ignore[misc]
        assert (r, g, b) == (0, 255, 0)

    def test_skip_existing(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """When skip_existing=True, pre-existing files are skipped."""
        plist_path, _ = atlas_pair
        out = tmp_path / "skip_out"
        out.mkdir()

        # Pre-create one file
        (out / "red.png").write_bytes(b"existing")

        result = extract_atlas(plist_path, out, skip_existing=True)

        # Only 3 sprites should have been extracted (red.png skipped)
        assert result.count == 3

    def test_creates_output_dir(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Creates the output directory if it does not exist."""
        plist_path, _ = atlas_pair
        out = tmp_path / "deep" / "nested" / "dir"

        result = extract_atlas(plist_path, out)
        assert out.exists()
        assert result.count == 4

    def test_missing_texture_raises(self, tmp_path: Path) -> None:
        """Raises ToolError when no matching texture file is found."""
        plist = _make_plist(
            tmp_path / "orphan.plist",
            frames={"sprite.png": {"frame": "{{0,0},{32,32}}", "rotated": False}},
        )
        with pytest.raises(ToolError, match="No texture found"):
            extract_atlas(plist, tmp_path / "out")

    def test_emits_progress_events(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """EventBus receives progress and completed events."""
        plist_path, _ = atlas_pair
        bus = EventBus()
        progress: list[dict[str, Any]] = []
        completed: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: progress.append(kw))
        bus.subscribe("completed", lambda **kw: completed.append(kw))

        extract_atlas(plist_path, tmp_path / "ev_out", event_bus=bus)

        assert len(progress) == 4
        assert progress[0]["tool"] == "atlas_unpacker"
        assert len(completed) == 1

    def test_rotated_sprite(self, tmp_path: Path) -> None:
        """Correctly un-rotates a rotated sprite.

        The original sprite is 64 wide x 32 tall.  Packed 90 deg CW in the
        atlas it occupies 32 wide x 64 tall (packed_w=h=32, packed_h=w=64).
        In the plist (format 2), ``{w,h}`` are the *original* dimensions:
        ``{64,32}``.

        The packed region is placed at PIL position (0, 0) which, for a
        64 px tall atlas, corresponds to Cocos2d y = 0 (bottom-left origin)
        with packed_h = 64: ``y_pil = 64 - 0 - 64 = 0``.
        """
        atlas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        # Packed region: 32 wide x 64 tall at PIL (0, 0)
        rotated_block = Image.new("RGBA", (32, 64), (255, 0, 0, 255))
        atlas.paste(rotated_block, (0, 0))
        atlas.save(str(tmp_path / "rot.png"))

        plist = _make_plist(
            tmp_path / "rot.plist",
            frames={
                "wide.png": {
                    "frame": "{{0,0},{64,32}}",
                    "rotated": True,
                    "sourceSize": "{64,32}",
                    "offset": "{0,0}",
                },
            },
        )

        result = extract_atlas(plist, tmp_path / "rot_out")
        assert result.count == 1

        sprite = Image.open(result.images[0].path)
        # Original dimensions restored: 64x32
        assert sprite.size == (64, 32)

    def test_suffix_naming(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Suffix is appended before the .png extension."""
        plist_path, _ = atlas_pair
        out = tmp_path / "suffix_out"

        result = extract_atlas(plist_path, out, suffix="@2x")

        assert result.count == 4
        names = {img.path.name for img in result.images}
        assert "red@2x.png" in names
        assert "green@2x.png" in names
        assert "blue@2x.png" in names
        assert "yellow@2x.png" in names

    def test_suffix_empty_default(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Default empty suffix produces plain .png filenames."""
        plist_path, _ = atlas_pair
        out = tmp_path / "nosuffix_out"

        result = extract_atlas(plist_path, out)

        names = {img.path.name for img in result.images}
        assert "red.png" in names
        assert "green.png" in names


class TestProbeAtlas:
    """Tests for ``probe_atlas``."""

    def test_returns_metadata(self, atlas_pair: tuple[Path, Path]) -> None:
        """Returns frame count and metadata without extracting."""
        plist_path, png_path = atlas_pair

        info = probe_atlas(plist_path)

        assert info["frame_count"] == 4
        assert info["plist"] == plist_path.resolve()
        assert info["texture"] == png_path.resolve()
        assert len(info["frame_names"]) == 4

    def test_missing_texture(self, tmp_path: Path) -> None:
        """Returns None texture when file is missing."""
        plist = _make_plist(
            tmp_path / "orphan.plist",
            frames={"a.png": {"frame": "{{0,0},{16,16}}"}},
        )
        info = probe_atlas(plist)
        assert info["texture"] is None
        assert info["frame_count"] == 1
