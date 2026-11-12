"""Resource forks, containers, placeholders, and lossless Type 1 header repair."""
from __future__ import annotations
import ctypes
import io
import os
import struct
import sys
from pathlib import Path
from fontTools.misc.macRes import ResourceReader

MODERN = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")
FONT_EXTENSIONS = {".otf", ".ttf", ".ttc", ".otc", ".pfb", ".pfa", ".t1", ".tt",
                   ".suit", ".dfont", ".bmap", ".screen", ".truetype"}
MAX_BYTES = 128 * 1024 * 1024


def online_only(path: Path) -> bool:
    st = path.stat()
    if getattr(st, "st_flags", 0) & 0x40000000:  # macOS SF_DATALESS
        return True
    if getattr(st, "st_file_attributes", 0) & (0x1000 | 0x400000):
        return True  # Windows OFFLINE / RECALL_ON_DATA_ACCESS
    if sys.platform == "darwin":
        lib = ctypes.CDLL(None, use_errno=True)
        lib.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                                ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
        lib.getxattr.restype = ctypes.c_ssize_t
        return lib.getxattr(os.fsencode(path), b"com.dropbox.placeholder", None, 0, 0, 0) >= 0
    return False


def bounded_read(path: Path) -> bytes:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("File exceeds the 128 MiB per-file limit")
    with path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds the 128 MiB per-file limit")
    return data


def apple_double(data: bytes) -> bytes | None:
    if len(data) < 26 or data[:4] != b"\x00\x05\x16\x07":
        return None
    count = struct.unpack_from(">H", data, 24)[0]
    if 26 + count * 12 > len(data):
        raise ValueError("Truncated AppleDouble table")
    for i in range(count):
        kind, offset, size = struct.unpack_from(">III", data, 26 + i * 12)
        if offset + size > len(data):
            raise ValueError("Truncated AppleDouble resource")
        if kind == 2:
            return data[offset:offset+size]
    return None


def resource_fork(path: Path) -> bytes | None:
    if sys.platform == "darwin":
        try:
            data = bounded_read(Path(str(path) + "/..namedfork/rsrc"))
            if data:
                return data
        except (OSError, ValueError):
            pass
    sidecar = path.with_name("._" + path.name)
    if sidecar.is_file() and not sidecar.is_symlink() and not online_only(sidecar):
        return apple_double(bounded_read(sidecar))
    return None


def pfb_from_resources(resources, data_fork: bytes = b"") -> bytes:
    chunks = []
    for resource in sorted(resources, key=lambda r: r.id):
        if len(resource.data) < 2 or resource.data[1] != 0:
            raise ValueError("Corrupt POST resource header")
        kind, content = resource.data[0], resource.data[2:]
        if kind in (1, 2):
            if chunks and chunks[-1][0] == kind:
                chunks[-1][1].extend(content)
            else:
                chunks.append((kind, bytearray(content)))
        elif kind in (3, 5):
            break
        elif kind == 4:
            if not data_fork.startswith(b"%!PS"):
                raise ValueError("POST resource references missing data-fork outlines")
            return data_fork  # Some Type 3 fonts; FontForge support varies.
        elif kind != 0:
            raise ValueError("Unsupported POST resource code")
    if not chunks:
        raise ValueError("No Type 1 outline chunks")
    return b"".join(bytes([128, k]) + struct.pack("<I", len(b)) + b for k, b in chunks) + b"\x80\x03"


def inspect(data: bytes, resource: bytes | None, suffix: str):
    """Return (payloads, status, warnings), using signatures rather than suffixes."""
    if data[:4] in MODERN:
        return [("modern", "", data)], "ready", []
    if data[:2] == b"\x80\x01" or data.startswith((b"%!PS-AdobeFont", b"%!FontType1")):
        return [("type1", "", data)], "ready", []
    reader = None
    warnings = []
    try:
        if resource:
            reader = ResourceReader(io.BytesIO(resource))
        elif data and suffix in {".dfont", ".suit", ".tt", ".bmap", ""}:
            try:
                reader = ResourceReader(io.BytesIO(data))
            except Exception:
                pass
        if reader is not None:
            payloads = [("extracted", str(r.id), r.data) for r in reader.get("sfnt", [])]
            if "POST" in reader:
                payloads.append(("type1", "", pfb_from_resources(reader["POST"], data)))
            if payloads:
                return payloads, "ready", warnings
            if any(t in reader for t in ("FOND", "NFNT", "FONT")):
                return [], "bitmap_companion", warnings
    finally:
        if reader is not None:
            reader.close()
    if suffix in {".afm", ".pfm"}:
        return [], "metrics_companion", warnings
    if suffix in {".sit", ".fog", ".bin", ".hqx"}:
        return [], "unsupported_container", warnings
    if suffix in FONT_EXTENSIONS or not data:
        return [], "needs_review", ["No recognized scalable outlines; resource forks may be missing"]
    return [], "supporting_file", warnings


def escape_header(data: bytes) -> bytes | None:
    """Equivalent octal string literals; never alter encrypted outline segments."""
    if not data.startswith(b"\x80\x01"):
        return None
    pos, parts, changed = 0, [], False
    while pos < len(data):
        if pos+2 > len(data) or data[pos] != 128:
            raise ValueError("Invalid PFB marker")
        kind = data[pos+1]
        pos += 2
        if kind == 3:
            parts.append(b"\x80\x03")
            break
        if kind not in (1, 2) or pos+4 > len(data):
            raise ValueError("Invalid PFB segment")
        length = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if pos+length > len(data):
            raise ValueError("Truncated PFB segment")
        segment = data[pos:pos+length]
        pos += length
        if not parts and kind == 1:
            output = bytearray()
            depth, escaped, comment = 0, False, False
            for c in segment:
                if comment:
                    output.append(c)
                    if c in (10, 13):
                        comment = False
                    continue
                if escaped:
                    output.append(c)
                    escaped = False
                    continue
                if depth and c == 92:
                    output.append(c)
                    escaped = True
                    continue
                if not depth and c == 37:
                    comment = True
                    output.append(c)
                    continue
                if c == 40:
                    depth += 1
                elif c == 41 and depth:
                    depth -= 1
                if depth and (c < 32 or c > 126):
                    output.extend(("\\%03o" % c).encode())
                else:
                    output.append(c)
            changed = bytes(output) != segment
            segment = bytes(output)
        parts.append(bytes([128, kind]) + struct.pack("<I", len(segment)) + segment)
    return b"".join(parts) if changed else None
