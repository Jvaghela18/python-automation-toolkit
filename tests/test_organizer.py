"""Tests for the file organizer. Run: python -m unittest discover -v"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_toolkit import organizer


def make_files(folder: Path, names: dict[str, str]) -> None:
    for name, content in names.items():
        p = folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


class TestCategorize(unittest.TestCase):
    def test_known_extensions(self):
        self.assertEqual(organizer.categorize(Path("a.pdf")), "Documents")
        self.assertEqual(organizer.categorize(Path("a.xlsx")), "Spreadsheets")
        self.assertEqual(organizer.categorize(Path("a.PNG")), "Images")
        self.assertEqual(organizer.categorize(Path("a.mp4")), "Videos")
        self.assertEqual(organizer.categorize(Path("a.py")), "Code")
        self.assertEqual(organizer.categorize(Path("a.zip")), "Archives")

    def test_unknown_extension_is_others(self):
        self.assertEqual(organizer.categorize(Path("a.xyz")), "Others")
        self.assertEqual(organizer.categorize(Path("noext")), "Others")


class TestOrganize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_moves_files_into_category_folders(self):
        make_files(self.folder, {"notes.txt": "hi", "photo.jpg": "x",
                                 "data.csv": "a,b"})
        summary = organizer.organize(self.folder)
        self.assertEqual(summary["moved"], 3)
        self.assertTrue((self.folder / "Documents" / "notes.txt").exists())
        self.assertTrue((self.folder / "Images" / "photo.jpg").exists())
        self.assertTrue((self.folder / "Spreadsheets" / "data.csv").exists())
        self.assertEqual(summary["by_category"],
                         {"Documents": 1, "Images": 1, "Spreadsheets": 1})

    def test_dry_run_moves_nothing(self):
        make_files(self.folder, {"notes.txt": "hi"})
        summary = organizer.organize(self.folder, dry_run=True)
        self.assertTrue(summary["dry_run"])
        self.assertEqual(summary["moved"], 0)
        self.assertTrue((self.folder / "notes.txt").exists())
        self.assertFalse((self.folder / "Documents").exists())

    def test_duplicate_name_is_renamed_not_overwritten(self):
        make_files(self.folder, {"a.txt": "new"})
        (self.folder / "Documents").mkdir()
        (self.folder / "Documents" / "a.txt").write_text("old")
        summary = organizer.organize(self.folder)
        self.assertEqual(summary["moved"], 1)
        self.assertEqual((self.folder / "Documents" / "a.txt").read_text(), "old")
        self.assertEqual((self.folder / "Documents" / "a_1.txt").read_text(), "new")

    def test_hidden_files_and_folders_are_skipped(self):
        make_files(self.folder, {".secret.txt": "x", "keep.txt": "y"})
        (self.folder / "sub").mkdir()
        (self.folder / "sub" / "inner.txt").write_text("z")
        summary = organizer.organize(self.folder)
        self.assertEqual(summary["moved"], 1)
        self.assertTrue((self.folder / ".secret.txt").exists())
        self.assertTrue((self.folder / "sub" / "inner.txt").exists())

    def test_by_date_groups_into_year_month(self):
        make_files(self.folder, {"notes.txt": "hi"})
        summary = organizer.organize(self.folder, by_date=True)
        self.assertEqual(summary["moved"], 1)
        dest = next((self.folder / "Documents").rglob("notes.txt"))
        self.assertEqual(len(dest.parent.name), 7)  # YYYY-MM
        self.assertEqual(dest.parent.name[4], "-")

    def test_already_organized_file_is_left_alone(self):
        make_files(self.folder, {"Documents/notes.txt": "hi"})
        summary = organizer.organize(self.folder)
        self.assertEqual(summary["moved"], 0)

    def test_undo_restores_files(self):
        make_files(self.folder, {"notes.txt": "hi", "photo.jpg": "x"})
        summary = organizer.organize(self.folder)
        self.assertIsNotNone(summary["log_path"])
        result = organizer.undo(Path(summary["log_path"]))
        self.assertEqual(result["restored"], 2)
        self.assertTrue((self.folder / "notes.txt").exists())
        self.assertTrue((self.folder / "photo.jpg").exists())

    def test_missing_folder_raises(self):
        with self.assertRaises(FileNotFoundError):
            organizer.organize(self.folder / "nope")


if __name__ == "__main__":
    unittest.main()
