# Status

Font Reviver 0.1.0 is implemented as a local browser app, CLI, Python library and portable Agent Skills package.

## Verified locally

- 13 automated checks passed on macOS with Python 3.15, including synthetic modern-font copying, collections, AppleDouble/resource extraction, ZIP path rejection, placeholder and symlink handling, non-destructive collisions, cache repeatability, FontForge conversion, JSON schema and HTTP authentication/result allowlisting.
- Wheel and source distribution build successfully.
- Skill frontmatter/name validation passed.
- Real resource-fork and malformed-header recovery checked using private local inputs kept outside this repository. No fonts or collection reports ship here.

## Platforms and local use

The app has been verified on macOS, including native CoreText recognition. Installation instructions are also provided for Linux and Windows. Native Mac resource forks are platform-specific; AppleDouble, DFONT and supported ZIP preservation enable extraction on other filesystems.

From a clone, create `.venv`, install `.[dev]`, and run `.venv/bin/font-reviver ui` (Windows: `.venv\Scripts\font-reviver.exe ui`). The app runs on localhost. The project includes a local browser app, CLI, Python library, JSON API, and portable agent skill.

## Website

The installation page is maintained in `docs/` for GitHub Pages. It introduces the app, command line, agent skill and fork-and-develop paths, with macOS, Linux and Windows setup instructions.

## Known limits

Legacy FOND kerning, missing resource forks, unsupported archives, procedural fonts, corrupted fonts and incomplete character coverage require review. Existing modern formats are preserved, not upgraded. Native recognition and parser checks do not guarantee exact application behavior.

## Browser verification

The local UI completed a two-font synthetic collection run. Expand all opened both specimens; Collapse all closed both. Restart the local app with `.venv/bin/font-reviver ui --port 8765`. Session tokens and temporary collection paths are intentionally not recorded here. The skill is discoverable through a local skill-directory link on the development machine.
