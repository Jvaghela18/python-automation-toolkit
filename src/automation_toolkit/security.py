"""File-integrity + security scan: flag risky files in a folder.

A tiny Tripwire-style check for the weekly report. It flags, without
running or opening anything:

- double extensions (``invoice.pdf.exe``) — a classic malware disguise;
- executable files (``.exe``, ``.msi``, ``.bat``, ...) that appeared in
  the folder — e.g. something downloaded that you did not expect;
- script files (``.py``, ``.ps1``, ``.sh``, ...) sitting in the folder;
- files whose SHA-256 hash changed since a saved baseline snapshot,
  plus files that are new or have gone missing since that snapshot.

Stdlib only. The baseline is just a JSON file of relative paths to
SHA-256 hashes — run ``scan --save-baseline baseline.json`` once, then
``scan --baseline baseline.json`` on later runs to see what changed.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

#: Extensions that can run code when opened. A file ending in one of
#: these is flagged as an executable, whatever it claims to be.
RISKY_EXECUTABLES = {
    ".exe", ".msi", ".bat", ".cmd", ".scr", ".com", ".ps1", ".vbs",
    ".jar", ".app", ".dmg",
}

#: Script files: code that runs in an interpreter, not an app you open.
SCRIPT_EXTENSIONS = {".py", ".js", ".ps1", ".bat", ".sh", ".vbs"}

# Folders this tool itself creates — never scanned as user files.
_SKIP_DIRS = {".automation-logs", "reports"}

_CHUNK = 1024 * 1024


def file_sha256(path: Path) -> str:
    """SHA-256 hex digest of a file, read in 1 MB chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def is_double_extension(path: Path) -> bool:
    """True for ``invoice.pdf.exe``: a harmless-looking suffix hiding a
    risky executable suffix underneath it."""
    suffixes = [s.lower() for s in Path(path).suffixes]
    return len(suffixes) >= 2 and suffixes[-1] in RISKY_EXECUTABLES


def check_file(path: Path) -> dict | None:
    """Return one finding for a file, or None if nothing is risky.

    Most severe check wins, so a file is flagged once, not three times:
    double extension beats executable beats script.
    """
    path = Path(path)
    if is_double_extension(path):
        return {
            "path": path.name,
            "kind": "double_extension",
            "detail": f"Double extension hiding an executable: {path.name}",
        }
    ext = path.suffix.lower()
    if ext in RISKY_EXECUTABLES:
        return {
            "path": path.name,
            "kind": "executable",
            "detail": f"Executable file: {path.name}",
        }
    if ext in SCRIPT_EXTENSIONS:
        return {
            "path": path.name,
            "kind": "script",
            "detail": f"Script file: {path.name}",
        }
    return None


def _iter_files(source: Path, *, exclude: Path | None = None):
    """User files under ``source``, skipping hidden files and our own
    logs/reports folders — same rule as the weekly report. ``exclude``
    skips one extra file, e.g. the baseline JSON itself when it lives
    inside the scanned folder."""
    exclude = Path(exclude).resolve() if exclude is not None else None
    for item in sorted(source.rglob("*")):
        if not item.is_file() or item.name.startswith("."):
            continue
        if exclude is not None and item.resolve() == exclude:
            continue
        if _SKIP_DIRS.intersection(item.parts):
            continue
        yield item


def save_baseline(source: Path, baseline_path: Path) -> dict:
    """Hash every file under ``source`` and save the snapshot as JSON.

    Returns {"path": ..., "files": <count>}. Run once, then pass the
    file to :func:`scan` on later runs to spot changes.
    """
    source, baseline_path = Path(source), Path(baseline_path)
    if not source.is_dir():
        raise FileNotFoundError(f"Folder not found: {source}")
    files = {}
    for item in _iter_files(source, exclude=baseline_path):
        rel = str(item.relative_to(source))
        files[rel] = {
            "sha256": file_sha256(item),
            "size_bytes": item.stat().st_size,
        }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps({
        "created_at": datetime.now().isoformat(),
        "source": str(source),
        "files": files,
    }, indent=2), encoding="utf-8")
    return {"path": str(baseline_path), "files": len(files)}


def load_baseline(baseline_path: Path) -> dict:
    """Load a baseline JSON file. Returns its ``files`` mapping."""
    data = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    return data.get("files", {})


def scan(source: Path, *, baseline: Path | dict | None = None) -> dict:
    """Scan ``source`` and return {"source", "total_files", "findings"}.

    ``findings`` is a list of {"path", "kind", "detail"} with kinds:
    ``double_extension``, ``executable``, ``script``, plus — only when
    a baseline is given — ``changed`` (hash differs from the baseline),
    ``new`` (not in the baseline) and ``missing`` (in the baseline,
    no longer on disk).
    """
    source = Path(source)
    if not source.is_dir():
        raise FileNotFoundError(f"Folder not found: {source}")
    baseline_path = None
    if baseline is not None and not isinstance(baseline, dict):
        baseline_path = Path(baseline)
        baseline = load_baseline(baseline_path)

    findings: list[dict] = []
    seen: set[str] = set()
    total = 0
    for item in _iter_files(source, exclude=baseline_path):
        total += 1
        rel = str(item.relative_to(source))
        seen.add(rel)
        finding = check_file(item)
        if finding is not None:
            findings.append({**finding, "path": rel})
        if baseline is not None:
            old = baseline.get(rel)
            if old is None:
                findings.append({
                    "path": rel,
                    "kind": "new",
                    "detail": f"New since baseline: {rel}",
                })
            elif old.get("sha256") != file_sha256(item):
                findings.append({
                    "path": rel,
                    "kind": "changed",
                    "detail": f"Content changed since baseline: {rel}",
                })
    if baseline is not None:
        for rel in sorted(baseline):
            if rel not in seen:
                findings.append({
                    "path": rel,
                    "kind": "missing",
                    "detail": f"Gone since baseline: {rel}",
                })

    kinds: dict[str, int] = {}
    for f in findings:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    return {
        "source": str(source),
        "total_files": total,
        "findings": findings,
        "by_kind": kinds,
    }


def to_markdown_section(data: dict) -> str:
    """Render scan findings as a Markdown section for the weekly report.
    Returns "" when there is nothing to flag."""
    findings = data.get("findings", [])
    if not findings:
        return ""
    lines = ["## Security findings", ""]
    for f in findings:
        lines.append(f"- **{f['kind'].replace('_', ' ')}** — `{f['path']}`")
    lines.append("")
    return "\n".join(lines)
