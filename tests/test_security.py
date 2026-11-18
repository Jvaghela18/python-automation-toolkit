"""Tests for the file-integrity + security scan. Run: python -m unittest discover -v"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_toolkit import report, security


def make_file(folder: Path, name: str, content: str = "hello") -> Path:
    p = folder / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_double_extension_flagged(self):
        make_file(self.folder, "invoice.pdf.exe")
        data = security.scan(self.folder)
        self.assertEqual(len(data["findings"]), 1)
        self.assertEqual(data["findings"][0]["kind"], "double_extension")

    def test_plain_pdf_not_flagged(self):
        make_file(self.folder, "invoice.pdf")
        self.assertEqual(security.scan(self.folder)["findings"], [])

    def test_executable_flagged(self):
        make_file(self.folder, "setup.exe")
        data = security.scan(self.folder)
        self.assertEqual([f["kind"] for f in data["findings"]],
                         ["executable"])

    def test_script_flagged(self):
        make_file(self.folder, "run.sh")
        data = security.scan(self.folder)
        self.assertEqual([f["kind"] for f in data["findings"]], ["script"])

    def test_double_extension_flagged_once_not_three_times(self):
        make_file(self.folder, "report.docx.bat")
        data = security.scan(self.folder)
        self.assertEqual(len(data["findings"]), 1)

    def test_hidden_files_skipped(self):
        make_file(self.folder, ".hidden.exe")
        self.assertEqual(security.scan(self.folder)["findings"], [])

    def test_baseline_unchanged_is_clean(self):
        make_file(self.folder, "notes.txt", "v1")
        baseline = self.folder / "baseline.json"
        security.save_baseline(self.folder, baseline)
        data = security.scan(self.folder, baseline=baseline)
        self.assertEqual(data["findings"], [])

    def test_baseline_spots_changed_new_and_missing(self):
        make_file(self.folder, "notes.txt", "v1")
        make_file(self.folder, "gone.txt", "bye")
        baseline = self.folder / "baseline.json"
        security.save_baseline(self.folder, baseline)
        (self.folder / "notes.txt").write_text("v2", encoding="utf-8")
        (self.folder / "gone.txt").unlink()
        make_file(self.folder, "fresh.txt", "new")
        data = security.scan(self.folder, baseline=baseline)
        kinds = sorted(f["kind"] for f in data["findings"])
        self.assertEqual(kinds, ["changed", "missing", "new"])

    def test_missing_baseline_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            security.scan(self.folder / "nope")

    def test_report_flags_risky_file_in_period(self):
        make_file(self.folder, "invoice.pdf.exe")
        make_file(self.folder, "ok.txt")
        data = report.collect(self.folder, days=7)
        kinds = [f["kind"] for f in data["security"]["findings"]]
        self.assertEqual(kinds, ["double_extension"])
        self.assertIn("Security findings", report.to_markdown(data))
        self.assertIn("invoice.pdf.exe", report.to_markdown(data))

    def test_report_with_no_risky_files_has_no_security_section(self):
        make_file(self.folder, "ok.txt")
        data = report.collect(self.folder, days=7)
        self.assertEqual(data["security"]["findings"], [])
        self.assertNotIn("Security findings", report.to_markdown(data))


if __name__ == "__main__":
    unittest.main()
