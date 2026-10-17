"""Check P1.7 release metadata with a synthetic final SQLite dataset."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_derived_decay_rate import create_decay_rate_table
from satellite_orbit.data.pod.prep_derived_orbit_10min import create_orbit_10min_table
from satellite_orbit.data.pod.prep_derived_orbital_elements import create_orbital_element_table
from satellite_orbit.data.pod.prep_derived_pod_quality import create_quality_table
from satellite_orbit.phase1.prep_derived_analysis_10min import create_analysis_10min_table
from satellite_orbit.phase1.prep_p1_7_release_audit import (
    REBUILD_COMMANDS,
    write_release_metadata,
)


TIME_US = 1_715_400_000_000_000


def add_release_fixture(connection):
    """Input: empty SQLite connection with raw schema
    Output: smallest complete P1.7 source-to-analysis chain"""
    create_orbit_10min_table(connection)
    create_orbital_element_table(connection)
    create_quality_table(connection)
    create_decay_rate_table(connection)
    create_analysis_10min_table(connection)
    connection.execute(
        "INSERT INTO source_files (source_id, file_name, signature) VALUES (?, ?, ?)",
        (1, "pod.ZIP", "pod-signature"),
    )
    connection.execute(
        "INSERT INTO space_weather VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (TIME_US, 120.0, 118.0, 117.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, "OBSERVED"),
    )
    connection.execute("INSERT INTO geomagnetic (time_us, sym_h_nt) VALUES (?, ?)", (TIME_US, -20.0))
    connection.execute(
        "INSERT INTO swarm_a_density VALUES (?, ?, ?, ?, ?, ?, ?)",
        (TIME_US, 1e-12, 500000.0, 1.0, 2.0, 12.0, "density.ZIP"),
    )
    connection.execute("INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (TIME_US, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, TIME_US, 1))
    connection.execute(
        "INSERT INTO swarm_a_orbital_elements VALUES (?, ?, ?)",
        (TIME_US, 6_850_000.0, None),
    )
    connection.execute("INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)", (TIME_US, 1, None, 1))
    connection.execute("CREATE TABLE swarm_a_mean_orbital_elements (time_us INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO swarm_a_mean_orbital_elements VALUES (?)", (TIME_US,))
    connection.execute(
        "INSERT INTO swarm_a_orbit_10min VALUES (?, ?, ?, ?, ?, ?)",
        (TIME_US, 6_850_000.0, 60, 10.0, 1, "p1.5"),
    )
    connection.execute(
        "INSERT INTO swarm_a_orbit_decay_10min VALUES (?, ?, ?, ?, ?, ?)",
        (TIME_US, 6_850_000.0, -0.001, 86.4, 1, "p1.5"),
    )
    connection.execute(
        "INSERT INTO swarm_a_analysis_10min VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (TIME_US, 6_850_000.0, -0.001, 86.4, 60, 10.0, 1, -20.0, TIME_US, TIME_US, 8.0, TIME_US, 120.0, TIME_US, 117.0, TIME_US, "OBSERVED", "", "p1.6"),
    )
    connection.executemany(
        "INSERT INTO metadata VALUES (?, ?)",
        [
            ("weather_signature", "weather-signature"),
            ("weather_preparation_version", "3"),
            ("mean_orbit_algorithm", "mean-v1"),
            ("orbit_10min_algorithm", "orbit-v1"),
            ("orbit_10min_bin_contract", "bin-v1"),
            ("orbit_decay_algorithm", "decay-v1"),
            ("orbit_decay_run_contract", "run-v1"),
            ("analysis_10min_algorithm", "analysis-v1"),
            ("analysis_10min_feature_contract", "feature-v1"),
        ],
    )


class P17ReleaseAuditTest(unittest.TestCase):
    """Input: complete synthetic P1 chain
    Output: immutable-raw release manifest and audit metadata"""

    def test_stores_deterministic_manifest_after_complete_audit(self):
        """Input: one valid P1.5/P1.6 row and raw provenance
        Output: pass status, coverage, policies, signatures, and rebuild commands"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.commit()
            finally:
                connection.close()

            manifest = write_release_metadata(
                database_path,
                {"git_head": "test-head", "git_dirty": False},
            )

            connection = sqlite3.connect(database_path)
            try:
                metadata = dict(connection.execute("SELECT name, value FROM metadata"))
            finally:
                connection.close()

        self.assertEqual(manifest["audit_outcome"], "pass")
        self.assertEqual(manifest["row_counts"]["swarm_a_analysis_10min"], 1)
        self.assertEqual(manifest["missingness"], {
            "raw_states_without_orbital_elements": 0,
            "orbital_elements_without_quality": 0,
            "usable_quality_without_mean_orbit": 0,
            "decay_rows_without_analysis": 0,
            "analysis_rows_without_decay": 0,
            "future_feature_references": 0,
            "invalid_pod_quality_rows": 0,
            "null_analysis_values": 0,
            "non_finite_analysis_rows": 0,
            "chunk_mismatch_rows": 0,
            "non_continuous_chunk_rows": 0,
        })
        self.assertEqual(manifest["raw_inputs"]["source_signature_sha256"], "145e8a679f718bfa8a2a4167e550d7156ff341554e19e2a4284274ff53e5c917")
        self.assertEqual(manifest["code_revision"], {"git_head": "test-head", "git_dirty": False})
        self.assertEqual(manifest["code_content"]["algorithm"], "sha256")
        self.assertTrue(manifest["code_content"]["digest"])
        self.assertIn(
            "satellite_orbit/phase1/prep_p1_7_release_audit.py",
            manifest["code_content"]["files"],
        )
        self.assertEqual(manifest["rebuild"]["status"], "not_executed")
        self.assertFalse(manifest["rebuild"]["clean_rebuild_executed"])
        self.assertEqual(manifest["rebuild"]["commands"], list(REBUILD_COMMANDS))
        self.assertEqual(metadata["p1_7_release_status"], "working_audit_pass")
        self.assertEqual(json.loads(metadata["p1_7_release_manifest"]), manifest)
        rebuild_commands = json.loads(metadata["p1_7_rebuild_commands"])
        self.assertEqual(rebuild_commands, list(REBUILD_COMMANDS))
        self.assertEqual(
            rebuild_commands,
            ["python -m satellite_orbit.phase1.prep_phase1_rebuild NEW_DATABASE"],
        )
        self.assertEqual(metadata["p1_7_rebuild_status"], "not_executed")

    def test_marks_frozen_only_with_explicit_clean_rebuild_evidence(self):
        """Input: valid final data and explicit fresh-rebuild evidence
        Output: frozen release metadata, not an automatic audit upgrade"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.commit()
            finally:
                connection.close()

            manifest = write_release_metadata(
                database_path,
                {"git_head": "test-head", "git_dirty": False},
                {"entry_point": "fresh_rebuild", "target_database": str(database_path)},
            )

            connection = sqlite3.connect(database_path)
            try:
                status = connection.execute(
                    "SELECT value FROM metadata WHERE name = 'p1_7_release_status'"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(manifest["rebuild"]["status"], "clean_rebuild_verified")
        self.assertEqual(status, "frozen")

    def test_rejects_raw_state_without_orbital_element(self):
        """Input: raw state missing its orbital result
        Output: audit rejects an incomplete raw-to-orbital chain"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (TIME_US + 10, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, TIME_US, 1),
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "raw_states_without_orbital_elements"):
                write_release_metadata(database_path)

    def test_rejects_orbital_element_without_quality_row(self):
        """Input: orbital element missing its quality result
        Output: audit rejects an incomplete orbital-to-quality chain"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute("INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (TIME_US + 10, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, TIME_US, 1))
                connection.execute("INSERT INTO swarm_a_orbital_elements VALUES (?, ?, ?)", (TIME_US + 10, 6_850_000.0, None))
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "orbital_elements_without_quality"):
                write_release_metadata(database_path)

    def test_rejects_usable_quality_row_without_mean_orbit(self):
        """Input: usable quality row missing its mean-orbit result
        Output: audit rejects an incomplete quality-to-mean chain"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute("INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (TIME_US + 10, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, TIME_US, 1))
                connection.execute("INSERT INTO swarm_a_orbital_elements VALUES (?, ?, ?)", (TIME_US + 10, 6_850_000.0, None))
                connection.execute("INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)", (TIME_US + 10, 1, None, 1))
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "usable_quality_without_mean_orbit"):
                write_release_metadata(database_path)

    def test_rejects_null_final_table_value(self):
        """Input: final analysis row with a missing feature label
        Output: audit rejects a final table NULL in any column"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    "UPDATE swarm_a_analysis_10min SET f107_data_type = NULL"
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "null_analysis_values"):
                write_release_metadata(database_path)

    def test_rejects_non_finite_final_table_value(self):
        """Input: final analysis row with an infinite numeric value
        Output: audit rejects non-finite final numeric output"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    "UPDATE swarm_a_analysis_10min SET sym_h_nt = 1e999"
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "non_finite_analysis_rows"):
                write_release_metadata(database_path)

    def test_rejects_chunk_mismatch_between_release_tables(self):
        """Input: analysis row with a different chunk ID
        Output: audit rejects a cross-chunk final join"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    "UPDATE swarm_a_analysis_10min SET chunk_id = 2"
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "chunk_mismatch_rows"):
                write_release_metadata(database_path)

    def test_rejects_gap_inside_analysis_chunk(self):
        """Input: two final rows 20 minutes apart in one chunk
        Output: audit rejects a discontinuous final analysis run"""
        later_time_us = TIME_US + 1_200_000_000
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    "INSERT INTO swarm_a_orbit_10min VALUES (?, ?, ?, ?, ?, ?)",
                    (later_time_us, 6_850_000.0, 60, 10.0, 1, "p1.5"),
                )
                connection.execute(
                    "INSERT INTO swarm_a_orbit_decay_10min VALUES (?, ?, ?, ?, ?, ?)",
                    (later_time_us, 6_850_000.0, -0.001, 86.4, 1, "p1.5"),
                )
                connection.execute(
                    """
                    INSERT INTO swarm_a_analysis_10min VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        later_time_us, 6_850_000.0, -0.001, 86.4, 60, 10.0, 1,
                        -20.0, TIME_US, TIME_US, 8.0, TIME_US, 120.0, TIME_US,
                        117.0, TIME_US, "OBSERVED", "", "p1.6",
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "non_continuous_chunk_rows"):
                write_release_metadata(database_path)


if __name__ == "__main__":
    unittest.main()
