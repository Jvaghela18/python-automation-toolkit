"""Tests for the weekly report generator. Run: python -m unittest discover -v"""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_toolkit import report


def make_file(folder: Path, name: str, content: str, days_ago: float) -> None:
    p = folder / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    ts = (datetime.now() - timedelta(days=days_ago)).timestamp()
    import os
    os.utime(p, (ts, ts))


class TestReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_collect_counts_only_recent_files(self):
        make_file(self.folder, "new.txt", "hello", days_ago=1)
        make_file(self.folder, "old.txt", "hello", days_ago=30)
        data = report.collect(self.folder, days=7)
        self.assertEqual(data["total_files"], 1)
        self.assertEqual(data["total_bytes"], 5)
        self.assertEqual(data["by_category"], {"Documents": 1})

    def test_collect_groups_by_day_and_extension(self):
        make_file(self.folder, "a.txt", "hi", days_ago=1)
        make_file(self.folder, "b.jpg", "1234", days_ago=2)
        data = report.collect(self.folder, days=7)
        self.assertEqual(data["total_files"], 2)
        self.assertEqual(data["by_extension"], {".txt": 1, ".jpg": 1})
        self.assertEqual(sum(data["by_day"].values()), 2)
        self.assertEqual(len(data["largest"]), 2)
        self.assertEqual(data["largest"][0]["name"], "b.jpg")

    def test_markdown_contains_summary(self):
        make_file(self.folder, "a.txt", "hello", days_ago=0)
        data = report.collect(self.folder, days=7)
        md = report.to_markdown(data)
        self.assertIn("# Weekly Report", md)
        self.assertIn("Files changed:** 1", md)
        self.assertIn("Documents: 1", md)
        self.assertIn("a.txt", md)

    def test_empty_period_report(self):
        data = report.collect(self.folder, days=7)
        self.assertEqual(data["total_files"], 0)
        self.assertIn("No files changed", report.to_markdown(data))

    def test_write_report_creates_md_and_csv(self):
        make_file(self.folder, "a.txt", "hello", days_ago=1)
        make_file(self.folder, "b.csv", "x,y", days_ago=1)
        result = report.write_report(self.folder, days=7)
        md, csv_path = Path(result["markdown"]), Path(result["csv"])
        self.assertTrue(md.exists())
        self.assertTrue(csv_path.exists())
        self.assertIn("Weekly Report", md.read_text())
        rows = csv_path.read_text().splitlines()
        self.assertEqual(rows[0], "day,category,extension,file,size_bytes")
        self.assertEqual(len(rows), 3)  # header + 2 files

    def test_invalid_days_raises(self):
        with self.assertRaises(ValueError):
            report.collect(self.folder, days=0)

    def test_missing_folder_raises(self):
        with self.assertRaises(FileNotFoundError):
            report.collect(self.folder / "nope")


if __name__ == "__main__":
    unittest.main()
