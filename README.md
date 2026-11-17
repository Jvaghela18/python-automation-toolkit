# Python Automation Toolkit

Built by Jay Vaghela — Rutgers University, Computer Science

## About me

I'm a sophomore Computer Science student at Rutgers University–New Brunswick,
aspiring to become a cybersecurity analyst — working toward a SOC (Security
Operations Center) analyst role. I've interned at the NJCCIC (New Jersey
Cybersecurity and Communications Integration Cell), where I worked on
cybersecurity projects, CTF challenges, and research on safely integrating AI
into cybersecurity, and I'm a member of the Rutgers University Security Club
(RUSEC). I build practical tools like this one to automate repetitive work
and keep building the skills I'll use defending systems.

Two repetitive tasks, automated in pure Python (stdlib only, no dependencies):

1. **File organizer** — sorts a messy folder into category folders
   (Documents, Images, Videos, Spreadsheets, Code, Archives, Audio, …).
2. **Weekly report generator** — scans a folder for the last 7 days and
   writes a Markdown report + CSV summary: files changed, per-day counts,
   breakdown by category, and the largest files.

## Run it

```bash
# 1. See what would move, without moving anything
PYTHONPATH=src python -m automation_toolkit organize ~/Downloads --dry-run

# 2. Actually organize (duplicates are renamed, never overwritten)
PYTHONPATH=src python -m automation_toolkit organize ~/Downloads

# 3. Also group into YYYY-MM subfolders by modified date
PYTHONPATH=src python -m automation_toolkit organize ~/Downloads --by-date

# 4. Weekly report for the last 7 days (writes reports/weekly-report-*.md + .csv)
PYTHONPATH=src python -m automation_toolkit report ~/Documents --days 7

# 5. Both at once: organize, then report
PYTHONPATH=src python -m automation_toolkit weekly ~/Downloads

# 6. Undo an organize run (uses the log it wrote)
PYTHONPATH=src python -m automation_toolkit undo ~/Downloads/.automation-logs/organize-2026-11-17-090000.json
```

## Safety rules

- Only files are moved — never folders, never hidden files (`.xxx`).
- A file already in its correct folder is left alone.
- Same name in the destination? The incoming file becomes `name_1.ext`,
  `name_2.ext`, … — nothing is ever overwritten.
- Every real organize run writes an undo log (JSON) to
  `<folder>/.automation-logs/` so you can reverse it.

## Tests

```bash
python -m unittest discover -s tests -v
```

17 tests: organizer (categorize, move, dry-run, duplicates, hidden files,
by-date, already-organized, undo, missing folder) and report (date filter,
per-day/extension grouping, Markdown, empty period, MD + CSV output,
invalid input).

## Example output

```
Moved 3 file(s), 1,024 bytes total.
  Documents: 1
  Images: 1
  Spreadsheets: 1
Undo log: ~/Downloads/.automation-logs/organize-2026-11-17-090000.json
```

```markdown
# Weekly Report — 2026-11-10 to 2026-11-17
- **Files changed:** 12
- **Total size:** 4.2 MB
## Files per day
- 2026-11-16: 5 file(s)
```

## Limits (honest)

- The organizer sorts by file extension, not by reading file contents —
  a `.txt` file that is really a photo is still filed as a Document.
- The weekly report uses last-modified time, not creation time.
- No cloud sync, no scheduling built in: run it yourself, or schedule it
  with `cron` (macOS/Linux) / Task Scheduler (Windows), e.g.
  `0 9 * * MON PYTHONPATH=... python -m automation_toolkit weekly ~/Downloads`.
