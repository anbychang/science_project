import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from satellite_orbit.data.density.down_swarm_density_pod import (
    required_source_days,
    select_source_files,
    verify_zip,
)


def source_file(day: str, version: int) -> dict:
    """Input: UTC day and version. Output: synthetic ESA DNSAPOD record."""
    name = f"SW_OPER_DNSAPOD_2__{day}T000000_{day}T235930_{version:04d}.ZIP"
    return {"name": name, "path": f"source/{name}", "size": 1}


class PodDensityDownloadTest(unittest.TestCase):
    def test_required_days_include_both_partial_edge_days(self):
        """Input: one t0 at midday. Output: seven intersected UTC days."""
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "storms.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    "CREATE TABLE storm_candidate_v1 "
                    "(t0_time_us INTEGER, symh_screening_status TEXT)"
                )
                storm_time_us = int(
                    datetime(2024, 1, 10, 12, tzinfo=timezone.utc).timestamp()
                    * 1_000_000
                )
                connection.execute(
                    "INSERT INTO storm_candidate_v1 VALUES (?, 'selected')",
                    (storm_time_us,),
                )
                connection.commit()
            finally:
                connection.close()

            days = required_source_days(database_path)

        self.assertEqual(days, {f"202401{day:02d}" for day in range(8, 15)})

    def test_selects_latest_pod_version_only(self):
        """Input: mixed products and versions. Output: latest requested POD ZIP."""
        selected = select_source_files(
            [
                source_file("20240108", 201),
                source_file("20240108", 301),
                source_file("20240109", 301),
                {"name": "SW_OPER_DNSAACC_2__20240108T000000_20240108T235950_0301.ZIP"},
            ],
            {"20240108"},
        )

        self.assertEqual(selected[0]["name"], source_file("20240108", 301)["name"])

    def test_rejects_missing_day(self):
        """Input: missing required POD day. Output: explicit error."""
        with self.assertRaisesRegex(ValueError, "20240109"):
            select_source_files([source_file("20240108", 301)], {"20240109"})

    def test_verifies_zip_contents_and_byte_count(self):
        """Input: local ZIP. Output: accepted matching archive, rejected wrong size."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.ZIP"
            with ZipFile(path, "w") as archive:
                archive.writestr("sample.HDR", "test")
            verify_zip(path, path.stat().st_size)
            with self.assertRaisesRegex(ValueError, "Wrong byte count"):
                verify_zip(path, path.stat().st_size + 1)


if __name__ == "__main__":
    unittest.main()
