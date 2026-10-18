"""Check downloaded geomagnetic files cover the requested end date."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from satellite_orbit.data.geomagnetic.down_geomagnetic import (
    MAX_DOWNLOAD_DAYS,
    _check_download_coverage,
    download_geomagnetic,
    download_geomagnetic_range,
)


class GeomagneticDownloadTest(unittest.TestCase):
    """Input: small downloaded geomagnetic CSV files
    Output: coverage validation result"""

    def test_accepts_file_reaching_requested_last_day(self):
        """Input: file with an observation on the requested end date
        Output: successful coverage validation"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            file_path = Path(temporary_folder) / "geomagnetic.csv"
            file_path.write_text("2025-12-31T23:59:00Z,-10,1\n", encoding="utf-8")

            result = _check_download_coverage(
                file_path,
                "2025-12-31",
                "2025-12-31",
            )

        self.assertIsNone(result)

    def test_rejects_file_ending_before_requested_last_day(self):
        """Input: file that WDC stopped before the requested end date
        Output: clear incomplete-download error"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            file_path = Path(temporary_folder) / "geomagnetic.csv"
            file_path.write_text("2025-10-18T10:40:00Z,-10,1\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Download a shorter date range"):
                _check_download_coverage(
                    file_path,
                    "2025-01-01",
                    "2025-12-31",
                )

    def test_rejects_file_starting_after_requested_first_day(self):
        """Input: file without the requested first day
        Output: clear incomplete-download error"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            file_path = Path(temporary_folder) / "geomagnetic.csv"
            file_path.write_text("2025-10-18T10:40:00Z,-10,1\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "starts at"):
                _check_download_coverage(
                    file_path,
                    "2025-01-01",
                    "2025-12-31",
                )

    def test_rejects_a_range_above_the_wdc_safe_limit(self):
        """Input: request longer than the WDC safe range
        Output: clear range-limit error before download"""
        with self.assertRaisesRegex(
            ValueError,
            f"at most {MAX_DOWNLOAD_DAYS} days",
        ):
            download_geomagnetic("2025-01-01", "2025-12-31")

    def test_splits_a_long_range_into_safe_requests(self):
        """Input: 181 requested days.
        Output: two sequential requests no longer than the source limit."""
        with patch(
            "satellite_orbit.data.geomagnetic.down_geomagnetic.download_geomagnetic",
            return_value={},
        ) as download_mock:
            download_geomagnetic_range("2025-01-01", "2025-06-30")

        self.assertEqual(
            [call.args[:2] for call in download_mock.call_args_list],
            [("2025-01-01", "2025-06-29"), ("2025-06-30", "2025-06-30")],
        )


if __name__ == "__main__":
    unittest.main()
