from __future__ import annotations
import ctypes
import io
import os
import sys
from pathlib import Path
from fontTools.ttLib import TTFont, TTCollection
from fontTools.ttLib.sfnt import calcChecksum
from PIL import ImageFont


def macos_recognizes(path: Path) -> bool | None:
    if sys.platform != "darwin":
        return None
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ct = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_ubyte]
    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
    cf.CFArrayGetCount.restype = ctypes.c_long
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    ct.CTFontManagerCreateFontDescriptorsFromURL.argtypes = [ctypes.c_void_p]
    ct.CTFontManagerCreateFontDescriptorsFromURL.restype = ctypes.c_void_p
    encoded = os.fsencode(path.resolve())
    url = cf.CFURLCreateFromFileSystemRepresentation(None, encoded, len(encoded), False)
    if not url:
        return False
    array = None
    try:
        array = ct.CTFontManagerCreateFontDescriptorsFromURL(url)
        return bool(array and cf.CFArrayGetCount(array) > 0)
    finally:
        if array:
            cf.CFRelease(array)
        cf.CFRelease(url)


def validate(path: Path) -> dict:
    data = path.read_bytes()
    fonts = TTCollection(io.BytesIO(data)).fonts if data[:4] == b"ttcf" else [TTFont(io.BytesIO(data), checkChecksums=0)]
    faces, warnings = [], []
    try:
        for idx, font in enumerate(fonts):
            for tag in font.keys():
                try:
                    font[tag]
                except Exception as error:
                    if tag in {"head", "hhea", "hmtx", "maxp", "cmap", "name", "glyf", "loca", "CFF ", "CFF2"}:
                        raise ValueError(f"Invalid {tag} table: {error}") from error
                    warnings.append(f"Optional {tag} table could not be decoded: {error}")
            if not any(t in font for t in ("glyf", "CFF ", "CFF2")):
                raise ValueError("No scalable outline table")
            if len(font.getGlyphOrder()) < 2:
                raise ValueError("No usable output glyphs")
            for tag, entry in font.reader.tables.items():
                block = font.reader[tag]
                if tag == "head":
                    block = block[:8] + b"\0\0\0\0" + block[12:]
                if calcChecksum(block) != entry.checkSum:
                    warnings.append(f"Checksum mismatch in {tag}; original bytes preserved")
            renderer = ImageFont.truetype(str(path), 32, index=idx)
            renderer.getmask("ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789 AV To fi fl")
            cmap = font.getBestCmap() or {}
            if not cmap:
                warnings.append("No Unicode character map; use a glyph palette and inspect encoding")
            faces.append({"name": font["name"].getDebugName(4) or path.stem,
                          "postscript_name": font["name"].getDebugName(6),
                          "glyphs": len(font.getGlyphOrder()), "unicode_characters": len(cmap), "face_index": idx})
    finally:
        for font in fonts:
            font.close()
    native = macos_recognizes(path)
    if native is False:
        raise ValueError("macOS CoreText did not recognize this font")
    return {"faces": faces, "warnings": list(dict.fromkeys(warnings)),
            "rendered": True, "macos_recognized": native}
