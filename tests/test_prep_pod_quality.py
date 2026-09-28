"""Check POD quality decisions and derived-table rebuilding."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.prep_sqlite_tables import create_tables
from satellite_orbit.data.prep_write_pod_quality import (
    create_quality_table,
    quality_row,
    starts_new_interval,
    write_pod_quality,
)


def valid_row():
    """Input: none
    Output: one usable POD row"""
    return {
        "time_us": 1_000_000,
        "x_m": 7_000_000.0,
        "y_m": 0.0,
        "z_m": 0.0,
        "vx_m_s": 0.0,
        "vy_m_s": 7_500.0,
        "vz_m_s": 0.0,
        "semi_major_axis_m": 7_000_000.0,
        "orbital_rejection_reason": None,
    }


class PodQualityTest(unittest.TestCase):
    """Input: small synthetic POD rows
    Output: expected usability decisions"""

    def test_accepts_valid_row(self):
        """Input: finite state and valid orbital element
        Output: usable row"""
        result = quality_row(valid_row(), None)
        self.assertEqual(result, (1_000_000, 1, None, None))

    def test_rejects_non_finite_state(self):
        """Input: state with NaN position
        Output: non_finite_state reason"""
        row = valid_row()
        row["x_m"] = float("nan")
        result = quality_row(row, None)
        self.assertEqual(result[2], "non_finite_state")

    def test_rejects_missing_orbital_element(self):
        """Input: state without P1.3 result
        Output: missing_orbital_element reason"""
        row = valid_row()
        row["semi_major_axis_m"] = None
        result = quality_row(row, None)
        self.assertEqual(result[2], "missing_orbital_element")

    def test_rejects_invalid_orbital_energy(self):
        """Input: P1.3 rejected orbital state
        Output: invalid_orbital_energy reason"""
        row = valid_row()
        row["orbital_rejection_reason"] = "Orbit state is not bound to Earth."
        result = quality_row(row, None)
        self.assertEqual(result[2], "invalid_orbital_energy")

    def test_starts_new_interval_at_source_boundary(self):
        """Input: adjacent rows from different source files
        Output: new interval"""
        row = valid_row()
        row["source_id"] = 2
        previous_row = {"time_us": 990_000, "source_id": 1, "is_usable": True}
        self.assertTrue(starts_new_interval(row, previous_row, 10_000))

    def test_starts_new_interval_after_gap(self):
        """Input: same-source rows with a missing 10-second observation
        Output: new interval"""
        row = valid_row()
        row["source_id"] = 1
        previous_row = {"time_us": 980_000, "source_id": 1, "is_usable": True}
        self.assertTrue(starts_new_interval(row, previous_row, 10_000))

    def test_continuous_usable_rows_keep_one_interval(self):
        """Input: adjacent usable rows from one source file
        Output: no new interval"""
        row = valid_row()
        row["source_id"] = 1
        previous_row = {"time_us": 990_000, "source_id": 1, "is_usable": True}
        self.assertFalse(starts_new_interval(row, previous_row, 10_000))

    def test_rejected_previous_row_starts_new_interval(self):
        """Input: usable row after a rejected row
        Output: new interval"""
        row = valid_row()
        row["source_id"] = 1
        previous_row = {"time_us": 990_000, "source_id": 1, "is_usable": False}
        self.assertTrue(starts_new_interval(row, previous_row, 10_000))

    def test_rebuild_removes_stale_quality_rows(self):
        """Input: raw POD rows and one obsolete derived row
        Output: only quality rows matching raw POD remain"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "quality.sqlite"
            with sqlite3.connect(database_path) as connection:
                create_tables(connection)
                connection.execute(
                    """
                    CREATE TABLE swarm_a_orbital_elements (
                        time_us INTEGER PRIMARY KEY,
                        semi_major_axis_m REAL,
                        rejection_reason TEXT
                    )
                    """
                )
                connection.executemany(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (0, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, 0, 1),
                        (10_000_000, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, 0, 1),
                    ],
                )
                connection.executemany(
                    "INSERT INTO swarm_a_orbital_elements VALUES (?, ?, ?)",
                    [(0, 7e6, None), (10_000_000, 7e6, None)],
                )
                create_quality_table(connection)
                connection.execute(
                    "INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
                    (99_000_000, 1, None, 99),
                )
            connection.close()

            result = write_pod_quality(database_path)

            with sqlite3.connect(database_path) as connection:
                quality_rows = connection.execute(
                    "SELECT time_us, interval_id FROM swarm_a_pod_quality ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(result["raw_rows"], 2)
        self.assertEqual(quality_rows, [(0, 1), (10_000_000, 1)])


if __name__ == "__main__":
    unittest.main()
