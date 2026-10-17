"""Check chunk-local 10-minute smoothing and decay-rate storage."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_derived_decay_rate import (
    ALGORITHM_VERSION,
    EDGE_SAMPLES,
    WINDOW_SAMPLES,
    create_decay_rate_table,
    write_decay_rates,
)
from satellite_orbit.data.pod.prep_derived_orbit_10min import create_orbit_10min_table


START_TIME_US = 1_800_000_000_000_000
TEN_MINUTES_US = 600_000_000


def create_database(database_path):
    """Input: SQLite path
    Output: database with P1.5-B and P1.5-C/D tables"""
    with sqlite3.connect(database_path) as connection:
        create_tables(connection)
        create_orbit_10min_table(connection)
        create_decay_rate_table(connection)
    connection.close()


def add_orbit_rows(connection, values_m, chunk_id, start_index=0):
    """Input: semi-major-axis values for one regular chunk run
    Output: matching P1.5-B rows stored"""
    connection.executemany(
        "INSERT INTO swarm_a_orbit_10min VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                START_TIME_US + (start_index + index) * TEN_MINUTES_US,
                value_m,
                60,
                10.0,
                chunk_id,
                "test",
            )
            for index, value_m in enumerate(values_m)
        ],
    )


class DecayRateStorageTest(unittest.TestCase):
    """Input: synthetic 10-minute mean-orbit rows
    Output: chunk-local smooth semi-major axis and decay rates"""

    def test_constant_series_has_zero_derivative(self):
        """Input: 73 constant 10-minute values
        Output: centered row has zero decay rate"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "constant.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(connection, [6_800_000.0] * WINDOW_SAMPLES, 1)
            connection.close()

            result = write_decay_rates(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_row = connection.execute(
                    "SELECT semi_major_axis_smooth_m, da_dt_smooth_m_s, "
                    "decay_rate_smooth_m_day, chunk_id, algorithm_version "
                    "FROM swarm_a_orbit_decay_10min"
                ).fetchone()
            connection.close()

        self.assertEqual(result, {"input_rows": 73, "contiguous_runs": 1, "stored_rows": 1})
        self.assertAlmostEqual(stored_row[0], 6_800_000.0, places=6)
        self.assertAlmostEqual(stored_row[1], 0.0, places=15)
        self.assertAlmostEqual(stored_row[2], 0.0, places=10)
        self.assertEqual(stored_row[3:], (1, ALGORITHM_VERSION))

    def test_linear_decline_has_positive_decay_rate(self):
        """Input: 75 values declining at 1.2 m/day
        Output: every released row has the known derivative and positive decay"""
        decline_m_day = 1.2
        values_m = [
            6_800_000.0 - decline_m_day * index * 600 / 86_400
            for index in range(75)
        ]
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "linear.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(connection, values_m, 7)
            connection.close()

            write_decay_rates(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_rows = connection.execute(
                    "SELECT da_dt_smooth_m_s, decay_rate_smooth_m_day "
                    "FROM swarm_a_orbit_decay_10min ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(len(stored_rows), 75 - 2 * EDGE_SAMPLES)
        for derivative_m_s, decay_m_day in stored_rows:
            self.assertAlmostEqual(derivative_m_s, -decline_m_day / 86_400, places=14)
            self.assertAlmostEqual(decay_m_day, decline_m_day, places=9)

    def test_gap_splits_runs_without_cross_gap_fit(self):
        """Input: two 73-row runs separated by one missing 10-minute bin
        Output: each center is smoothed only from its own side of the gap"""
        values_m = [6_800_000.0] * WINDOW_SAMPLES
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "gap.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(connection, values_m, 1)
                add_orbit_rows(
                    connection,
                    [6_900_000.0] * WINDOW_SAMPLES,
                    1,
                    start_index=WINDOW_SAMPLES + 1,
                )
            connection.close()

            result = write_decay_rates(database_path)
            with sqlite3.connect(database_path) as connection:
                smooth_values = connection.execute(
                    "SELECT semi_major_axis_smooth_m "
                    "FROM swarm_a_orbit_decay_10min ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(result, {"input_rows": 146, "contiguous_runs": 2, "stored_rows": 2})
        self.assertAlmostEqual(smooth_values[0][0], 6_800_000.0, places=6)
        self.assertAlmostEqual(smooth_values[1][0], 6_900_000.0, places=6)

    def test_chunk_boundary_splits_runs_without_cross_chunk_fit(self):
        """Input: two adjacent 73-row chunks
        Output: each center is smoothed only from its own chunk"""
        values_m = [6_800_000.0] * WINDOW_SAMPLES
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "chunks.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(connection, values_m, 1)
                add_orbit_rows(connection, [6_900_000.0] * WINDOW_SAMPLES, 2, start_index=73)
            connection.close()

            result = write_decay_rates(database_path)
            with sqlite3.connect(database_path) as connection:
                stored_rows = connection.execute(
                    "SELECT semi_major_axis_smooth_m, chunk_id "
                    "FROM swarm_a_orbit_decay_10min ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(result, {"input_rows": 146, "contiguous_runs": 2, "stored_rows": 2})
        self.assertAlmostEqual(stored_rows[0][0], 6_800_000.0, places=6)
        self.assertAlmostEqual(stored_rows[1][0], 6_900_000.0, places=6)
        self.assertEqual([row[1] for row in stored_rows], [1, 2])


if __name__ == "__main__":
    unittest.main()
