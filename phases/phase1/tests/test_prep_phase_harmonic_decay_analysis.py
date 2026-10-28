"""Check P1.6 and P1.7 for the four phase-harmonic candidates."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from phases.phase0.code.data.database.prep_raw_identifiers import time_to_us
from phases.phase0.code.data.database.prep_raw_schema import create_tables
from phases.phase1.code.prep_14_phase_harmonic_decay_candidates import (
    DECAY_CANDIDATE_TABLE,
    create_decay_candidate_table,
)
from phases.phase1.code.prep_10_phase_harmonic_decay_analysis import (
    ANALYSIS_TABLE,
    write_phase_harmonic_decay_analysis,
)
from phases.phase1.code.prep_11_phase_harmonic_decay_audit import (
    write_phase_harmonic_decay_audit,
)


def utc_time_us(day, hour, minute=0):
    """Input: 2024-05 UTC day, hour, and minute.
    Output: Unix time in microseconds."""
    return time_to_us(datetime(2024, 5, day, hour, minute, tzinfo=timezone.utc))


def weather_values(time_us):
    """Input: weather source time.
    Output: SQLite space_weather row values."""
    return (
        time_us, 130.0, 120.0, 111.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, "OBSERVED",
    )


def candidate_values(time_us, method, orbit_window):
    """Input: candidate key values.
    Output: P1.5.6 SQLite candidate row."""
    return (
        time_us, method, orbit_window, -80.0, 5.0, 20.0, 1800,
        time_us - 10_000_000, 1, "2,3" if method.startswith("joint") else "", "test-v1",
    )


class PhaseHarmonicCandidateAnalysisTest(unittest.TestCase):
    """Input: synthetic P1.5.6 candidates plus raw causal features.
    Output: P1.6 analysis and P1.7 audit records."""

    def test_stores_all_four_candidates_with_causal_feature_provenance(self):
        """Input: four candidates at one time and valid feature source rows.
        Output: four causal P1.6 rows keyed by candidate identity."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "phase.sqlite"
            self._create_fixture(database_path)
            result = write_phase_harmonic_decay_analysis(database_path)
            connection = sqlite3.connect(database_path)
            try:
                rows = connection.execute(f"""
                    SELECT decay_method, orbit_window, sym_h_nt, ap_source_time_us,
                           f107_source_time_us, f107a_source_time_us, quality_flags
                    FROM {ANALYSIS_TABLE}
                    ORDER BY decay_method, orbit_window
                """).fetchall()
            finally:
                connection.close()

        self.assertEqual(result, {"input_rows": 4, "stored_rows": 4})
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual(row[2], -40.0)
            self.assertEqual(row[-1], "ok")
            self.assertLessEqual(row[3], utc_time_us(10, 10))
            self.assertLessEqual(row[4], utc_time_us(10, 10))
            self.assertLessEqual(row[5], utc_time_us(10, 10))

    def test_audit_records_passing_three_year_candidate_branch(self):
        """Input: valid four-candidate analysis table.
        Output: P1.7 working audit metadata and row evidence."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "phase.sqlite"
            self._create_fixture(database_path)
            write_phase_harmonic_decay_analysis(database_path)
            manifest = write_phase_harmonic_decay_audit(database_path)

        self.assertEqual(manifest["audit_outcome"], "pass")
        self.assertEqual(manifest["row_counts"], {
            "p1_5_6_candidates": 4,
            "p1_6_candidate_analysis": 4,
        })

    def test_audit_rejects_future_weather_reference(self):
        """Input: analysis row changed to cite a later weather source.
        Output: P1.7 rejects a causal-contract violation."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "phase.sqlite"
            self._create_fixture(database_path)
            write_phase_harmonic_decay_analysis(database_path)
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(f"""
                    UPDATE {ANALYSIS_TABLE}
                    SET ap_source_time_us = time_us + 1
                """)
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "future_feature_references"):
                write_phase_harmonic_decay_audit(database_path)

    def _create_fixture(self, database_path):
        """Input: empty temporary SQLite path.
        Output: complete raw feature and P1.5.6 candidate fixture."""
        target_time_us = utc_time_us(10, 10)
        connection = sqlite3.connect(database_path)
        try:
            create_tables(connection)
            create_decay_candidate_table(connection)
            connection.executemany(
                f"INSERT INTO {DECAY_CANDIDATE_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    candidate_values(target_time_us, method, orbit_window)
                    for method in ("raw_b_l_local_ols", "joint_h2_h3_local_ols")
                    for orbit_window in (3, 5)
                ],
            )
            connection.executemany(
                "INSERT INTO space_weather VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [weather_values(utc_time_us(10, 9)), weather_values(utc_time_us(9, 0))],
            )
            connection.execute(
                "INSERT INTO geomagnetic (time_us, sym_h_nt) VALUES (?, ?)",
                (target_time_us, -40.0),
            )
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
