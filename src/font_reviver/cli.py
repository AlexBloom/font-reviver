from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from . import __version__
from .engine import scan_folder, convert_folder, atomic_json


def doctor(fontforge=None):
    from PIL import features
    from .formats import MAX_BYTES
    executable = fontforge or os.environ.get("FONTFORGE") or shutil.which("fontforge")
    scripting = False
    diagnostic = None
    if executable:
        try:
            result = subprocess.run([str(executable), "-lang=py", "-c", "import fontforge; print('font-reviver-ready')"],
                                    capture_output=True, text=True, errors="replace", timeout=15)
            scripting = result.returncode == 0 and "font-reviver-ready" in result.stdout
            if not scripting:
                diagnostic = (result.stdout + result.stderr)[-1200:]
        except (OSError, subprocess.TimeoutExpired) as error:
            diagnostic = str(error)
    return {"schema_version": 1, "version": __version__, "python": sys.version.split()[0],
            "platform": sys.platform, "fontforge": str(executable) if executable else None,
            "fontforge_python_scripting": scripting, "fontforge_diagnostic": diagnostic,
            "freetype": features.check("freetype2"), "native_macos_validation": sys.platform == "darwin",
            "max_file_bytes": MAX_BYTES, "ready_for_legacy_conversion": bool(scripting and features.check("freetype2"))}



def main(argv=None):
    parser = argparse.ArgumentParser(prog="font-reviver", description="revive your ancient, dead fonts")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    health = sub.add_parser("doctor", help="Check dependencies and platform capabilities")
    health.add_argument("--fontforge")
    for command in ["scan", "convert"]:
        child = sub.add_parser(command, help="Inspect without writing fonts" if command=="scan" else "Copy, extract and convert fonts")
        child.add_argument("source", type=Path)
        child.add_argument("--output", type=Path)
        child.add_argument("--no-archives", action="store_true")
        child.add_argument("--report", type=Path, help="Optional extra JSON report location")
        if command == "convert":
            child.add_argument("--jobs", type=int, default=4)
            child.add_argument("--fontforge")
    ui = sub.add_parser("ui", help="Launch the local browser app")
    ui.add_argument("--port", type=int, default=0)
    ui.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "ui":
            from .server import serve
            serve(port=args.port, open_browser=not args.no_browser)
            return 0
        if args.command == "doctor":
            result = doctor(args.fontforge)
        elif args.command == "scan":
            result = scan_folder(args.source, args.output, archives=not args.no_archives)
        else:
            def progress(event):
                if event["event"] == "converted":
                    print(f"Checked {event['completed']} / {event['total']} legacy conversion jobs", file=sys.stderr)
            result = convert_folder(args.source, args.output, archives=not args.no_archives,
                                    jobs=args.jobs, fontforge=args.fontforge, progress=progress)
        if getattr(args, "report", None):
            report_path = args.report.expanduser().resolve()
            if args.command in {"scan", "convert"}:
                src = args.source.expanduser().resolve()
                if report_path == src or src in report_path.parents:
                    raise ValueError("Extra report must be outside the original source folder")
            atomic_json(report_path, result)
        print(json.dumps(result, indent=2))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"schema_version": 1, "error": str(error) or "Interrupted"}), file=sys.stdout)
        return 130 if isinstance(error, KeyboardInterrupt) else 2
