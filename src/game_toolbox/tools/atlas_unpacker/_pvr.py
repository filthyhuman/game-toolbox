"""Parse PVR v2 / v3 texture data into PIL Images.

PVRv2 header (52 bytes, little-endian)::

    headerLength  height  width  numMipmaps  flags  dataLength
    bpp  bitmaskR  bitmaskG  bitmaskB  bitmaskA  pvrTag  numSurfaces

    pvrTag == 0x21525650  ('PVR!' in the file)
    Pixel format == flags & 0xFF, using OGL pixel-type constants:

        0x10  OGL_RGBA_4444   16 bpp
        0x11  OGL_RGBA_5551   16 bpp
        0x12  OGL_RGBA_8888   32 bpp
        0x13  OGL_RGB_565     16 bpp
        0x14  OGL_RGB_555     16 bpp
        0x15  OGL_RGB_888     24 bpp
        0x16  OGL_I_8          8 bpp
        0x17  OGL_AI_88       16 bpp
        0x18  OGL_PVRTC2       2 bpp (GPU-compressed)
        0x19  OGL_PVRTC4       4 bpp (GPU-compressed)
        0x1A  OGL_BGRA_8888   32 bpp
        0x1B  OGL_A_8          8 bpp

PVRv3 header (52 bytes + metadata, little-endian)::

    version(4) flags(4) pixelFormat(8) colorSpace(4) channelType(4)
    height(4) width(4) depth(4) numSurfaces(4) numFaces(4) numMipLevels(4) metaDataSize(4)
    version == 0x03525650
"""

import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from game_toolbox.core.exceptions import ToolError

# ---------------------------------------------------------------------------
# PVRv2 constants
# ---------------------------------------------------------------------------

_PVR2_TAG = 0x21525650  # 'PVR!' stored at byte offset 44
_PVR2_HEADER = "<13I"  # 13 x uint32 = 52 bytes

# fmt -> (bytes_per_pixel, PIL_mode, PIL_raw_mode | None)
# bytes_per_pixel == 0  -> PVRTC GPU-compressed
# PIL_raw_mode == None   -> decoded manually by a helper function
_PVR2_FMT: dict[int, tuple[int, str, str | None]] = {
    0x10: (2, "RGBA", None),  # OGL_RGBA_4444
    0x11: (2, "RGBA", None),  # OGL_RGBA_5551
    0x12: (4, "RGBA", "RGBA"),  # OGL_RGBA_8888
    0x13: (2, "RGB", "BGR;16"),  # OGL_RGB_565
    0x14: (2, "RGB", None),  # OGL_RGB_555  (manual)
    0x15: (3, "RGB", "RGB"),  # OGL_RGB_888
    0x16: (1, "L", "L"),  # OGL_I_8
    0x17: (2, "LA", "LA"),  # OGL_AI_88
    0x18: (0, "", None),  # OGL_PVRTC2  (PVRTC 2bpp)
    0x19: (0, "", None),  # OGL_PVRTC4  (PVRTC 4bpp)
    0x1A: (4, "RGBA", "BGRA"),  # OGL_BGRA_8888
    0x1B: (1, "L", "L"),  # OGL_A_8
}

# ---------------------------------------------------------------------------
# PVRv3 constants
# ---------------------------------------------------------------------------

_PVR3_MAGIC = 0x03525650


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_pvr(data: bytes, *, pvrtextool: Path | None = None) -> Image.Image:
    """Parse raw PVR bytes (v2 or v3) and return an RGBA PIL Image.

    Args:
        data: Raw bytes of the PVR file (after CCZ decompression if applicable).
        pvrtextool: Optional path to PVRTexToolCLI. Required only for
            PVRTC-compressed atlases.

    Returns:
        An RGBA PIL Image.

    Raises:
        ToolError: On unknown format or PVRTC when no conversion tool is available.
    """
    if len(data) < 52:
        msg = f"PVR data too short ({len(data)} bytes)"
        raise ToolError(msg)

    tag_v2: int = struct.unpack_from("<I", data, 44)[0]
    if tag_v2 == _PVR2_TAG:
        return _parse_v2(data, pvrtextool=pvrtextool)

    magic_v3: int = struct.unpack_from("<I", data, 0)[0]
    if magic_v3 == _PVR3_MAGIC:
        return _parse_v3(data, pvrtextool=pvrtextool)

    msg = f"Unknown PVR format — v2 tag @ 44: {tag_v2:#010x}, v3 magic @ 0: {magic_v3:#010x}"
    raise ToolError(msg)


def describe_pvr(data: bytes) -> dict[str, Any]:
    """Return a human-readable dict describing a PVR file without decoding pixels.

    Args:
        data: Raw bytes of the PVR file.

    Returns:
        A dict with version, dimensions, and format information.
    """
    tag_v2: int = struct.unpack_from("<I", data, 44)[0]
    if tag_v2 == _PVR2_TAG:
        _, height, width, _, flags, _, bpp = struct.unpack_from("<7I", data, 0)
        fmt = flags & 0xFF
        name = _PVR2_FMT.get(fmt, (0, f"unknown({fmt:#x})", None))[1] or "?"
        return {"version": 2, "width": width, "height": height, "format": fmt, "format_name": name, "bpp": bpp}

    magic_v3: int = struct.unpack_from("<I", data, 0)[0]
    if magic_v3 == _PVR3_MAGIC:
        _, _, pf_lo, pf_hi, _, _, height, width = struct.unpack_from("<8I", data, 0)
        return {"version": 3, "width": width, "height": height, "pf_lo": pf_lo, "pf_hi": pf_hi}

    return {"version": "unknown"}


# ---------------------------------------------------------------------------
# PVRv2 parser
# ---------------------------------------------------------------------------


def _parse_v2(data: bytes, *, pvrtextool: Path | None) -> Image.Image:
    """Parse a PVRv2 texture.

    Args:
        data: Raw PVR bytes.
        pvrtextool: Optional path to PVRTexToolCLI.

    Returns:
        An RGBA PIL Image.

    Raises:
        ToolError: On unknown pixel format or missing PVRTC tool.
    """
    (
        _header_len,
        height,
        width,
        _mipmaps,
        flags,
        _data_len,
        _bpp,
        _mr,
        _mg,
        _mb,
        _ma,
        _tag,
        _surfaces,
    ) = struct.unpack_from(_PVR2_HEADER, data, 0)

    fmt = flags & 0xFF

    if fmt not in _PVR2_FMT:
        msg = f"Unknown PVRv2 pixel format: {fmt} ({fmt:#04x}). Known formats: {sorted(_PVR2_FMT)}"
        raise ToolError(msg)

    bpp, mode, raw_mode = _PVR2_FMT[fmt]

    if bpp == 0:  # PVRTC
        return _pvrtc_fallback(data, pvrtextool, label=f"PVRv2 fmt={fmt:#04x}")

    pixel_data = data[52:]

    if fmt == 0x10:
        return _decode_rgba4444(pixel_data, width, height)
    if fmt == 0x11:
        return _decode_rgba5551(pixel_data, width, height)
    if fmt == 0x14:
        return _decode_rgb555(pixel_data, width, height)

    nbytes = width * height * bpp
    img = Image.frombytes(mode, (width, height), pixel_data[:nbytes], "raw", raw_mode or mode)
    return img.convert("RGBA")


# ---------------------------------------------------------------------------
# PVRv3 parser
# ---------------------------------------------------------------------------


def _parse_v3(data: bytes, *, pvrtextool: Path | None) -> Image.Image:
    """Parse a PVRv3 texture.

    Args:
        data: Raw PVR bytes.
        pvrtextool: Optional path to PVRTexToolCLI.

    Returns:
        An RGBA PIL Image.

    Raises:
        ToolError: On unsupported pixel format or missing PVRTC tool.
    """
    (
        _version,
        _flags,
        pf_lo,
        pf_hi,
        _color_space,
        _channel_type,
        height,
        width,
        _depth,
        _surfaces,
        _faces,
        _mip_levels,
        meta_size,
    ) = struct.unpack_from("<IIIIIIIIIIIIi", data, 0)

    header_size = 52 + meta_size
    pixel_data = data[header_size:]

    # pf_lo == 0 -> GPU-compressed (PVRTC, ETC ...)
    if pf_lo == 0:
        return _pvrtc_fallback(data, pvrtextool, label=f"PVRv3 pf_hi={pf_hi}")

    # Uncompressed: pf_lo = channel identifiers ('r','g','b','a') as bytes
    #               pf_hi = bits per channel as bytes
    channels = _v3_channels(pf_lo)
    bits = [(pf_hi >> (i * 8)) & 0xFF for i in range(4)]

    if all(b == 8 for b in bits[: len(channels)]):
        n = len(channels)
        nbytes = width * height * n
        mode = {4: "RGBA", 3: "RGB", 2: "LA", 1: "L"}.get(n, "RGBA")
        img = Image.frombytes(mode, (width, height), pixel_data[:nbytes])
        img = _reorder_v3(img, channels)
        return img.convert("RGBA")

    msg = f"Unsupported PVRv3 pixel format — pf_lo={pf_lo:#010x}, pf_hi={pf_hi:#010x}"
    raise ToolError(msg)


def _v3_channels(pf_lo: int) -> str:
    """Extract channel order string from PVRv3 pixel format low word.

    Args:
        pf_lo: The low 32 bits of the pixel format field.

    Returns:
        A string of channel characters, e.g. ``"rgba"``.
    """
    return "".join(chr((pf_lo >> (i * 8)) & 0xFF) for i in range(4) if (pf_lo >> (i * 8)) & 0xFF)


def _reorder_v3(img: Image.Image, order: str) -> Image.Image:
    """Re-arrange channel order if PVRv3 encoding differs from PIL default.

    Args:
        img: The PIL Image with bands in PVRv3 order.
        order: The channel order as a string (e.g. ``"bgra"``).

    Returns:
        The Image with bands in standard order.
    """
    bands = img.getbands()
    standard = "".join(b.lower() for b in bands)
    order = order.lower()
    if order == standard:
        return img
    split = img.split()
    mapping = {c: split[i] for i, c in enumerate(standard)}
    reordered = [mapping[c] for c in order if c in mapping]
    return Image.merge(img.mode, reordered)


# ---------------------------------------------------------------------------
# Packed-pixel decoders
# ---------------------------------------------------------------------------


def _decode_rgba4444(raw: bytes, w: int, h: int) -> Image.Image:
    """Decode OGL_RGBA_4444: 16-bit word, bits 15-12=R 11-8=G 7-4=B 3-0=A.

    Args:
        raw: Raw pixel data bytes.
        w: Image width in pixels.
        h: Image height in pixels.

    Returns:
        An RGBA PIL Image.
    """
    pixels = bytearray(w * h * 4)
    for i in range(w * h):
        word: int = struct.unpack_from("<H", raw, i * 2)[0]
        j = i * 4
        pixels[j] = ((word >> 12) & 0xF) * 17  # R -> 0..255
        pixels[j + 1] = ((word >> 8) & 0xF) * 17  # G
        pixels[j + 2] = ((word >> 4) & 0xF) * 17  # B
        pixels[j + 3] = ((word >> 0) & 0xF) * 17  # A
    return Image.frombytes("RGBA", (w, h), bytes(pixels))


def _decode_rgba5551(raw: bytes, w: int, h: int) -> Image.Image:
    """Decode OGL_RGBA_5551: 16-bit word, bits 15-11=R 10-6=G 5-1=B 0=A.

    Args:
        raw: Raw pixel data bytes.
        w: Image width in pixels.
        h: Image height in pixels.

    Returns:
        An RGBA PIL Image.
    """
    pixels = bytearray(w * h * 4)
    for i in range(w * h):
        word: int = struct.unpack_from("<H", raw, i * 2)[0]
        j = i * 4
        pixels[j] = ((word >> 11) & 0x1F) << 3  # R 5-bit
        pixels[j + 1] = ((word >> 6) & 0x1F) << 3  # G
        pixels[j + 2] = ((word >> 1) & 0x1F) << 3  # B
        pixels[j + 3] = (word & 0x1) * 255  # A 1-bit
    return Image.frombytes("RGBA", (w, h), bytes(pixels))


def _decode_rgb555(raw: bytes, w: int, h: int) -> Image.Image:
    """Decode OGL_RGB_555: 16-bit word, bits 14-10=R 9-5=G 4-0=B.

    Args:
        raw: Raw pixel data bytes.
        w: Image width in pixels.
        h: Image height in pixels.

    Returns:
        An RGBA PIL Image.
    """
    pixels = bytearray(w * h * 3)
    for i in range(w * h):
        word: int = struct.unpack_from("<H", raw, i * 2)[0]
        j = i * 3
        pixels[j] = ((word >> 10) & 0x1F) << 3  # R
        pixels[j + 1] = ((word >> 5) & 0x1F) << 3  # G
        pixels[j + 2] = ((word >> 0) & 0x1F) << 3  # B
    return Image.frombytes("RGB", (w, h), bytes(pixels)).convert("RGBA")


# ---------------------------------------------------------------------------
# PVRTC fallback via PVRTexToolCLI
# ---------------------------------------------------------------------------


def _pvrtc_fallback(pvr_data: bytes, tool: Path | None, label: str) -> Image.Image:
    """Decode PVRTC texture using external PVRTexToolCLI.

    Args:
        pvr_data: Complete PVR file bytes (header + pixel data).
        tool: Path to the PVRTexToolCLI binary.
        label: Human-readable label for error messages.

    Returns:
        An RGBA PIL Image.

    Raises:
        ToolError: If no tool is provided or the subprocess fails.
    """
    if not tool:
        msg = (
            f"PVRTC-compressed texture ({label}) cannot be decoded in pure Python.\n"
            "Install PVRTexToolCLI from Imagination Technologies and pass its path\n"
            "via --pvrtextool or the PVRTEXTOOL environment variable."
        )
        raise ToolError(msg)
    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "texture.pvr"
        out_path = Path(tmp) / "texture.png"
        in_path.write_bytes(pvr_data)
        try:
            subprocess.run(
                [str(tool), "-i", str(in_path), "-o", str(out_path), "-d", "r8g8b8a8"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            msg = f"PVRTexToolCLI failed for {label}: {exc.stderr.decode(errors='replace')}"
            raise ToolError(msg) from exc
        return Image.open(out_path).convert("RGBA")
