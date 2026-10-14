"""Check that raw density rows are not replaced."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from satellite_orbit.data.prep_raw_density import write_density_folder
from satellite_orbit.data.prep_raw_schema import create_tables


class DensitySQLiteTest(unittest.TestCase):
    """Input: density files with the same observation time
    Output: first raw row remains stored"""

    def test_does_not_replace_an_existing_density_observation(self):
        """Input: two source files at one time with different density values
        Output: original raw density value remains stored"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            folder = Path(temporary_folder)
            (folder / "first.ZIP").write_bytes(b"first")
            connection = sqlite3.connect(":memory:")
            create_tables(connection)
            first_point = {
                "time": datetime(2024, 5, 1, tzinfo=timezone.utc),
                "density_kg_m3": 1.0,
                "altitude_m": 400000.0,
                "latitude_deg": 1.0,
                "longitude_deg": 2.0,
                "local_solar_time_h": 3.0,
            }
            with patch(
                "satellite_orbit.data.prep_raw_density.load_swarm_density",
                return_value=[first_point],
            ):
                write_density_folder(connection, folder)

            (folder / "second.ZIP").write_bytes(b"second")
            revised_point = first_point | {"density_kg_m3": 9.0}
            with patch(
                "satellite_orbit.data.prep_raw_density.load_swarm_density",
                return_value=[revised_point],
            ):
                write_density_folder(connection, folder)

            self.assertEqual(
                connection.execute(
                    "SELECT density_kg_m3 FROM swarm_a_density"
                ).fetchone()[0],
                1.0,
            )
            connection.close()


if __name__ == "__main__":
    unittest.main()
