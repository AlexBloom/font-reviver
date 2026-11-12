# Status

Font Reviver 0.1.0 is implemented as a local browser app, CLI, Python library and portable Agent Skills package.

## Verified locally

- 12 automated checks passed on macOS with Python 3.15, including synthetic modern-font copying, collections, AppleDouble/resource extraction, ZIP path rejection, placeholder and symlink handling, non-destructive collisions, cache repeatability, FontForge conversion, JSON schema and HTTP authentication/result allowlisting.
- Wheel and source distribution build successfully.
- Skill frontmatter/name validation passed.
- Real resource-fork and malformed-header recovery checked using private local inputs kept outside this repository. No fonts or collection reports ship here.

## Platform scope

macOS has been run locally, including native CoreText recognition. Linux/Windows CI jobs are prepared in `docs/ci.example.yml`, not activated. The current GitHub OAuth login lacks the `workflow` scope, so the app is published without an active Actions workflow. Copy the template to `.github/workflows/ci.yml` with an appropriately authorized GitHub session to enable it. Check actual runner results before describing those platforms as verified. Native Mac resource forks are platform-specific; AppleDouble/DFONT/ZIP preservation enables portable extraction.

## Local use

From a clone: create `.venv`, install `.[dev]`, then run `.venv/bin/font-reviver ui` (Windows: `.venv\Scripts\font-reviver.exe ui`). It binds only to localhost and prints a token-bearing URL. No production hosting, domain, deployment or external service is configured.

## Known limits

Legacy FOND kerning, missing resource forks, unsupported archives, procedural fonts, corrupted fonts and incomplete character coverage require review. Existing modern formats are preserved, not upgraded. Native recognition and parser checks do not guarantee exact application behavior.

## Browser verification

The local UI completed a two-font synthetic collection run. Expand all opened both specimens; Collapse all closed both. Restart the local app with `.venv/bin/font-reviver ui --port 8765`. Session tokens and temporary collection paths are intentionally not recorded here. The skill is discoverable through a local skill-directory link on the development machine.
