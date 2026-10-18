"""Check POD weather-block alignment."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from satellite_orbit.data.database.prep_raw_identifiers import time_to_us
from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_01_raw_pod import (
    prepare_source_file,
    weather_block_time,
    write_pod_file,
)


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
                "INSERT INTO source_files (source_id, file_name, signature) "
                "VALUES (1, 'POD.ZIP', 'old-signature')"
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

    def test_rejects_when_loaded_state_count_differs_from_sp3_inventory(self):
        """Input: SP3 inventory with two epochs but one loaded state
        Output: failure and no partial raw POD records"""
        with tempfile.TemporaryDirectory() as temp_folder:
            zip_path = Path(temp_folder) / "POD.ZIP"
            zip_path.write_bytes(b"test pod")
            time_utc = datetime(2026, 1, 1, tzinfo=timezone.utc)
            connection = sqlite3.connect(":memory:")
            create_tables(connection)

            with (
                patch(
                    "satellite_orbit.data.pod.prep_01_raw_pod.load_swarm_pod",
                    return_value=[
                        {
                            "time": time_utc,
                            "position_m": [1.0, 2.0, 3.0],
                            "velocity_m_s": [4.0, 5.0, 6.0],
                        }
                    ],
                ),
                patch(
                    "satellite_orbit.data.pod.prep_01_raw_pod.load_sp3_inventory",
                    return_value={"epoch_count": 2},
                ),
            ):
                with self.assertRaisesRegex(ValueError, "inventory=2, loaded=1"):
                    write_pod_file(connection, zip_path, {time_to_us(time_utc)})

            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM swarm_a_states").fetchone()[0],
                0,
            )
            connection.close()

    def test_rejects_when_kept_state_is_already_stored(self):
        """Input: one loaded state whose time already exists
        Output: clear count failure instead of silent INSERT OR IGNORE"""
        with tempfile.TemporaryDirectory() as temp_folder:
            zip_path = Path(temp_folder) / "POD.ZIP"
            zip_path.write_bytes(b"test pod")
            time_utc = datetime(2026, 1, 1, tzinfo=timezone.utc)
            connection = sqlite3.connect(":memory:")
            create_tables(connection)
            connection.execute(
                "INSERT INTO swarm_a_states VALUES (?, 1, 1, 1, 1, 1, 1, ?, 1)",
                (1, 1),
            )

            with (
                patch(
                    "satellite_orbit.data.pod.prep_01_raw_pod.load_swarm_pod",
                    return_value=[
                        {
                            "time": time_utc,
                            "position_m": [1.0, 2.0, 3.0],
                            "velocity_m_s": [4.0, 5.0, 6.0],
                        }
                    ],
                ),
                patch(
                    "satellite_orbit.data.pod.prep_01_raw_pod.load_sp3_inventory",
                    return_value={"epoch_count": 1},
                ),
                patch(
                    "satellite_orbit.data.pod.prep_01_raw_pod.pod_row",
                    return_value=(1, 1, 1, 1, 1, 1, 1, 1, 2),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "kept=1, inserted=0"):
                    write_pod_file(connection, zip_path, {time_to_us(time_utc)})

            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0],
                0,
            )
            connection.close()


if __name__ == "__main__":
    unittest.main()
