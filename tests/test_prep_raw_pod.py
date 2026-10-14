"""Check POD weather-block alignment."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from satellite_orbit.data.prep_raw_pod import prepare_source_file, weather_block_time
from satellite_orbit.data.prep_raw_schema import create_tables


class PodWeatherBlockTest(unittest.TestCase):
    """Input: UTC POD times near a 3-hour boundary
    Output: their official weather-block starts"""

    def test_time_before_boundary_uses_previous_block(self):
        """Input: 02:59 UTC
        Output: 00:00 UTC block start"""
        time_utc = datetime(2026, 1, 1, 2, 59, tzinfo=timezone.utc)

        self.assertEqual(
            weather_block_time(time_utc),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_time_at_boundary_uses_new_block(self):
        """Input: 03:00 UTC
        Output: 03:00 UTC block start"""
        time_utc = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)

        self.assertEqual(weather_block_time(time_utc), time_utc)

    def test_rejects_a_revised_source_without_deleting_raw_states(self):
        """Input: source file name with a changed signature
        Output: original raw state and signature remain stored"""
        with tempfile.TemporaryDirectory() as temp_folder:
            zip_path = Path(temp_folder) / "POD.ZIP"
            zip_path.write_bytes(b"revised source")
            connection = sqlite3.connect(":memory:")
            create_tables(connection)
            connection.execute(
                "INSERT INTO source_files VALUES (1, 'POD.ZIP', 'old-signature')"
            )
            connection.execute(
                "INSERT INTO swarm_a_states VALUES (1, 1, 1, 1, 1, 1, 1, 1, 1)"
            )

            with self.assertRaises(ValueError):
                prepare_source_file(connection, zip_path)

            self.assertEqual(
                connection.execute("SELECT signature FROM source_files").fetchone()[0],
                "old-signature",
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM swarm_a_states").fetchone()[0],
                1,
            )
            connection.close()


if __name__ == "__main__":
    unittest.main()
