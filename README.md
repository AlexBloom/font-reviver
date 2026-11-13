# Font Reviver

**revive your ancient, dead fonts**

A local browser app, command-line tool, Python library, and portable agent skill for recovering legacy font collections. Point it at a folder on your desktop. Font Reviver copies modern fonts, extracts scalable suitcase fonts, converts recoverable PostScript outlines to OpenType, and builds a searchable gallery with **Expand all / Collapse all**.

No account, hosted service, agent subscription, or cloud upload is required. **No font files are included in this repository.**

## Quick start

Use Python **3.10 or newer** (3.11+ recommended). Install FontForge separately for legacy outline conversion. You do not need FontForge to inspect a collection or copy modern fonts.

### macOS

```sh
brew install python git fontforge
python3 -m venv ~/.venvs/font-reviver
source ~/.venvs/font-reviver/bin/activate
python -m pip install 'git+https://github.com/AlexBloom/font-reviver.git@main'
font-reviver doctor
font-reviver ui
```

The browser opens a local app. Paste a path such as `~/Desktop/Old Fonts`, inspect it, then choose **Revive fonts**. Leave the destination blank to create `~/Desktop/Old Fonts Revived`.

### Linux

On Debian/Ubuntu, install `python3-venv`, `fontforge`, and `python3-fontforge` using your package manager. Then create a virtual environment and install the package as above. FontForge builds must support Python scripting.

```sh
sudo apt-get install git python3-venv fontforge python3-fontforge
python3 -m venv ~/.venvs/font-reviver
. ~/.venvs/font-reviver/bin/activate
python -m pip install 'git+https://github.com/AlexBloom/font-reviver.git@main'
font-reviver ui
```

### Windows

Install Python 3.10+ and a FontForge build with Python scripting from the [FontForge project](https://fontforge.org/en-US/downloads/). In PowerShell:

```powershell
py -m venv "$HOME\.venvs\font-reviver"
& "$HOME\.venvs\font-reviver\Scripts\Activate.ps1"
python -m pip install 'git+https://github.com/AlexBloom/font-reviver.git@main'
$env:FONTFORGE = 'C:\Program Files (x86)\FontForgeBuilds\bin\fontforge.exe'
font-reviver doctor
font-reviver ui
```

Set `FONTFORGE` to the executable actually installed on your computer. Paths and FontForge packaging vary. The browser app and portable formats use the same engine on macOS, Linux, and Windows; native Mac resource forks require macOS or preservation as AppleDouble/DFONT/ZIP resources. See [platform notes](STATUS.md) for details.

## Fork and develop

Fork this repository on GitHub, then substitute **your** GitHub username in the clone URL:

```sh
git clone https://github.com/YOUR-USERNAME/font-reviver.git
cd font-reviver
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m pytest
font-reviver ui
```

Development happens on `dev`; `main` is the stable branch. You can pin an installation to a reviewed commit instead of following a branch.

## Command-line usage

```sh
# Inspect without writing fonts or changing originals.
font-reviver scan "$HOME/Desktop/Old Fonts" > scan.json

# Convert into a separate folder; JSON on stdout, progress on stderr.
font-reviver convert "$HOME/Desktop/Old Fonts" \
  --output "$HOME/Desktop/Revived Fonts" > conversion.json

# Choose the FontForge executable and limit parallel work.
font-reviver convert "$HOME/Desktop/Old Fonts" --jobs 2 \
  --fontforge /path/to/fontforge

# Start a loopback-only UI without opening a browser.
font-reviver ui --no-browser
```

Outputs:

- `Fonts/`: validated usable fonts, organized by source folders.
- `Gallery.html`: offline, searchable font specimens; **Expand all** opens all visible search matches. **Collapse all** closes them.
- `report.json`: versioned machine-readable inventory, warnings, validation, and source-to-output mapping.
- `results.csv`: human-readable file-by-file results.
- `.font-reviver/work/`: conversion intermediates and logs, outside the usable font directory.

Original files are never changed and fonts are never installed. A destination can be inside the source if explicitly supplied; it is excluded from scanning. The source itself and its ancestors cannot be destinations. Existing unrelated output files are not overwritten. Identical inputs and matching spacing data reuse validated conversion results; reruns avoid duplicate output files. Changed sources or distinct variants remain separate. If a process crashes, verify it stopped before removing `.font-reviver/lock`.

## Acceptable files and limitations

| Input | Treatment |
|---|---|
| `.otf`, `.ttf`, `.ttc`, `.otc` | Validate, render-check, and copy unchanged; collections remain collections. |
| `.pfb`, `.pfa`, Type 1 `.t1`, extensionless Mac LWFN printer fonts | Convert recoverable scalable outlines to CFF OpenType `.otf`. Signatures and resource contents determine the format. |
| `.suit`, `.dfont`, `.bmap`, `.screen`, `.tt`, extensionless suitcases | Extract `sfnt` scalable fonts or convert `POST` outlines when present. Bitmap-only companions are reported, not traced or invented. |
| `.afm`, `.pfm` | Spacing/kerning companions; require matching outlines. AFM internal FontName or matching companion filenames are used. Metrics alone cannot become a font. |
| `.zip`, AppleDouble `._` sidecars | Inspect bounded ZIPs and preserve embedded resource forks. No paths are extracted outside the output workspace. Nested ZIPs are not recursively opened. |
| `.sit`, `.fog`, `.bin` MacBinary, `.hqx` BinHex | Report for separate extraction/export; not directly supported. |

Type 3/data-fork-referenced PostScript fonts are attempted only when their resource structure identifies font outlines; support varies by FontForge. Some malformed cleartext Type 1 metadata can be escaped losslessly to make the parser accept it. Encrypted outline bytes are unchanged by that repair.

Missing outlines, lost resource forks, corrupted fonts, procedural fonts, bitmap-only files, and unsupported archives may not be recoverable. **Legacy FOND suitcase kerning is not imported.** Converting does not create missing Unicode mappings, ligatures, or other modern features. Limited character sets and symbol encodings may need a glyph palette. Collections may show only their first face in browser previews, although every face is validated.

Checks include scalable font table parsing, FreeType rendering, FontForge glyph/advance-width comparisons for conversions, and native CoreText recognition on macOS. Existing checksum or optional-table warnings are recorded without changing original modern font bytes. These checks **do not guarantee** exact appearance, hinting, kerning, compatibility with every application, or Apple's Font Book validation. Compare results in the applications you use.

### Sync and resource-fork preservation

Make cloud folders available offline first. Font Reviver skips recognized macOS dataless files, legacy Dropbox placeholders, and Windows offline/recall-on-data files. Other cloud providers may expose placeholders differently; empty or unreadable files are reported. No downloads are forced.

A classic Mac file can legitimately have a zero-byte data fork and still contain an intact resource fork. Keep whole font families together. Use a Mac-aware archive/transfer process that preserves forks or AppleDouble sidecars. Copying extensionless zero-byte data forks alone onto another filesystem can permanently discard the outlines.

## Use with any agent or UI

The engine has no agent-specific dependencies. Agents can invoke the executable or `python -m font_reviver`, parse JSON, import the Python API, or use the local HTTP adapter. No MCP server is required.

```python
from font_reviver.engine import scan_folder, convert_folder

plan = scan_folder("~/Desktop/Old Fonts")
result = convert_folder("~/Desktop/Old Fonts", "~/Desktop/Revived Fonts", jobs=4)
print(result["summary"])
```

See [the interface contract](docs/INTERFACES.md), [report schema](docs/report.schema.json), and [portable agent skill](skills/font-reviver/SKILL.md).

To install the skill, first install the CLI, then copy `skills/font-reviver/` into your agent's skill directory. For example, Codex uses `~/.codex/skills/font-reviver`; Claude Code commonly uses `~/.claude/skills/font-reviver`. Other agents can read `SKILL.md` directly or use the CLI contract. The optional `agents/openai.yaml` supplies display metadata only. The included `scripts/run.py` adapter also works when an agent has not activated the app environment: it uses an installed CLI, a linked checkout’s `.venv`, or the current Python module. A skill does not bundle or install fonts.

Example request: “Use Font Reviver to inspect `~/Desktop/Old Fonts`, convert the recoverable files into a separate folder, and show the gallery and exceptions.”

## Licensing and legal disclaimer

**You are responsible for obeying font licensing terms, copyright, and all applicable laws.** Possession of a font file does not necessarily grant permission to convert, modify, use, embed, share, upload, or redistribute it. Check the license and obtain the rights or permission required for your intended use. Conversion does not remove restrictions or transfer ownership. Do not commit converted fonts to a public repository unless you have the necessary redistribution rights.

Font Reviver's own source code is MIT-licensed. That license **does not cover any fonts you process**. FontForge and other separately installed dependencies retain their own licenses. This software is provided without warranty, including any warranty that a font can be recovered or that results preserve its original behavior. This notice is not legal advice.

For implementation background: [FontForge Python scripting](https://fontforge.org/docs/scripting/python/fontforge.html), [fontTools resource-fork support](https://fonttools.readthedocs.io/en/latest/misc/macRes.html), and [fontTools collections](https://fonttools.readthedocs.io/en/stable/ttLib/ttCollection.html).
