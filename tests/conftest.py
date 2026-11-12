from pathlib import Path
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


def make_font(path: Path, family="Reviver Test", width=600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fb = FontBuilder(1000, isTTF=True)
    order = [".notdef", "space", "A", "V", "B"]
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({32: "space", 65: "A", 86: "V", 66: "B"})
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        if name != "space":
            pen.moveTo((80, 0)); pen.lineTo((300, 700)); pen.lineTo((520, 0)); pen.closePath()
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (300 if n == "space" else width, 0) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family+"-Regular",
                       "fullName": family+" Regular", "psName": family.replace(" ", "")+"-Regular"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost(); fb.setupMaxp(); fb.save(path)
    return path


@pytest.fixture
def font_factory():
    return make_font
