"""Command-line interface: organize, report, weekly, undo.

Usage:
    python -m automation_toolkit organize ~/Downloads --dry-run
    python -m automation_toolkit organize ~/Downloads --by-date
    python -m automation_toolkit report ~/Documents --days 7
    python -m automation_toolkit weekly ~/Downloads   # organize + report
    python -m automation_toolkit undo <log-file.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, organizer, report


def _print_summary(summary: dict) -> None:
    if summary.get("dry_run"):
        print(f"Dry run — {len(summary['moves'])} file(s) would move:")
    else:
        print(f"Moved {summary['moved']} file(s), "
              f"{summary['total_bytes']:,} bytes total.")
    for category, count in sorted(summary["by_category"].items()):
        print(f"  {category}: {count}")
    if summary.get("log_path"):
        print(f"Undo log: {summary['log_path']}")
    if summary.get("dry_run"):
        for move in summary["moves"]:
            print(f"  {move['source']} -> {move['destination']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="automation-toolkit",
        description="Organize files into folders and generate weekly reports.")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_org = sub.add_parser("organize", help="Sort files into category folders.")
    p_org.add_argument("folder", type=Path)
    p_org.add_argument("--by-date", action="store_true",
                       help="Also group into YYYY-MM subfolders by modified date.")
    p_org.add_argument("--recursive", action="store_true")
    p_org.add_argument("--dry-run", action="store_true",
                       help="Show what would move, change nothing.")

    p_rep = sub.add_parser("report", help="Write a weekly Markdown + CSV report.")
    p_rep.add_argument("folder", type=Path)
    p_rep.add_argument("--days", type=int, default=7)
    p_rep.add_argument("--output-dir", type=Path, default=None)

    p_week = sub.add_parser("weekly",
                            help="Organize a folder, then write its weekly report.")
    p_week.add_argument("folder", type=Path)
    p_week.add_argument("--days", type=int, default=7)
    p_week.add_argument("--by-date", action="store_true")
    p_week.add_argument("--dry-run", action="store_true")

    p_undo = sub.add_parser("undo", help="Reverse an organize run from its log.")
    p_undo.add_argument("log", type=Path)

    args = parser.parse_args(argv)

    try:
        if args.command == "organize":
            _print_summary(organizer.organize(
                args.folder, by_date=args.by_date, recursive=args.recursive,
                dry_run=args.dry_run))
        elif args.command == "report":
            result = report.write_report(args.folder, days=args.days,
                                         output_dir=args.output_dir)
            data = result["data"]
            print(f"Report: {data['total_files']} file(s), "
                  f"{data['total_bytes']:,} bytes over {data['days']} days.")
            print(f"Markdown: {result['markdown']}")
            print(f"CSV: {result['csv']}")
        elif args.command == "weekly":
            _print_summary(organizer.organize(
                args.folder, by_date=args.by_date, dry_run=args.dry_run))
            result = report.write_report(args.folder, days=args.days)
            print(f"Report: {result['markdown']}")
            print(f"CSV: {result['csv']}")
        elif args.command == "undo":
            result = organizer.undo(args.log)
            print(f"Restored {result['restored']} file(s).")
            if result["missing"]:
                print(f"Missing (already moved/deleted): {len(result['missing'])}")
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
