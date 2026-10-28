"""Check P1.6 causal feature storage from synthetic SQLite records."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research_workspace.phases.phase0.code.data.database.prep_raw_identifiers import time_to_us
from research_workspace.phases.phase0.code.data.database.prep_raw_schema import create_tables
from research_workspace.phases.phase1.code.prep_06_orbit_10min import create_orbit_10min_table
from research_workspace.phases.phase1.code.prep_07_decay_rate import create_decay_rate_table
from research_workspace.phases.phase1.code.prep_08_analysis_10min import write_analysis_10min


def utc_time_us(hour, minute=0, day=10):
    """Input: 2024-05 UTC day, hour, and minute
    Output: Unix time in microseconds"""
    return time_to_us(datetime(2024, 5, day, hour, minute, tzinfo=timezone.utc))


def weather_values(time_us, ap_now, f107_sfu, f107a_last81_sfu, f107_data_type):
    """Input: raw weather values at one UTC block
    Output: SQLite space_weather value tuple"""
    return (
        time_us,
        f107_sfu,
        f107a_last81_sfu,
        f107a_last81_sfu,
        ap_now,
        ap_now,
        ap_now,
        ap_now,
        ap_now,
        ap_now,
        ap_now,
        f107_data_type,
    )


def add_orbit_rows(connection, times):
    """Input: SQLite connection and qualifying P1.5 times
    Output: matching orbit and decay records"""
    for index, time_us in enumerate(times):
        connection.execute(
            "INSERT INTO swarm_a_orbit_10min VALUES (?, ?, ?, ?, ?, ?)",
            (time_us, 6_850_000.0, 60, 10.0, 1, "p1.5"),
        )
        connection.execute(
            "INSERT INTO swarm_a_orbit_decay_10min VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                time_us,
                6_850_000.0,
                -0.001,
                -86.4,
                -0.001,
                -86.4,
                -0.001,
                -86.4,
                1,
                f"p1.5-{index}",
            ),
        )


class Analysis10MinuteStorageTest(unittest.TestCase):
    """Input: synthetic P1.5, weather, and SYM-H SQLite records
    Output: causal analysis rows with source-time provenance"""

    def test_preserves_orbits_and_records_causal_feature_provenance(self):
        """Input: exact, interpolated, missing, and future-only SYM-H cases
        Output: every orbit retained without future weather values"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "analysis_10min.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                create_orbit_10min_table(connection)
                create_decay_rate_table(connection)
                times = [
                    utc_time_us(9, 30),
                    utc_time_us(10),
                    utc_time_us(10, 10),
                    utc_time_us(10, 20),
                ]
                add_orbit_rows(connection, times)
                connection.executemany(
                    "INSERT INTO space_weather VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        weather_values(utc_time_us(9), 8.0, 130.0, 111.0, "PREDICTED"),
                        weather_values(
                            utc_time_us(0, day=9),
                            6.0,
                            129.0,
                            110.0,
                            "OBSERVED",
                        ),
                    ],
                )
                connection.executemany(
                    "INSERT INTO geomagnetic (time_us, sym_h_nt) VALUES (?, ?)",
                    [
                        (utc_time_us(10), -40.0),
                        (utc_time_us(10, 9), -50.0),
                        (utc_time_us(10, 11), -30.0),
                        (utc_time_us(10, 18), -60.0),
                        (utc_time_us(10, 21), -20.0),
                        (utc_time_us(10, 31), -10.0),
                    ],
                )
                connection.commit()
            finally:
                connection.close()

            result = write_analysis_10min(database_path)

            connection = sqlite3.connect(database_path)
            try:
                rows = connection.execute(
                    """
                    SELECT time_us, sym_h_nt, sym_h_left_time_us, sym_h_right_time_us,
                           ap_now, ap_source_time_us, f107_sfu, f107_source_time_us,
                           f107a_sfu, f107a_source_time_us, f107_data_type, quality_flags
                    FROM swarm_a_analysis_10min
                    ORDER BY time_us
                    """
                ).fetchall()
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(swarm_a_analysis_10min)")
                }
            finally:
                connection.close()

        self.assertEqual(result, {"input_rows": 4, "stored_rows": 4})
        self.assertIsNone(rows[0][1])
        self.assertEqual(rows[0][-1], "missing_sym_h")
        self.assertEqual(rows[1][1:4], (-40.0, utc_time_us(10), utc_time_us(10)))
        self.assertEqual(rows[2][1:4], (-40.0, utc_time_us(10, 9), utc_time_us(10, 11)))
        self.assertIsNone(rows[3][1])
        self.assertEqual(rows[3][-1], "missing_sym_h")
        for row in rows:
            self.assertLessEqual(row[5], row[0])
            self.assertLessEqual(row[7], row[0])
            self.assertLessEqual(row[9], row[0])
        self.assertEqual((rows[0][4], rows[0][6], rows[0][8]), (8.0, 129.0, 110.0))
        self.assertEqual(rows[0][10], "OBSERVED")
        self.assertNotIn("density_kg_m3", columns)


if __name__ == "__main__":
    unittest.main()
