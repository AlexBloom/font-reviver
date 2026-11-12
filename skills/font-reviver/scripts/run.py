#!/usr/bin/env python3
"""Portable adapter for agents whose shell has not activated the app environment."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[3]
executable = os.environ.get("FONT_REVIVER_EXECUTABLE") or shutil.which("font-reviver")
if not executable:
    candidate = root / ".venv" / ("Scripts/font-reviver.exe" if os.name == "nt" else "bin/font-reviver")
    if candidate.is_file():
        executable = str(candidate)
if executable:
    os.execv(executable, [executable] + sys.argv[1:])
if importlib.util.find_spec("font_reviver"):
    os.execv(sys.executable, [sys.executable, "-m", "font_reviver"] + sys.argv[1:])
print(json.dumps({"schema_version": 1, "error": "Install Font Reviver using the repository README, activate its environment, or set FONT_REVIVER_EXECUTABLE to the installed CLI path."}))
raise SystemExit(2)
