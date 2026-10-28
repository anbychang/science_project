"""Tests for the Phase 2R twelve-year source adapters."""

import csv
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, time, timezone
from pathlib import Path

from phases.phase2r.code.prep_2r0_source_audit import audit_sme
from phases.phase2r.code.prep_2r0_source_checkpoint import write_source_checkpoint
from phases.phase2r.code.prep_2r1_geomag_1min import source_audit


def write_sme_day(folder: Path, day: date) -> dict:
    """Input: folder and UTC day. Output: manifest record for a valid SME day."""
    path = folder / f"SME_{day:%Y%m%d}.csv"
    start = int(datetime.combine(day, time.min, timezone.utc).timestamp())
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(("tval", "SME", "SMEnum"))
        for minute in range(1440):
            writer.writerow((start + minute * 60, 100.0, 50))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "file_name": path.name,
        "row_count": 1440,
        "downloaded_at_utc": "2026-10-25T00:00:00+00:00",
        "sha256": digest,
    }


class Phase2RSourceAdapterTests(unittest.TestCase):
    """Input: temporary source fixtures. Output: verified Phase 2R boundaries."""

    def test_audit_sme_selects_requested_range_from_larger_manifest(self):
        """Input: three-day manifest. Output: selected two-day audit."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            folder = Path(directory)
            days = (date(2014, 6, 30), date(2014, 7, 1), date(2014, 7, 2))
            records = [write_sme_day(folder, day) for day in days]
            (folder / "manifest_p2_0_sme.json").write_text(
                json.dumps({"files": records}), encoding="utf-8"
            )
            audit = audit_sme(folder, (days[1], days[2]))
        self.assertEqual(audit["day_files"], 2)
        self.assertEqual(audit["minute_slots"], 2880)
        self.assertEqual(audit["manifest_files"], 3)

    def test_checkpoint_and_geomag_adapter_accept_fixed_range(self):
        """Input: fixed-range audit. Output: hash-verified P2R.0 checkpoint."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            folder = Path(directory)
            audit_path = folder / "audit.json"
            output_db = folder / "source.sqlite"
            audit_text = json.dumps({
                "date_range_utc": ["2014-07-01", "2026-06-30"],
            }, indent=2) + "\n"
            audit_path.write_text(audit_text, encoding="utf-8")
            file_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
            audit_hash = write_source_checkpoint(audit_path, output_db)
            with closing(sqlite3.connect(output_db)) as connection:
                embedded = source_audit(connection)
        self.assertEqual(audit_hash, file_hash)
        self.assertEqual(embedded["date_range_utc"], ["2014-07-01", "2026-06-30"])


if __name__ == "__main__":
    unittest.main()
