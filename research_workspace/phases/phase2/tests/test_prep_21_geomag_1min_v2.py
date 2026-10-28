"""Check raw-minute preservation and missing-value boundaries for P2.1."""

import csv
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from research_workspace.phases.phase2.code.prep_21_geomag_1min import kyoto_rows, sme_rows


class GeomagMinuteTest(unittest.TestCase):
    """Input: small raw CSV fixtures. Output: validated one-minute records."""

    def test_sme_fill_becomes_null_without_changing_other_minutes(self):
        """Input: complete SME day with one fill. Output: one missing minute."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "SME_20230701.csv"
            first_second = int(datetime(2023, 7, 1, tzinfo=timezone.utc).timestamp())
            with path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.writer(output)
                writer.writerow(("tval", "SME", "SMEnum"))
                for minute in range(1440):
                    writer.writerow((first_second + 60 * minute,
                                     999999 if minute == 1 else 12.5,
                                     0 if minute == 1 else 23))
            rows = list(sme_rows(path, date(2023, 7, 1)))
        self.assertEqual((rows[1][1], rows[1][2], rows[1][3]), (None, 0, 0))
        self.assertEqual((rows[0][1], rows[0][2], rows[0][3]), (12.5, 23, 1))
        self.assertEqual(rows[0][5] - rows[0][0], 60_000_000)

    def test_sme_rejects_incomplete_day(self):
        """Input: one-minute SME file. Output: explicit incomplete-day error."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "SME_20230701.csv"
            path.write_text("tval,SME,SMEnum\n1688169600,10,20\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                list(sme_rows(path, date(2023, 7, 1)))

    def test_kyoto_keeps_signed_symh_and_skips_fill(self):
        """Input: signed HAPI values with fill. Output: observed source minutes."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sym_h.csv"
            path.write_text(
                "#{}\n2023-07-01T00:00:00Z,-120,10\n"
                "2023-07-01T00:01:00Z,99999,10\n",
                encoding="utf-8",
            )
            rows = list(kyoto_rows(path, date(2023, 7, 1), date(2023, 7, 1)))
        self.assertEqual(rows, [(-120, 10, "sym_h.csv", 1688169600000000)])


if __name__ == "__main__":
    unittest.main()
