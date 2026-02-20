"""Decompress Cocos2d CCZ files.

CCZ is a thin wrapper around a compressed payload (zlib, bzip2 or gzip).
The 16-byte header layout (all big-endian):

    Offset  Size  Field
    0       4     Magic: ``CCZ!`` (0x43 0x43 0x5A 0x21)
    4       2     Compression type (0=zlib, 1=bzip2, 2=gzip, 3=none)
    6       2     Version (typically 2)
    8       4     Reserved
    12      4     Uncompressed length in bytes
    16      ...   Compressed payload
"""

import bz2
import gzip
import io
import struct
import zlib

from game_toolbox.core.exceptions import ToolError

_MAGIC = b"CCZ!"
_HEADER_SIZE = 16

_COMP_ZLIB = 0
_COMP_BZIP2 = 1
_COMP_GZIP = 2
_COMP_NONE = 3


def decompress_ccz(data: bytes) -> bytes:
    """Decompress raw CCZ bytes and return the payload.

    Args:
        data: Raw bytes of the CCZ container.

    Returns:
        The decompressed payload bytes.

    Raises:
        ToolError: If the data is too short, has bad magic, or uses an
            unknown compression type.
    """
    if len(data) < _HEADER_SIZE:
        msg = f"Data too short to be a CCZ file ({len(data)} bytes)"
        raise ToolError(msg)
    if data[:4] != _MAGIC:
        msg = f"Not a CCZ file — magic bytes: {data[:4]!r}"
        raise ToolError(msg)

    comp_type: int = struct.unpack_from(">H", data, 4)[0]
    payload = data[_HEADER_SIZE:]

    if comp_type == _COMP_ZLIB:
        return zlib.decompress(payload)
    if comp_type == _COMP_BZIP2:
        return bz2.decompress(payload)
    if comp_type == _COMP_GZIP:
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as gz:
            return gz.read()
    if comp_type == _COMP_NONE:
        return payload

    msg = f"Unknown CCZ compression type: {comp_type}"
    raise ToolError(msg)


def is_ccz(data: bytes) -> bool:
    """Return True if the bytes start with the CCZ magic.

    Args:
        data: Raw bytes to inspect.

    Returns:
        Whether the data has the ``CCZ!`` magic header.
    """
    return data[:4] == _MAGIC
