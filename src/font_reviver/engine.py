"""Portable conversion service. No agent SDK, cloud account, or shell interpolation."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from collections import Counter
import csv
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from . import __version__
from .formats import (MODERN, MAX_BYTES, inspect, online_only, bounded_read,
                      resource_fork, apple_double, escape_header)
from .validation import validate

SCHEMA_VERSION = 1


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".reviver-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=True)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def roots(source, output=None):
    src = Path(source).expanduser().resolve(strict=True)
    if not src.is_dir():
        raise ValueError("Source must be a folder")
    dest = Path(output).expanduser().resolve() if output else src.with_name(src.name + " Revived")
    if dest == src or dest in src.parents:
        raise ValueError("Output must not be the source folder or one of its ancestors")
    return src, dest


@dataclass
class Source:
    name: str
    relative: Path
    data: bytes = b""
    resource: bytes | None = None
    physical: Path | None = None
    companions: list | None = None
    status: str | None = None
    error: str | None = None


def _metrics(folder: Path):
    result = []
    for p in sorted(folder.iterdir()):
        if p.is_symlink() or p.suffix.lower() not in {".afm", ".pfm"} or not p.is_file():
            continue
        try:
            if not online_only(p):
                result.append((p.name, bounded_read(p)))
        except (OSError, ValueError):
            continue
    return result


def _safe_member(name):
    p = PurePosixPath(name)
    return (not p.is_absolute() and not PureWindowsPath(name).drive and ".." not in p.parts
            and "\\" not in name and "\x00" not in name)


def _archive(path, rel):
    yield Source(str(rel), rel, status="archive_inspected")
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > 10000:
                raise ValueError("ZIP exceeds the 10,000-entry limit")
            blobs, total = {}, 0
            for entry in infos:
                if entry.is_dir():
                    continue
                name = entry.filename
                if not _safe_member(name) or stat.S_ISLNK(entry.external_attr >> 16):
                    yield Source(str(rel) + "!/" + name, rel, status="skipped_archive_entry", error="Unsafe archive path or symlink")
                    continue
                total += entry.file_size
                if entry.file_size > MAX_BYTES or total > 256 * 1024 * 1024:
                    raise ValueError("ZIP exceeds the 128 MiB entry / 256 MiB total expanded limit")
                with z.open(entry) as handle:
                    blob = handle.read(MAX_BYTES + 1)
                if len(blob) > MAX_BYTES:
                    raise ValueError("Expanded ZIP entry exceeds limit")
                blobs[name] = blob
            for name, data in blobs.items():
                member = PurePosixPath(name)
                if "__MACOSX" in member.parts or member.name.startswith("."):
                    continue
                sidecar = str(member.parent / ("._" + member.name))
                companion = blobs.get("__MACOSX/" + sidecar, blobs.get(sidecar, b""))
                resource = apple_double(companion) if companion else None
                siblings = [(PurePosixPath(k).name, v) for k, v in blobs.items()
                            if PurePosixPath(k).parent == member.parent and PurePosixPath(k).suffix.lower() in {".afm", ".pfm"}]
                output_rel = rel.parent / (rel.stem + " [archive]") / Path(name)
                yield Source(str(rel) + "!/" + name, output_rel, data, resource, companions=siblings)
    except Exception as error:
        yield Source(str(rel), rel, status="needs_review", error=f"ZIP: {error}")


def sources(src: Path, output: Path, archives=True):
    metrics = {}
    for folder, dirs, files in os.walk(src, followlinks=False):
        base = Path(folder)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".")
                         and not (base/d).is_symlink() and (base/d).resolve() != output)
        for name in sorted(files):
            if name.startswith("."):
                continue
            path = base/name
            rel = path.relative_to(src)
            try:
                if path.is_symlink():
                    yield Source(str(rel), rel, status="skipped_symlink")
                    continue
                if online_only(path):
                    yield Source(str(rel), rel, status="skipped_online_only")
                    continue
                data = bounded_read(path)
                if archives and data[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
                    yield from _archive(path, rel)
                    continue
                # A broken auxiliary fork must not prevent copying a valid modern data fork.
                resource = None if data[:4] in MODERN else resource_fork(path)
                if base not in metrics:
                    metrics[base] = _metrics(base)
                yield Source(str(rel), rel, data, resource, path, metrics[base])
            except Exception as error:
                yield Source(str(rel), rel, status="needs_review", error=str(error))


def _row(source):
    row = {"source": source.name, "status": source.status or "ready", "fonts": [], "warnings": []}
    if source.error:
        row["error"] = source.error
    if source.status:
        return row, []
    try:
        payloads, status, warnings = inspect(source.data, source.resource, source.relative.suffix.lower())
        row.update(status=status, warnings=warnings)
        if source.relative.name.startswith("Comments about ") and not payloads:
            row["status"] = "supporting_file"
        for kind, rid, data in payloads:
            identity = digest((source.name + "\0" + kind + "\0" + rid).encode())
            row["fonts"].append({"id": identity, "kind": kind, "resource_id": rid,
                                  "sha256": digest(data), "status": "ready"})
        return row, payloads
    except Exception as error:
        row.update(status="needs_review", error=str(error))
        return row, []


def summarize(records):
    states = Counter(f["status"] for row in records for f in row["fonts"])
    return {"source_entries": len(records), "included_files": sum("output" in f for r in records for f in r["fonts"]),
            "converted": states["converted"], "copied": states["copied"], "extracted": states["extracted"],
            "skipped_online_only": sum(r["status"] == "skipped_online_only" for r in records),
            "review_entries": sum(r["status"] in {"needs_review", "unsupported_container"}
                                  or any(f["status"] in {"needs_review", "missing_fontforge"} for f in r["fonts"]) for r in records)}


def scan_folder(source, output=None, *, archives=True):
    src, dest = roots(source, output)
    records = [_row(item)[0] for item in sources(src, dest, archives)]
    return {"schema_version": SCHEMA_VERSION, "version": __version__, "operation": "scan",
            "source_root": str(src), "output_root": str(dest), "summary": summarize(records), "records": records}


def _match_metrics(source, data):
    name = re.search(rb"/FontName\s*/([^\s{}\[\]()]+)", data)
    afms = []
    for filename, blob in source.companions or []:
        match = re.search(rb"(?:^|[\r\n])FontName[ \t]+([^\s]+)", blob)
        if filename.lower().endswith(".afm") and name and match and match[1] == name[1]:
            afms.append((filename, blob))
    if len(afms) == 1:
        return afms
    matches = [(n, b) for n, b in source.companions or [] if Path(n).stem.casefold() == source.relative.stem.casefold()]
    return sorted(matches, key=lambda x: not x[0].lower().endswith(".afm"))[:1]


def _safe_name(name):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).rstrip(". ") or "font"
    if text.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1,10)), *(f"LPT{i}" for i in range(1,10))}:
        text = "_" + text
    return text[:160]


def _safe_dir(path, root):
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("Output subdirectories must not be symlinks")
        current.mkdir(exist_ok=True)


def _publish(data, source, item, dest, extension):
    parent = dest / "Fonts"
    for part in source.relative.parent.parts:
        parent /= _safe_name(part)
    _safe_dir(parent, dest)
    name = source.relative.name
    if Path(name).suffix.lower() in {".ttf", ".otf", ".ttc", ".otc"}:
        name = Path(name).stem
    if item["resource_id"]:
        name += "-" + item["resource_id"]
    name = _safe_name(name)
    fingerprint = digest(data)
    # Case-insensitive collision handling works on macOS, Windows, and Linux.
    existing = {p.name.casefold(): p for p in parent.iterdir()}
    suffix = ""
    index = 1
    while True:
        candidate = parent / (name + suffix + extension)
        collision = existing.get(candidate.name.casefold())
        if collision is None:
            with candidate.open("xb") as handle:
                handle.write(data)
            break
        if not collision.is_symlink() and collision.is_file() and digest(collision.read_bytes()) == fingerprint:
            candidate = collision
            break
        suffix = "--" + item["id"][:10] + "-" + fingerprint[:8] + (f"-{index}" if index > 1 else "")
        index += 1
    item.update(output=candidate.relative_to(dest).as_posix(), output_sha256=fingerprint)


def _convert_job(job, work, executable):
    key, payload, metrics = job
    folder = work/key
    _safe_dir(folder, work)
    if any(p.is_symlink() for p in folder.iterdir()):
        raise ValueError("Conversion work files must not be symlinks")
    input_path, target, metadata_path = folder/"input.pfb", folder/"font.otf", folder/"metadata.json"
    marker = folder/"success.json"
    if marker.is_file() and not marker.is_symlink() and target.is_file() and not target.is_symlink():
        try:
            cached = json.loads(marker.read_text(encoding="utf-8"))
            if digest(target.read_bytes()) == cached["sha256"]:
                checked = validate(target)
                return target.read_bytes(), {**cached["metadata"], "validation": checked}
        except Exception:
            pass
    input_path.write_bytes(payload)
    metric_paths = []
    for idx, (name, blob) in enumerate(metrics):
        path = folder/(f"metric-{idx}" + Path(name).suffix.lower())
        path.write_bytes(blob)
        metric_paths.append(str(path))
    worker = str(Path(__file__).with_name("worker.py"))
    messages = []
    variants = [(payload, False)]
    try:
        repaired = escape_header(payload)
        if repaired:
            variants.append((repaired, True))
    except ValueError:
        pass
    for content, repaired in variants:
        input_path.write_bytes(content)
        for stale in [target, metadata_path]:
            if stale.exists():
                stale.unlink()
        process = subprocess.run([executable, "-lang=py", "-script", worker, str(input_path), str(target),
                                  str(metadata_path), *metric_paths], capture_output=True, text=True,
                                 errors="replace", timeout=90)
        messages.append(process.stdout + process.stderr)
        (folder/"fontforge.log").write_text("\n".join(messages), encoding="utf-8")
        if process.returncode or not target.is_file() or not metadata_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        validation = validate(target)
        if metadata.get("width_changes") or not metadata.get("glyphs"):
            raise ValueError("Failed glyph/width validation")
        metadata["metrics_imported"] = [name for name, _ in metrics]
        metadata.update(validation=validation, header_repaired=repaired)
        atomic_json(marker, {"sha256": digest(target.read_bytes()), "metadata": metadata})
        return target.read_bytes(), metadata
    raise ValueError("FontForge could not produce a valid font. " + "\n".join(messages)[-1800:])


def convert_folder(source, output=None, *, archives=True, jobs=4, fontforge=None, progress=None):
    src, dest = roots(source, output)
    if not 1 <= jobs <= 16:
        raise ValueError("jobs must be between 1 and 16")
    dest.mkdir(parents=True, exist_ok=True)
    control = dest/".font-reviver"
    _safe_dir(control, dest)
    for name in ["results.csv", "Gallery.html"]:
        if (dest/name).is_symlink():
            raise ValueError("Output report files must not be symlinks")
    lock = control/"lock"
    try:
        handle = lock.open("x")
    except FileExistsError:
        raise ValueError("Output is already locked. If a previous process crashed, verify it stopped before removing .font-reviver/lock") from None
    handle.write(str(os.getpid()))
    handle.close()
    try:
        return _convert(src, dest, control, archives, jobs, fontforge, progress)
    finally:
        lock.unlink(missing_ok=True)


def _convert(src, dest, control, archives, jobs, fontforge, progress):
    executable = fontforge or os.environ.get("FONTFORGE") or shutil.which("fontforge")
    records, pending = [], {}
    work = control/"work"
    _safe_dir(work, dest)
    for source in sources(src, dest, archives):
        row, payloads = _row(source)
        records.append(row)
        for item, (kind, rid, blob) in zip(row["fonts"], payloads):
            if kind == "type1":
                if not executable:
                    item.update(status="missing_fontforge", error="Install FontForge or set FONTFORGE to its executable")
                    continue
                metrics = _match_metrics(source, blob)
                key = digest(__version__.encode() + bytes.fromhex(digest(blob)) + b"".join(bytes.fromhex(digest(b)) for _, b in metrics))
                pending.setdefault(key, {"job": (key, blob, metrics), "consumers": []})["consumers"].append((source, item))
                item["status"] = "queued"
            else:
                try:
                    extension = ".ttc" if blob[:4] == b"ttcf" else ".otf" if blob[:4] == b"OTTO" else ".ttf"
                    # Validate staging data before placing it in the usable Fonts directory.
                    with tempfile.TemporaryDirectory(dir=work) as temp:
                        stage = Path(temp)/("font" + extension)
                        stage.write_bytes(blob)
                        validation = validate(stage)
                    _publish(blob, source, item, dest, extension)
                    item.update(status="copied" if kind == "modern" else "extracted", validation=validation)
                except Exception as error:
                    item.update(status="needs_review", error=str(error))
        if progress:
            progress({"event": "scanned", "source": source.name, "entries": len(records)})
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_convert_job, details["job"], work, executable): (key, details) for key, details in pending.items()}
        for index, future in enumerate(as_completed(futures), 1):
            key, details = futures[future]
            try:
                data, metadata = future.result()
                for source, item in details["consumers"]:
                    _publish(data, source, item, dest, ".otf")
                    item.update(status="converted", **metadata)
            except Exception as error:
                for _, item in details["consumers"]:
                    item.update(status="needs_review", error=str(error), log=f".font-reviver/work/{key}/fontforge.log")
            if progress:
                progress({"event": "converted", "completed": index, "total": len(pending)})
    report = {"schema_version": SCHEMA_VERSION, "version": __version__, "operation": "convert",
              "source_root": str(src), "output_root": str(dest), "summary": summarize(records), "records": records}
    atomic_json(dest/"report.json", report)
    with (dest/"results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Source", "Status", "Output", "Error"])
        for row in records:
            if not row["fonts"]:
                writer.writerow([row["source"], row["status"], "", row.get("error", "; ".join(row["warnings"]))])
            for item in row["fonts"]:
                writer.writerow([row["source"], item["status"], item.get("output", ""), item.get("error", "")])
    from .gallery import write_gallery
    write_gallery(report, dest/"Gallery.html")
    return report
