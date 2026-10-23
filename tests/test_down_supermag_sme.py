"""Check SuperMAG SME download parsing without using the network."""

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from satellite_orbit.data.geomagnetic.down_supermag_sme import (
    DEFAULT_DATES,
    DEFAULT_OUTPUT_FOLDER,
    api_records,
    download_range,
    row_count,
    sme_rows,
    write_day,
)


class SupermagSmeDownloadTest(unittest.TestCase):
    """Input: synthetic SuperMAG response. Output: auditable daily SME CSV."""

    def test_default_output_folder_is_directly_under_data(self):
        """Input: downloader defaults. Output: direct data/sme destination."""
        self.assertEqual(DEFAULT_OUTPUT_FOLDER, Path("data/sme"))

    def test_default_dates_end_at_2026_first_half(self):
        """Input: downloader defaults. Output: fixed research date range."""
        self.assertEqual(DEFAULT_DATES, (date(2014, 1, 1), date(2026, 6, 30)))

    def test_keeps_sme_and_station_count(self):
        """Input: lower-case API fields. Output: named raw SME row."""
        records = api_records(b'OK\n[{"tval": 1, "sme": 240, "num": 18}]')

        self.assertEqual(sme_rows(records), [(1, 240, 18)])

    def test_rejects_empty_api_record_list(self):
        """Input: empty JSON record list. Output: explicit retryable error."""
        with self.assertRaisesRegex(ValueError, "empty"):
            api_records(b"[]")

    def test_rejects_ok_without_records(self):
        """Input: bare API OK response. Output: explicit retryable error."""
        with self.assertRaisesRegex(ValueError, "no records"):
            api_records(b"OK")

    def test_writes_expected_raw_columns(self):
        """Input: SME rows. Output: exact raw CSV shape and count."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_folder:
            path = Path(temporary_folder) / "SME_20240510.csv"
            write_day(path, [(1, 240, 18), (2, 250, None)])
            with path.open(encoding="utf-8", newline="") as source:
                rows = list(csv.reader(source))

            self.assertEqual(rows[0], ["tval", "SME", "SMEnum"])
            self.assertEqual(rows[1], ["1", "240", "18"])
            self.assertEqual(rows[2], ["2", "250", ""])
            self.assertEqual(row_count(path), 2)

    def test_rejects_missing_user_id_before_creating_output(self):
        """Input: empty SuperMAG user ID. Output: no partial output folder."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_folder:
            output_folder = Path(temporary_folder) / "sme"

            with self.assertRaisesRegex(ValueError, "SUPERMAG_USER_ID"):
                download_range((date(2024, 5, 10), date(2024, 5, 10)), "", output_folder)

            self.assertFalse(output_folder.exists())


if __name__ == "__main__":
    unittest.main()
