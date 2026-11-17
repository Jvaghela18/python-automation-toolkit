"""End-to-end demo: builds a messy folder in /tmp, organizes it, reports on it.

Run:  python examples/demo.py
It only touches a temp folder it creates itself — never your real files.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_toolkit import organizer, report

with tempfile.TemporaryDirectory() as tmp:
    folder = Path(tmp) / "messy-downloads"
    folder.mkdir()
    for name, text in {
        "essay.pdf": "x" * 100, "notes.txt": "hello", "budget.xlsx": "a,b",
        "photo.jpg": "x" * 500, "clip.mp4": "x" * 900, "song.mp3": "x" * 300,
        "backup.zip": "x" * 200, "script.py": "print(1)", "mystery.xyz": "?",
    }.items():
        (folder / name).write_text(text)

    print("== dry run ==")
    print(organizer.organize(folder, dry_run=True)["by_category"])
    print("== real run ==")
    summary = organizer.organize(folder)
    print(f"moved {summary['moved']} files: {summary['by_category']}")
    print("== weekly report ==")
    result = report.write_report(folder, days=7)
    print(Path(result["markdown"]).read_text())
    print("Demo OK — all files organized, report written.")
