"""Generate a weekly report for a folder: what changed, by day and type.

Scans files (recursive), groups them by the day they were last modified,
and summarizes counts, sizes, categories and the largest files.
Outputs a Markdown report and a CSV summary — the two formats people
actually forward or paste into a status update.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .organizer import categorize

TOP_LARGEST = 10


def _human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def collect(source: Path, *, days: int = 7,
            end: datetime | None = None) -> dict:
    """Collect file stats for the ``days`` ending at ``end`` (default: now)."""
    source = Path(source)
    if not source.is_dir():
        raise FileNotFoundError(f"Folder not found: {source}")
    if days < 1:
        raise ValueError("days must be at least 1")

    end = end or datetime.now()
    start = end - timedelta(days=days)
    start_date, end_date = start.date(), end.date()

    files: list[dict] = []
    for item in sorted(source.rglob("*")):
        if not item.is_file() or item.name.startswith("."):
            continue
        # Skip our own logs and generated reports.
        if ".automation-logs" in item.parts or item.parent.name == "reports":
            continue
        mtime = datetime.fromtimestamp(item.stat().st_mtime)
        if not (start <= mtime <= end):
            continue
        files.append({
            "name": item.name,
            "path": str(item.relative_to(source)),
            "category": categorize(item),
            "extension": item.suffix.lower() or "(none)",
            "size_bytes": item.stat().st_size,
            "modified": mtime,
            "day": mtime.date().isoformat(),
        })

    by_day: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        by_day[f["day"]].append(f)

    return {
        "source": str(source),
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "days": days,
        "total_files": len(files),
        "total_bytes": sum(f["size_bytes"] for f in files),
        "by_category": dict(Counter(f["category"] for f in files)),
        "by_extension": dict(Counter(f["extension"] for f in files)),
        "by_day": {d: len(v) for d, v in sorted(by_day.items())},
        "largest": sorted(files, key=lambda f: f["size_bytes"],
                          reverse=True)[:TOP_LARGEST],
        "files": files,
    }


def to_markdown(data: dict) -> str:
    """Render collected stats as a Markdown weekly report."""
    lines = [
        f"# Weekly Report — {data['start']} to {data['end']}",
        "",
        f"Folder: `{data['source']}`  |  Period: {data['days']} days",
        "",
        "## Summary",
        "",
        f"- **Files changed:** {data['total_files']}",
        f"- **Total size:** {_human_size(data['total_bytes'])}",
        "",
        "## Files per day",
        "",
    ]
    if data["by_day"]:
        for day, count in data["by_day"].items():
            lines.append(f"- {day}: {count} file(s)")
    else:
        lines.append("- No files changed in this period.")
    lines += ["", "## By category", ""]
    if data["by_category"]:
        for cat, count in sorted(data["by_category"].items(),
                                 key=lambda kv: -kv[1]):
            lines.append(f"- {cat}: {count}")
    else:
        lines.append("- (none)")
    lines += ["", "## Largest files", ""]
    if data["largest"]:
        for f in data["largest"]:
            lines.append(f"- `{f['path']}` — {_human_size(f['size_bytes'])}")
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def write_report(source: Path, *, days: int = 7,
                 output_dir: Path | None = None,
                 end: datetime | None = None) -> dict:
    """Collect stats and write the .md report + .csv summary. Returns paths."""
    data = collect(source, days=days, end=end)
    output_dir = Path(output_dir) if output_dir else Path(source) / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = data["end"]
    md_path = output_dir / f"weekly-report-{stamp}.md"
    csv_path = output_dir / f"weekly-summary-{stamp}.csv"
    md_path.write_text(to_markdown(data), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["day", "category", "extension", "file", "size_bytes"])
        for f in sorted(data["files"], key=lambda x: (x["day"], x["path"])):
            writer.writerow([f["day"], f["category"], f["extension"],
                             f["path"], f["size_bytes"]])
    return {"data": data, "markdown": str(md_path), "csv": str(csv_path)}
