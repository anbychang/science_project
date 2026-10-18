"""Check chunk-local signed 3-, 6-, and 12-hour rate storage."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_07_decay_rate import (
    ALGORITHM_VERSION,
    BACKWARD_INTERVAL_SAMPLES,
    create_decay_rate_table,
    write_decay_rates,
)
from satellite_orbit.data.pod.prep_06_orbit_10min import create_orbit_10min_table


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
    Output: chunk-local signed 3-, 6-, and 12-hour semi-major-axis rates"""

    def test_schema_migration_refuses_populated_analysis_output(self):
        """Input: legacy decay schema referenced by final analysis output
        Output: migration fails before SQLite foreign-key failure"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "legacy.sqlite"
            with sqlite3.connect(database_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE swarm_a_orbit_decay_10min (
                        time_us INTEGER PRIMARY KEY,
                        legacy_value REAL
                    );
                    CREATE TABLE swarm_a_analysis_10min (
                        time_us INTEGER PRIMARY KEY,
                        FOREIGN KEY (time_us)
                            REFERENCES swarm_a_orbit_decay_10min(time_us)
                    );
                    INSERT INTO swarm_a_orbit_decay_10min VALUES (1, 1.0);
                    INSERT INTO swarm_a_analysis_10min VALUES (1);
                    """
                )

                with self.assertRaisesRegex(ValueError, "analysis output exists"):
                    create_decay_rate_table(connection)
            connection.close()

    def test_constant_series_has_zero_derivative(self):
        """Input: one 12-hour constant interval
        Output: its start row has zero semi-major-axis rate"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "constant.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(
                    connection,
                    [6_800_000.0] * (BACKWARD_INTERVAL_SAMPLES + 1),
                    1,
                )
            connection.close()

            result = write_decay_rates(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_row = connection.execute(
                    "SELECT time_us, semi_major_axis_orbit_mean_m, "
                    "da_dt_3h_backward_m_s, da_dt_3h_backward_m_day, "
                    "da_dt_6h_backward_m_s, da_dt_6h_backward_m_day, "
                    "da_dt_12h_backward_m_s, da_dt_12h_backward_m_day, "
                    "chunk_id, algorithm_version "
                    "FROM swarm_a_orbit_decay_10min"
                ).fetchone()
            connection.close()

        self.assertEqual(
            result,
            {"input_rows": 73, "contiguous_runs": 1, "stored_rows": 1},
        )
        self.assertEqual(
            stored_row[0], START_TIME_US + BACKWARD_INTERVAL_SAMPLES * TEN_MINUTES_US
        )
        self.assertAlmostEqual(stored_row[1], 6_800_000.0, places=6)
        for value in stored_row[2:8]:
            self.assertAlmostEqual(value, 0.0, places=15)
        self.assertEqual(stored_row[8:], (1, ALGORITHM_VERSION))

    def test_rebuild_clears_stale_release_audit_metadata(self):
        """Input: modified decay input with an old release manifest
        Output: release evidence is removed until P1.7 runs again"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "stale-audit.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(
                    connection,
                    [6_800_000.0] * (BACKWARD_INTERVAL_SAMPLES + 1),
                    1,
                )
                connection.executemany(
                    "INSERT INTO metadata VALUES (?, ?)",
                    [
                        ("p1_7_release_status", "working_audit_pass"),
                        ("p1_7_release_manifest", "old"),
                    ],
                )

            write_decay_rates(database_path)

            with sqlite3.connect(database_path) as connection:
                stale_rows = connection.execute(
                    "SELECT name FROM metadata WHERE name LIKE 'p1_7_release_%'"
                ).fetchall()
            connection.close()

        self.assertEqual(stale_rows, [])

    def test_linear_decline_has_negative_semi_major_axis_rate(self):
        """Input: 75 values declining at 1.2 m/day
        Output: every released row has the known derivative and negative daily rate"""
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
                    "SELECT da_dt_3h_backward_m_s, da_dt_3h_backward_m_day, "
                    "da_dt_6h_backward_m_s, da_dt_6h_backward_m_day, "
                    "da_dt_12h_backward_m_s, da_dt_12h_backward_m_day "
                    "FROM swarm_a_orbit_decay_10min ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(len(stored_rows), 75 - BACKWARD_INTERVAL_SAMPLES)
        for stored_row in stored_rows:
            for derivative_m_s, derivative_m_day in zip(stored_row[::2], stored_row[1::2]):
                self.assertAlmostEqual(derivative_m_s, -decline_m_day / 86_400, places=12)
                self.assertAlmostEqual(derivative_m_day, -decline_m_day, places=8)

    def test_first_rate_compares_with_12_hours_earlier(self):
        """Input: a changed 73rd sample
        Output: first rate uses sample zero, not a future sample"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "backward.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(
                    connection,
                    [6_800_000.0] * BACKWARD_INTERVAL_SAMPLES + [6_799_900.0],
                    1,
                )

            write_decay_rates(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_row = connection.execute(
                    "SELECT time_us, da_dt_3h_backward_m_s, da_dt_3h_backward_m_day, "
                    "da_dt_6h_backward_m_s, da_dt_6h_backward_m_day, "
                    "da_dt_12h_backward_m_s, da_dt_12h_backward_m_day "
                    "FROM swarm_a_orbit_decay_10min"
                ).fetchone()
            connection.close()

        self.assertEqual(
            stored_row[0],
            START_TIME_US + BACKWARD_INTERVAL_SAMPLES * TEN_MINUTES_US,
        )
        for offset, hours in ((1, 3), (3, 6), (5, 12)):
            self.assertAlmostEqual(stored_row[offset], -100.0 / (hours * 3_600), places=14)
            self.assertAlmostEqual(stored_row[offset + 1], -100.0 * 24 / hours, places=10)

    def test_gap_splits_runs_without_cross_gap_fit(self):
        """Input: two 12-hour runs separated by one missing 10-minute bin
        Output: each rate interval stays within one side of the gap"""
        values_m = [6_800_000.0] * (BACKWARD_INTERVAL_SAMPLES + 1)
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "gap.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(connection, values_m, 1)
                add_orbit_rows(
                    connection,
                    [6_900_000.0] * (BACKWARD_INTERVAL_SAMPLES + 1),
                    1,
                    start_index=BACKWARD_INTERVAL_SAMPLES + 2,
                )
            connection.close()

            result = write_decay_rates(database_path)
            with sqlite3.connect(database_path) as connection:
                mean_values = connection.execute(
                    "SELECT semi_major_axis_orbit_mean_m "
                    "FROM swarm_a_orbit_decay_10min ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(result, {"input_rows": 146, "contiguous_runs": 2, "stored_rows": 2})
        self.assertAlmostEqual(mean_values[0][0], 6_800_000.0, places=6)
        self.assertAlmostEqual(mean_values[1][0], 6_900_000.0, places=6)

    def test_chunk_boundary_splits_runs_without_cross_chunk_fit(self):
        """Input: two adjacent 12-hour chunks
        Output: each rate interval stays inside its chunk"""
        values_m = [6_800_000.0] * (BACKWARD_INTERVAL_SAMPLES + 1)
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "chunks.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(connection, values_m, 1)
                add_orbit_rows(
                    connection,
                    [6_900_000.0] * (BACKWARD_INTERVAL_SAMPLES + 1),
                    2,
                    start_index=BACKWARD_INTERVAL_SAMPLES + 1,
                )
            connection.close()

            result = write_decay_rates(database_path)
            with sqlite3.connect(database_path) as connection:
                stored_rows = connection.execute(
                    "SELECT semi_major_axis_orbit_mean_m, chunk_id "
                    "FROM swarm_a_orbit_decay_10min ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(result, {"input_rows": 146, "contiguous_runs": 2, "stored_rows": 2})
        self.assertAlmostEqual(stored_rows[0][0], 6_800_000.0, places=6)
        self.assertAlmostEqual(stored_rows[1][0], 6_900_000.0, places=6)
        self.assertEqual([row[1] for row in stored_rows], [1, 2])

    def test_12_hours_requires_73_ten_minute_samples(self):
        """Input: only 72 consecutive 10-minute samples
        Output: no incomplete 12-hour interval rate"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "short.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_orbit_rows(connection, [6_800_000.0] * BACKWARD_INTERVAL_SAMPLES, 1)
            connection.close()

            result = write_decay_rates(database_path)

        self.assertEqual(
            result,
            {
                "input_rows": BACKWARD_INTERVAL_SAMPLES,
                "contiguous_runs": 1,
                "stored_rows": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
