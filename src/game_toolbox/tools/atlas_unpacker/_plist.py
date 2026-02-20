"""Parse Cocos2d texture-atlas .plist files.

Supports Cocos2d plist format 2 (TexturePacker default for Cocos2d) and
format 3 (extended, used by newer TexturePacker versions).

Frame dictionary keys used::

    frame / textureRect     — ``{x,y,w,h}`` or ``{{x,y},{w,h}}`` in the atlas
    rotated                 — bool; True means sprite was rotated 90 deg CW in atlas
    offset / spriteOffset   — ``{ox,oy}`` trim offset from original centre
    sourceSize / spriteSourceSize — ``{sw,sh}`` original (untrimmed) size
"""

import plistlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from game_toolbox.core.exceptions import ToolError


@dataclass
class AtlasSpriteFrame:
    """A single sprite frame entry from a Cocos2d texture atlas.

    Attributes:
        name: Filename key as it appears in the plist (e.g. ``farmer.png``).
        x: X position of this sprite in the atlas texture.
        y: Y position of this sprite in the atlas texture.
        w: Width of this sprite region in the atlas texture.
        h: Height of this sprite region in the atlas texture.
        rotated: True if the sprite was rotated 90 deg clockwise when packed.
        source_w: Original (untrimmed) width of the sprite.
        source_h: Original (untrimmed) height of the sprite.
        offset_x: Trim offset X from the original centre.
        offset_y: Trim offset Y from the original centre.
    """

    name: str
    x: int
    y: int
    w: int
    h: int
    rotated: bool
    source_w: int
    source_h: int
    offset_x: int
    offset_y: int

    @property
    def natural_w(self) -> int:
        """Width of the sprite in its natural (unrotated) orientation."""
        return self.h if self.rotated else self.w

    @property
    def natural_h(self) -> int:
        """Height of the sprite in its natural (unrotated) orientation."""
        return self.w if self.rotated else self.h


def load_plist(plist_path: Path) -> dict[str, AtlasSpriteFrame]:
    """Parse a Cocos2d .plist and return a dict mapping frame name to frame data.

    Args:
        plist_path: Path to the .plist file (binary or XML format both supported).

    Returns:
        Keys are the original frame names (e.g. ``farmer.png``).

    Raises:
        ToolError: If the plist cannot be read or parsed.
    """
    try:
        with plist_path.open("rb") as fh:
            data: dict[str, Any] = plistlib.load(fh)
    except Exception as exc:
        msg = f"Failed to read plist file '{plist_path}'"
        raise ToolError(msg) from exc

    frames_raw: dict[str, dict[str, Any]] = data.get("frames", {})
    result: dict[str, AtlasSpriteFrame] = {}

    for name, info in frames_raw.items():
        rotated = bool(info.get("rotated", False))

        # Frame rect: position + size in the atlas
        rect_str: str = info.get("frame") or info.get("textureRect") or ""
        x, y, w, h = _parse_rect(rect_str)

        # Source size (original untrimmed dimensions)
        src_str: str = info.get("sourceSize") or info.get("spriteSourceSize") or f"{{{w},{h}}}"
        sw, sh = _parse_point(src_str)

        # Trim offset from the original sprite centre
        off_str: str = info.get("offset") or info.get("spriteOffset") or "{0,0}"
        ox, oy = _parse_point(off_str)

        result[name] = AtlasSpriteFrame(
            name=name,
            x=x,
            y=y,
            w=w,
            h=h,
            rotated=rotated,
            source_w=sw,
            source_h=sh,
            offset_x=ox,
            offset_y=oy,
        )

    return result


def plist_metadata(plist_path: Path) -> dict[str, Any]:
    """Return the raw metadata dict from the plist.

    Contains the texture filename, atlas size, and format version.

    Args:
        plist_path: Path to the .plist file.

    Returns:
        The ``metadata`` section of the plist, or an empty dict if absent.

    Raises:
        ToolError: If the plist cannot be read or parsed.
    """
    try:
        with plist_path.open("rb") as fh:
            data: dict[str, Any] = plistlib.load(fh)
    except Exception as exc:
        msg = f"Failed to read plist file '{plist_path}'"
        raise ToolError(msg) from exc

    return dict(data.get("metadata", {}))


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _parse_rect(s: str) -> tuple[int, int, int, int]:
    """Parse a Cocos2d rect string into ``(x, y, w, h)``.

    Accepted formats::

        ``{{x,y},{w,h}}``   — Cocos2d format 2
        ``{x,y,w,h}``       — flat format
        ``x y w h``         — space-separated fallback

    Args:
        s: The raw rect string from the plist.

    Returns:
        A tuple of ``(x, y, width, height)``.

    Raises:
        ToolError: If the string cannot be parsed into four numbers.
    """
    nums = list(map(float, re.findall(r"[-\d.]+", s)))
    if len(nums) == 4:
        return int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])
    msg = f"Cannot parse rect string: {s!r} (extracted: {nums})"
    raise ToolError(msg)


def _parse_point(s: str) -> tuple[int, int]:
    """Parse a Cocos2d point/size string into ``(x, y)`` or ``(w, h)``.

    Args:
        s: The raw point string from the plist.

    Returns:
        A tuple of two integers.

    Raises:
        ToolError: If the string cannot be parsed into two numbers.
    """
    nums = list(map(float, re.findall(r"[-\d.]+", s)))
    if len(nums) == 2:
        return int(nums[0]), int(nums[1])
    msg = f"Cannot parse point string: {s!r} (extracted: {nums})"
    raise ToolError(msg)
