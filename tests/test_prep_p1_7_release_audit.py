"""Check P1.7 release metadata with a synthetic final SQLite dataset."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_03_orbital_elements import create_orbital_element_table
from satellite_orbit.data.pod.prep_05_pod_quality import create_quality_table
from satellite_orbit.data.pod.prep_06_orbit_10min import (
    BIN_DURATION_US,
    create_orbit_10min_table,
)
from satellite_orbit.data.pod.prep_07_decay_rate import (
    BACKWARD_INTERVALS,
    BACKWARD_INTERVAL_SAMPLES,
    BACKWARD_INTERVAL_SECONDS,
    SECONDS_PER_DAY,
    create_decay_rate_table,
)
from satellite_orbit.phase1.prep_08_analysis_10min import create_analysis_10min_table
from satellite_orbit.phase1.prep_09_release_audit import (
    REBUILD_COMMANDS,
    write_release_metadata,
)


TIME_US = 1_715_400_000_000_000
PAST_TIME_US = TIME_US - BACKWARD_INTERVAL_SAMPLES * BIN_DURATION_US
PAST_3H_TIME_US = TIME_US - BACKWARD_INTERVALS[0][1] * BIN_DURATION_US
PAST_6H_TIME_US = TIME_US - BACKWARD_INTERVALS[1][1] * BIN_DURATION_US
CURRENT_SEMI_MAJOR_AXIS_M = 6_850_000.0
DERIVATIVE_M_S = -0.001
PAST_SEMI_MAJOR_AXIS_M = (
    CURRENT_SEMI_MAJOR_AXIS_M - DERIVATIVE_M_S * BACKWARD_INTERVAL_SECONDS
)
PAST_3H_SEMI_MAJOR_AXIS_M = CURRENT_SEMI_MAJOR_AXIS_M - DERIVATIVE_M_S * 3 * 3_600
PAST_6H_SEMI_MAJOR_AXIS_M = CURRENT_SEMI_MAJOR_AXIS_M - DERIVATIVE_M_S * 6 * 3_600
DERIVATIVE_M_DAY = DERIVATIVE_M_S * SECONDS_PER_DAY


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
        (TIME_US, CURRENT_SEMI_MAJOR_AXIS_M, None),
    )
    connection.execute("INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)", (TIME_US, 1, None, 1))
    connection.execute("CREATE TABLE swarm_a_mean_orbital_elements (time_us INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO swarm_a_mean_orbital_elements VALUES (?)", (TIME_US,))
    connection.execute(
        "INSERT INTO swarm_a_orbit_10min VALUES (?, ?, ?, ?, ?, ?)",
        (PAST_3H_TIME_US, PAST_3H_SEMI_MAJOR_AXIS_M, 60, 10.0, 1, "p1.5"),
    )
    connection.execute(
        "INSERT INTO swarm_a_orbit_10min VALUES (?, ?, ?, ?, ?, ?)",
        (PAST_6H_TIME_US, PAST_6H_SEMI_MAJOR_AXIS_M, 60, 10.0, 1, "p1.5"),
    )
    connection.execute(
        "INSERT INTO swarm_a_orbit_10min VALUES (?, ?, ?, ?, ?, ?)",
        (PAST_TIME_US, PAST_SEMI_MAJOR_AXIS_M, 60, 10.0, 1, "p1.5"),
    )
    connection.execute(
        "INSERT INTO swarm_a_orbit_10min VALUES (?, ?, ?, ?, ?, ?)",
        (TIME_US, CURRENT_SEMI_MAJOR_AXIS_M, 60, 10.0, 1, "p1.5"),
    )
    connection.execute(
        "INSERT INTO swarm_a_orbit_decay_10min VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            TIME_US, CURRENT_SEMI_MAJOR_AXIS_M,
            DERIVATIVE_M_S, DERIVATIVE_M_DAY,
            DERIVATIVE_M_S, DERIVATIVE_M_DAY,
            DERIVATIVE_M_S, DERIVATIVE_M_DAY,
            1, "p1.5",
        ),
    )
    connection.execute(
        "INSERT INTO swarm_a_analysis_10min VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            TIME_US, CURRENT_SEMI_MAJOR_AXIS_M,
            DERIVATIVE_M_S, DERIVATIVE_M_DAY,
            DERIVATIVE_M_S, DERIVATIVE_M_DAY,
            DERIVATIVE_M_S, DERIVATIVE_M_DAY,
            60, 10.0, 1, -20.0, TIME_US, TIME_US, 8.0, TIME_US,
            120.0, TIME_US, 117.0, TIME_US, "OBSERVED", "ok", "p1.6",
        ),
    )
    connection.executemany(
        "INSERT INTO metadata VALUES (?, ?)",
        [
            ("weather_signature", "weather-signature"),
            ("weather_preparation_version", "3"),
            ("orbital_element_algorithm", "two-body-v1"),
            ("orbital_element_mu_m3_s2", "398600441800000.0"),
            ("p1_4_quality_policy_version", "official-events-v1"),
            ("p1_4_official_orbit_events", "[]"),
            ("mean_orbit_algorithm", "mean-v1"),
            ("mean_orbit_input_policy", "valid-p1.3"),
            ("mean_orbit_input_frame", "GCRF"),
            ("mean_orbit_input_transform", "test-transform"),
            ("mean_orbit_gravity_field_degree_order", "5,0"),
            ("mean_orbit_m2", "0.0"),
            ("mean_orbit_implementation_fingerprint", "test-fingerprint"),
            ("orbit_10min_algorithm", "orbit-v1"),
            ("orbit_10min_bin_contract", "bin-v1"),
            ("orbit_decay_algorithm", "decay-v1"),
            ("orbit_decay_interval_hours", "3,6,12"),
            ("orbit_decay_interval_samples", "72"),
            ("orbit_decay_interval_seconds", "43200.0"),
            ("orbit_decay_time_convention", "interval-end"),
            ("orbit_decay_edge_exclusion", "first-72"),
            ("orbit_decay_run_contract", "run-v1"),
            ("orbit_decay_rate_definition", "difference-v1"),
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
            "invalid_optional_feature_missingness": 0,
            "chunk_mismatch_rows": 0,
            "non_continuous_chunk_rows": 0,
            "invalid_decay_contract_rows": 0,
        })
        self.assertEqual(manifest["raw_inputs"]["source_signature_sha256"], "145e8a679f718bfa8a2a4167e550d7156ff341554e19e2a4284274ff53e5c917")
        self.assertEqual(manifest["code_revision"], {"git_head": "test-head", "git_dirty": False})
        self.assertEqual(manifest["code_content"]["algorithm"], "sha256")
        self.assertTrue(manifest["code_content"]["digest"])
        self.assertIn(
            "satellite_orbit/phase1/prep_09_release_audit.py",
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
            ["python -m satellite_orbit.phase1.prep_phase1_rebuild NEW_DATABASE [MEAN_CACHE]"],
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

    def test_records_verified_mean_cache_without_claiming_clean_rebuild(self):
        """Input: valid final data and verified mean-orbit cache evidence
        Output: frozen cache reuse without a false clean-rebuild claim"""
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
                {
                    "entry_point": "fresh_raw_with_cache",
                    "mean_orbit_cache_database": "cache.sqlite",
                },
            )

        self.assertEqual(manifest["rebuild"]["status"], "verified_mean_orbit_cache_reuse")
        self.assertFalse(manifest["rebuild"]["clean_rebuild_executed"])

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

    def test_rejects_partial_optional_feature_missingness(self):
        """Input: final analysis row with a missing feature label
        Output: audit rejects a partial feature group"""
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

            with self.assertRaisesRegex(ValueError, "invalid_optional_feature_missingness"):
                write_release_metadata(database_path)

    def test_accepts_complete_missing_sym_h_group(self):
        """Input: all SYM-H fields missing with its controlled flag
        Output: audit keeps the orbit row without future-value filling"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    """
                    UPDATE swarm_a_analysis_10min
                    SET sym_h_nt = NULL,
                        sym_h_left_time_us = NULL,
                        sym_h_right_time_us = NULL,
                        quality_flags = 'missing_sym_h'
                    """
                )
                connection.commit()
            finally:
                connection.close()

            manifest = write_release_metadata(database_path)

        self.assertEqual(manifest["missingness"]["invalid_optional_feature_missingness"], 0)

    def test_accepts_complete_missing_space_weather_group(self):
        """Input: absent causal weather fields with its controlled flag
        Output: audit accepts the complete optional missing group"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    """
                    UPDATE swarm_a_analysis_10min
                    SET ap_now = NULL,
                        ap_source_time_us = NULL,
                        f107_sfu = NULL,
                        f107_source_time_us = NULL,
                        f107a_sfu = NULL,
                        f107a_source_time_us = NULL,
                        f107_data_type = NULL,
                        quality_flags = 'missing_space_weather'
                    """
                )
                connection.commit()
            finally:
                connection.close()

            manifest = write_release_metadata(database_path)

        self.assertEqual(manifest["missingness"]["invalid_optional_feature_missingness"], 0)

    def test_accepts_both_complete_optional_missing_groups(self):
        """Input: absent SYM-H and weather groups with both controlled flags
        Output: audit accepts the complete combined missingness state"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    """
                    UPDATE swarm_a_analysis_10min
                    SET sym_h_nt = NULL,
                        sym_h_left_time_us = NULL,
                        sym_h_right_time_us = NULL,
                        ap_now = NULL,
                        ap_source_time_us = NULL,
                        f107_sfu = NULL,
                        f107_source_time_us = NULL,
                        f107a_sfu = NULL,
                        f107a_source_time_us = NULL,
                        f107_data_type = NULL,
                        quality_flags = 'missing_sym_h|missing_space_weather'
                    """
                )
                connection.commit()
            finally:
                connection.close()

            manifest = write_release_metadata(database_path)

        self.assertEqual(manifest["missingness"]["invalid_optional_feature_missingness"], 0)

    def test_rejects_decay_row_without_12_hour_predecessor(self):
        """Input: decay row without its same-chunk 12-hour orbit row
        Output: audit rejects an unverifiable backward difference"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "release.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                add_release_fixture(connection)
                connection.execute(
                    "DELETE FROM swarm_a_orbit_10min WHERE time_us = ?",
                    (PAST_TIME_US,),
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "invalid_decay_contract_rows"):
                write_release_metadata(database_path)

    def test_rejects_wrong_derivative_for_each_backward_window(self):
        """Input: each stored window derivative inconsistent with orbit values
        Output: audit rejects every incorrect rate calculation"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            for column in (
                "da_dt_3h_backward_m_s",
                "da_dt_6h_backward_m_s",
                "da_dt_12h_backward_m_s",
            ):
                database_path = Path(temporary_folder) / f"{column}.sqlite"
                connection = sqlite3.connect(database_path)
                try:
                    create_tables(connection)
                    add_release_fixture(connection)
                    connection.execute(
                        f"UPDATE swarm_a_orbit_decay_10min SET {column} = 0.0"
                    )
                    connection.commit()
                finally:
                    connection.close()

                with self.assertRaisesRegex(ValueError, "invalid_decay_contract_rows"):
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
                    "INSERT INTO swarm_a_orbit_decay_10min VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        later_time_us, 6_850_000.0,
                        -0.001, 86.4, -0.001, 86.4, -0.001, 86.4,
                        1, "p1.5",
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO swarm_a_analysis_10min VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        later_time_us, 6_850_000.0,
                        -0.001, 86.4, -0.001, 86.4, -0.001, 86.4,
                        60, 10.0, 1, -20.0, TIME_US, TIME_US, 8.0, TIME_US,
                        120.0, TIME_US, 117.0, TIME_US, "OBSERVED", "ok", "p1.6",
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "non_continuous_chunk_rows"):
                write_release_metadata(database_path)


if __name__ == "__main__":
    unittest.main()
