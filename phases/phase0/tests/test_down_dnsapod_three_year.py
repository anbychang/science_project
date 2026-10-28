"""Checks for the full three-year DNSAPOD download selection."""

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from phases.phase0.code.data.density.down_dnsapod_three_year import (
    download_three_year,
    required_days,
)


class RequiredDaysTest(unittest.TestCase):
    """Input: date bounds. Output: exact UTC day selection."""

    def test_inclusive_days(self) -> None:
        """Input: two UTC days. Output: both day identifiers."""
        self.assertEqual(
            required_days(date(2024, 2, 28), date(2024, 3, 1)),
            {"20240228", "20240229", "20240301"},
        )

    def test_reversed_range(self) -> None:
        """Input: reversed bounds. Output: ValueError."""
        with self.assertRaises(ValueError):
            required_days(date(2024, 3, 1), date(2024, 2, 28))

    def test_existing_manifest_is_not_overwritten(self) -> None:
        """Input: existing range manifest. Output: refusal before any request."""
        with TemporaryDirectory() as folder:
            path = Path(folder) / "manifest_dnsapod_20240228_20240301.json"
            path.write_text("retained", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                download_three_year(date(2024, 2, 28), date(2024, 3, 1), Path(folder))
            self.assertEqual(path.read_text(encoding="utf-8"), "retained")


if __name__ == "__main__":
    unittest.main()
