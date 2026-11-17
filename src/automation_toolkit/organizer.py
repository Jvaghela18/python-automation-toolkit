"""Organize files in a folder into category subfolders.

Rules (kept simple and safe on purpose):
- Only files are moved, never folders, never hidden files (names starting with '.').
- A file already inside its correct category folder is left alone.
- If a file with the same name already exists in the destination, the
  incoming file is renamed ``name_1.ext``, ``name_2.ext``, ... — nothing
  is ever overwritten.
- Every real run writes an undo log (JSON) so ``undo`` can move files back.
- Dry-run changes nothing and reports exactly what *would* happen.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

CATEGORIES = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"},
    "Spreadsheets": {".csv", ".xls", ".xlsx", ".ods"},
    "Presentations": {".ppt", ".pptx", ".key"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic"},
    "Videos": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "Archives": {".zip", ".tar", ".gz", ".rar", ".7z"},
    "Code": {".py", ".js", ".java", ".cpp", ".c", ".h", ".html", ".css",
             ".json", ".xml", ".yaml", ".yml", ".sql", ".ts"},
}

DEFAULT_CATEGORY = "Others"


def categorize(path: Path) -> str:
    """Return the category folder for a file, based on its extension."""
    ext = path.suffix.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return DEFAULT_CATEGORY


def _unique_destination(dest: Path) -> Path:
    """Return dest, or dest with _1, _2, ... added if it already exists."""
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 1
    while True:
        candidate = dest.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_moves(source: Path, *, by_date: bool = False,
               recursive: bool = False) -> list[dict]:
    """Work out what would move where. No files are touched.

    Returns a list of dicts: {source, destination, category, size_bytes}.
    """
    source = Path(source)
    if not source.is_dir():
        raise FileNotFoundError(f"Folder not found: {source}")

    files = source.rglob("*") if recursive else source.iterdir()
    moves: list[dict] = []
    planned_dests: set[Path] = set()

    for item in sorted(files, key=lambda p: p.name.lower()):
        if not item.is_file():
            continue
        if item.name.startswith("."):
            continue
        category = categorize(item)
        # Already in the right place? Leave it alone.
        if item.parent.name == category:
            continue
        if by_date:
            stamp = datetime.fromtimestamp(item.stat().st_mtime)
            dest_dir = source / category / stamp.strftime("%Y-%m")
        else:
            dest_dir = source / category
        dest = dest_dir / item.name
        # Account for duplicates already planned in this run.
        while dest in planned_dests or dest.exists():
            stem, suffix = dest.stem, dest.suffix
            base = stem.rsplit("_", 1)[0] if stem.rsplit("_", 1)[-1].isdigit() else stem
            n = 1
            # Find the next free numbered name.
            while True:
                candidate = dest_dir / f"{base}_{n}{suffix}"
                if candidate not in planned_dests and not candidate.exists():
                    dest = candidate
                    break
                n += 1
            break
        planned_dests.add(dest)
        moves.append({
            "source": str(item),
            "destination": str(dest),
            "category": category,
            "size_bytes": item.stat().st_size,
        })
    return moves


def organize(source: Path, *, by_date: bool = False, recursive: bool = False,
             dry_run: bool = False, log_dir: Path | None = None) -> dict:
    """Move files into category folders. Returns a summary dict.

    On a real run, writes an undo log JSON into ``log_dir`` (default:
    ``<source>/.automation-logs``) and returns its path in the summary.
    """
    source = Path(source)
    moves = plan_moves(source, by_date=by_date, recursive=recursive)

    summary: dict = {
        "source": str(source),
        "dry_run": dry_run,
        "moved": 0,
        "skipped_duplicates_renamed": 0,
        "total_bytes": sum(m["size_bytes"] for m in moves),
        "by_category": {},
        "moves": moves,
        "log_path": None,
    }
    for move in moves:
        summary["by_category"][move["category"]] = \
            summary["by_category"].get(move["category"], 0) + 1
        if Path(move["destination"]).name != Path(move["source"]).name:
            summary["skipped_duplicates_renamed"] += 1

    if dry_run or not moves:
        return summary

    performed: list[dict] = []
    for move in moves:
        src, dest = Path(move["source"]), Path(move["destination"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        performed.append({**move, "destination": str(dest)})

    summary["moved"] = len(performed)
    summary["moves"] = performed

    log_dir = Path(log_dir) if log_dir else source / ".automation-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / (
        f"organize-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.json")
    log_path.write_text(json.dumps({
        "created_at": datetime.now().isoformat(),
        "source": str(source),
        "moves": performed,
    }, indent=2), encoding="utf-8")
    summary["log_path"] = str(log_path)
    return summary


def undo(log_path: Path) -> dict:
    """Reverse an organize run from its undo log. Returns a summary."""
    log_path = Path(log_path)
    data = json.loads(log_path.read_text(encoding="utf-8"))
    restored, missing = 0, []
    for move in data["moves"]:
        src, dest = Path(move["destination"]), Path(move["source"])
        if not src.exists():
            missing.append(str(src))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(_unique_destination(dest)))
        restored += 1
    return {"restored": restored, "missing": missing, "log": str(log_path)}
