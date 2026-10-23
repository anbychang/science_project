"""Check Phase 2 source audit boundaries with small local fixtures."""

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from satellite_orbit.phase2.prep_20_source_audit import audit_kyoto, audit_sme


def make_sme_day(folder: Path) -> Path:
    """Input: empty folder. Output: one synthetic SME day and source manifest."""
    path = folder / "SME_20230701.csv"
    first_second = int(datetime(2023, 7, 1, tzinfo=timezone.utc).timestamp())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tval", "SME", "SMEnum"])
        for minute in range(1440):
            writer.writerow([float(first_second + 60 * minute), 999999.0 if minute >= 1438 else 50.0, 0 if minute >= 1438 else 20])
    manifest = {
        "files": [
            {
                "file_name": path.name,
                "row_count": 1440,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        ]
    }
    (folder / "manifest_p2_0_sme.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


class Phase2SourceAuditTest(unittest.TestCase):
    """Input: synthetic source files. Output: source QC or explicit failure."""

    def test_records_contiguous_sme_fill_span(self):
        """Input: two terminal fill minutes. Output: one exact invalid span."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_folder:
            folder = Path(temporary_folder)
            make_sme_day(folder)
            result = audit_sme(folder, (date(2023, 7, 1), date(2023, 7, 1)))
            first_second = int(datetime(2023, 7, 1, tzinfo=timezone.utc).timestamp())
            expected = [{"start_unix_s": first_second + 1438 * 60, "end_unix_s": first_second + 1439 * 60}]
            self.assertEqual(result["invalid_spans"], expected)

    def test_rejects_changed_sme_source(self):
        """Input: CSV changed after manifest. Output: digest error."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_folder:
            folder = Path(temporary_folder)
            path = make_sme_day(folder)
            with path.open("a", encoding="utf-8") as handle:
                handle.write("changed\n")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                audit_sme(folder, (date(2023, 7, 1), date(2023, 7, 1)))

    def test_rejects_conflicting_kyoto_duplicate(self):
        """Input: same minute with different values. Output: conflict error."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_folder:
            folder = Path(temporary_folder)
            header = {"cadence": "PT1M", "timeStampLocation": "center", "modificationDate": "2026-01-01T00:00:00Z"}
            for name, value in [("sym_h_2023-07-01_2023-07-01.csv", -100), ("sym_h_2023-06-30_2023-07-02.csv", -101)]:
                path = folder / name
                path.write_text(f"#{json.dumps(header)}\n2023-07-01T00:00:00Z,{value},10\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Conflicting Kyoto duplicate"):
                audit_kyoto(folder, "sym_h", (date(2023, 7, 1), date(2023, 7, 1)))


if __name__ == "__main__":
    unittest.main()
