"""Runs inside FontForge's Python interpreter, not the app's interpreter."""
import json
import sys
import fontforge


def main():
    source, target, result = sys.argv[1:4]
    font = fontforge.open(source)
    metadata = {"fontname": font.fontname, "family": font.familyname,
                "metrics_imported": [], "warnings": []}
    for metric in sys.argv[4:]:
        font.mergeKern(metric)
        metadata["metrics_imported"].append(metric)
    widths = {g.glyphname: g.width for g in font.glyphs() if g.isWorthOutputting()}
    if not widths or not any(len(g.foreground) or g.references for g in font.glyphs()):
        raise ValueError("No scalable glyph outlines decoded")
    metadata.update(glyphs=len(widths), source_validation_flags=font.validate())
    font.generate(target, flags=("opentype", "round"))
    font.close()
    font = fontforge.open(target)
    after = {g.glyphname: g.width for g in font.glyphs() if g.isWorthOutputting()}
    changed = [n for n, w in widths.items() if n not in after or abs(w-after[n]) > 1]
    metadata["output_validation_flags"] = font.validate()
    font.close()
    if changed:
        raise ValueError("Changed or missing glyph advances: " + repr(changed))
    metadata["width_changes"] = []
    with open(result, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle)


if __name__ == "__main__":
    main()
