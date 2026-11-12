from __future__ import annotations
import html
import json
from pathlib import Path
from urllib.parse import quote

STYLE = """
:root{color-scheme:light;--ink:#24201d;--paper:#f4f0e7;--accent:#ae3a23}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{max-width:1150px;margin:auto;padding:48px 24px}h1{font:700 clamp(44px,7vw,76px)/1.02 Georgia,serif;letter-spacing:-.045em;margin:18px 0}
.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.16em;color:var(--accent);font-weight:750}.tagline{font:italic 24px Georgia,serif}
button,a.button{border:1px solid var(--ink);padding:11px 17px;border-radius:5px;background:transparent;color:inherit;font:inherit;cursor:pointer;text-decoration:none}
button:hover,a.button:hover{background:#e9e1d4}button:disabled{opacity:.45;cursor:wait}input{border:1px solid #b9ad9e;border-radius:5px;padding:12px;font:inherit;background:white;max-width:100%;width:100%}
.controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:25px 0}.controls input{flex:1;min-width:220px}.muted,small{color:#6d635a}small{font-size:12px}
details{border-top:1px solid #cbbfb1;padding:20px 0}summary{cursor:pointer;list-style-position:outside;margin-left:20px;font-size:18px;font-weight:600}
.sample{font-size:clamp(24px,4vw,40px);line-height:1.35;overflow-wrap:anywhere;margin:20px 0}.path{font-size:12px;overflow-wrap:anywhere}
a{color:var(--accent)}.notice{background:#e9e1d4;padding:16px;border-left:3px solid var(--accent);margin:24px 0}footer{margin-top:40px;font-size:13px;color:#6d635a}
[hidden]{display:none!important}:focus-visible{outline:3px solid #3b728a;outline-offset:3px}
"""


def gallery_script():
    return """document.getElementById('expand-all').addEventListener('click',()=>{
 document.querySelectorAll('details[data-font]:not([hidden])').forEach(d=>d.open=true)});
document.getElementById('collapse-all').addEventListener('click',()=>{
 document.querySelectorAll('details[data-font]').forEach(d=>d.open=false)});
document.getElementById('search').addEventListener('input',e=>{
 let n=0;document.querySelectorAll('details[data-font]').forEach(d=>{
 d.hidden=!d.dataset.search.includes(e.target.value.toLowerCase());if(!d.hidden)n++});
 document.getElementById('visible-count').textContent=n+' font files shown'});"""


def write_gallery(report: dict, target: Path):
    cards, faces = [], []
    for row in report["records"]:
        for item in row["fonts"]:
            if "output" not in item:
                continue
            idx = len(cards)
            names = [f["name"] for f in item["validation"]["faces"]]
            name = " / ".join(names)
            url = quote(item["output"], safe="/")
            faces.append(f'@font-face{{font-family:revived{idx};src:url("{url}")}}')
            search = html.escape((name + " " + row["source"]).lower(), quote=True)
            warnings = item["validation"].get("warnings", [])
            warning = '<div class="notice">' + html.escape("; ".join(warnings)) + '</div>' if warnings else ''
            collection_note = '<small>Collection: browser preview may show only the first face. All faces were checked.</small>' if len(names)>1 else ''
            cards.append(f'''<details data-font data-search="{search}"><summary>{html.escape(name)} <small> · {html.escape(item['status'])}</small></summary>
<div class="path">{html.escape(row['source'])}</div>{collection_note}
<div class="sample" style="font-family:revived{idx}">The quick brown fox jumps over the lazy dog.</div>
<div class="sample" style="font-family:revived{idx}">ABCDEFGHIJKLMNOPQRSTUVWXYZ</div>
<div class="sample" style="font-family:revived{idx}">abcdefghijklmnopqrstuvwxyz 0123456789 AV AW To Ta fi fl !? &amp; @</div>
{warning}<a href="{url}">Open font file</a></details>''')
    summary = report["summary"]
    title = "Font Reviver — Gallery"
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{STYLE}{''.join(faces)}</style><main><div class="eyebrow">Font Reviver · your recovered collection</div>
<h1>Back from the dead.</h1><p class="tagline">revive your ancient, dead fonts</p>
<p>{len(cards)} included font files · {summary['converted']} converted · {summary['copied']+summary['extracted']} copied or extracted</p>
<div class="notice">Originals remain untouched. Fonts have not been installed. Check spacing, glyph coverage and appearance in your design app. Legacy FOND suitcase kerning is not imported. You are responsible for font licensing.</div>
<div class="controls"><input id="search" type="search" placeholder="Search font names or folders" aria-label="Search font names or folders"><button id="expand-all" type="button">Expand all</button><button id="collapse-all" type="button">Collapse all</button></div>
<p id="visible-count" class="muted" aria-live="polite">{len(cards)} font files shown</p>
{''.join(cards) if cards else '<p>No usable fonts yet. See the report for missing outlines, placeholders or unsupported formats.</p>'}
<footer><a href="report.json">JSON report</a> · <a href="results.csv">File-by-file results</a><p>Built locally with Font Reviver. No fonts are uploaded.</p></footer></main>
<script>{gallery_script()}</script></html>'''
    target.write_text(page, encoding="utf-8")
