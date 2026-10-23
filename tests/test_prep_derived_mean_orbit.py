"""Check SQLite storage for Brouwer-Lyddane mean-orbit results."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from satellite_orbit.data.pod import prep_04_mean_orbit
from satellite_orbit.data.pod import prep_mean_orbit_cache
from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_04_mean_orbit import (
    ALGORITHM_NAME,
    MEAN_ORBIT_ELEMENT_FIELDS,
    MEAN_ORBIT_ELEMENTS_TABLE,
    write_mean_orbit_elements,
    write_mean_orbits,
)
from satellite_orbit.data.pod.prep_05_pod_quality import create_quality_table


OREKIT_AVAILABLE = (Path(__file__).resolve().parents[1] / ".orekitvenv").is_dir()
POD_TIME_US = 1_715_350_802_000_000


def create_orbital_elements_table(connection):
    """Input: SQLite connection
    Output: P1.3 orbital-element table exists"""
    connection.execute(
        """
        CREATE TABLE swarm_a_orbital_elements (
            time_us INTEGER PRIMARY KEY,
            semi_major_axis_m REAL,
            rejection_reason TEXT
        )
        """
    )


def insert_valid_orbital_elements(connection, states):
    """Input: SQLite connection and POD states
    Output: matching valid P1.3 rows"""
    connection.executemany(
        "INSERT INTO swarm_a_orbital_elements VALUES (?, ?, ?)",
        [(state[0], 6_800_000.0, None) for state in states],
    )


class MeanOrbitResumeMetadataTest(unittest.TestCase):
    """Input: existing mean-orbit output with changed metadata
    Output: resume requires an explicit rebuild"""

    def test_rejects_resume_when_algorithm_metadata_changed(self):
        """Input: existing row and a changed mean-orbit algorithm
        Output: writer fails before calculating more rows"""
        metadata = [("mean_orbit_algorithm", "mean-v2")]
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "mean_orbit.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                create_quality_table(connection)
                create_orbital_elements_table(connection)
                prep_04_mean_orbit.create_mean_orbit_table(connection)
                connection.execute(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (POD_TIME_US, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, POD_TIME_US, 1),
                )
                connection.execute(
                    "INSERT INTO swarm_a_mean_orbital_elements VALUES (?, ?, ?)",
                    (POD_TIME_US, 6_800_000.0, None),
                )
                connection.execute(
                    "INSERT INTO metadata VALUES (?, ?)",
                    ("mean_orbit_algorithm", "mean-v1"),
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(
                prep_04_mean_orbit,
                "mean_orbit_metadata",
                return_value=metadata,
            ):
                with self.assertRaisesRegex(ValueError, "Use rebuild=True"):
                    write_mean_orbits(database_path)

    def test_allows_rebuild_when_algorithm_metadata_changed(self):
        """Input: existing mean-orbit row and changed algorithm metadata
        Output: explicit rebuild replaces the old metadata"""
        metadata = [("mean_orbit_algorithm", "mean-v2")]
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "mean_orbit.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                create_quality_table(connection)
                create_orbital_elements_table(connection)
                prep_04_mean_orbit.create_mean_orbit_table(connection)
                connection.execute(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (POD_TIME_US, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, POD_TIME_US, 1),
                )
                connection.execute(
                    "INSERT INTO swarm_a_mean_orbital_elements VALUES (?, ?, ?)",
                    (POD_TIME_US, 6_800_000.0, None),
                )
                connection.execute(
                    "INSERT INTO metadata VALUES (?, ?)",
                    ("mean_orbit_algorithm", "mean-v1"),
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(
                prep_04_mean_orbit,
                "mean_orbit_metadata",
                return_value=metadata,
            ), patch.object(
                prep_04_mean_orbit,
                "write_source",
                return_value=(0, 0),
            ):
                write_mean_orbits(database_path, rebuild=True)

            connection = sqlite3.connect(database_path)
            try:
                stored_metadata = connection.execute(
                    "SELECT value FROM metadata WHERE name = 'mean_orbit_algorithm'"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(stored_metadata, "mean-v2")


class MeanOrbitSourceStateTest(unittest.TestCase):
    """Input: valid and invalid P1.3 rows with no P1.4 table
    Output: mean-orbit input follows P1.3 validity only"""

    def test_reads_valid_p1_3_state_before_quality_exists(self):
        """Input: one valid P1.3 state
        Output: state is eligible before P1.4 writes quality"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "mean_orbit.sqlite"
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                create_orbital_elements_table(connection)
                connection.execute(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (POD_TIME_US, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, POD_TIME_US, 1),
                )
                insert_valid_orbital_elements(connection, [(POD_TIME_US,)])
                rows = prep_04_mean_orbit.mean_orbit_source_states(connection, 1)
            finally:
                connection.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], POD_TIME_US)


class FullMeanOrbitStorageTest(unittest.TestCase):
    """Input: valid P1.3 states inside and outside the full-element window
    Output: only 2022--2026 elements enter the independent versioned table"""

    def test_writes_full_elements_without_changing_existing_tables(self):
        """Input: one 2024 state, one 2021 state, and existing old output
        Output: finite full elements for only the 2024 P1.3 state"""
        earlier_time_us = 1_609_459_200_000_000
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "full_mean_orbit.sqlite"
            states = [
                (earlier_time_us, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, earlier_time_us, 1),
                (POD_TIME_US, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, POD_TIME_US, 1),
            ]
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                create_orbital_elements_table(connection)
                prep_04_mean_orbit.create_mean_orbit_table(connection)
                connection.executemany(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    states,
                )
                insert_valid_orbital_elements(connection, states)
                connection.executemany(
                    "INSERT INTO swarm_a_mean_orbital_elements VALUES (?, ?, ?)",
                    [(time_us, 6_800_000.0, None) for time_us, *_ in states],
                )
                before_raw = connection.execute(
                    "SELECT * FROM swarm_a_states ORDER BY time_us"
                ).fetchall()
                before_p1_3 = connection.execute(
                    "SELECT * FROM swarm_a_orbital_elements ORDER BY time_us"
                ).fetchall()
                before_old_mean = connection.execute(
                    "SELECT * FROM swarm_a_mean_orbital_elements ORDER BY time_us"
                ).fetchall()
                connection.commit()
            finally:
                connection.close()

            def fake_element_rows(source_rows):
                return [
                    (time_us, 6_800_000.0, *([1.0] * (len(MEAN_ORBIT_ELEMENT_FIELDS) - 1)), None)
                    for time_us, _ in source_rows
                ]

            with patch.object(
                prep_04_mean_orbit,
                "mean_orbit_element_rows",
                side_effect=fake_element_rows,
            ):
                result = write_mean_orbit_elements(database_path)
                resumed_result = write_mean_orbit_elements(database_path)

            connection = sqlite3.connect(database_path)
            try:
                rows = connection.execute(
                    f"SELECT * FROM {MEAN_ORBIT_ELEMENTS_TABLE} ORDER BY time_us"
                ).fetchall()
                metadata = dict(connection.execute("SELECT name, value FROM metadata"))
                after_raw = connection.execute(
                    "SELECT * FROM swarm_a_states ORDER BY time_us"
                ).fetchall()
                after_p1_3 = connection.execute(
                    "SELECT * FROM swarm_a_orbital_elements ORDER BY time_us"
                ).fetchall()
                after_old_mean = connection.execute(
                    "SELECT * FROM swarm_a_mean_orbital_elements ORDER BY time_us"
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(result["stored_rows"], 1)
        self.assertEqual(resumed_result["new_source_files"], 0)
        self.assertEqual([row[0] for row in rows], [POD_TIME_US])
        element_row = rows[0]
        self.assertEqual(element_row[1], 6_800_000.0)
        self.assertTrue(all(value is not None for value in element_row[1:-1]))
        self.assertIsNone(element_row[-1])
        self.assertEqual(metadata["mean_orbit_elements_table"], MEAN_ORBIT_ELEMENTS_TABLE)
        self.assertEqual(metadata["mean_orbit_elements_fields"], ",".join(MEAN_ORBIT_ELEMENT_FIELDS))
        self.assertEqual(before_raw, after_raw)
        self.assertEqual(before_p1_3, after_p1_3)
        self.assertEqual(before_old_mean, after_old_mean)


class MeanOrbitCacheReuseTest(unittest.TestCase):
    """Input: matching fresh state and frozen mean-orbit cache
    Output: only verified usable cache rows are reused"""

    def test_reuses_matching_cache_for_current_usable_rows(self):
        """Input: equal source/state rows and one usable quality row
        Output: copied mean row and explicit cache provenance"""
        metadata = [
            ("mean_orbit_algorithm", "legacy-v1"),
            ("mean_orbit_input_frame", "GCRF"),
            ("mean_orbit_input_transform", "astropy_itrf_to_gcrf"),
            ("mean_orbit_gravity_field_degree_order", "5,0"),
            ("mean_orbit_m2", "0.0"),
            ("orekit_jpype_version", "test-orekit"),
            ("astropy_version", "test-astropy"),
            ("mean_orbit_implementation_fingerprint", "legacy-fingerprint"),
        ]
        state = (POD_TIME_US, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, POD_TIME_US, 1)
        with tempfile.TemporaryDirectory() as temporary_folder:
            cache_path = Path(temporary_folder) / "cache.sqlite"
            target_path = Path(temporary_folder) / "target.sqlite"
            for database_path, include_quality in (
                (cache_path, False),
                (target_path, True),
            ):
                connection = sqlite3.connect(database_path)
                try:
                    create_tables(connection)
                    create_orbital_elements_table(connection)
                    prep_04_mean_orbit.create_mean_orbit_table(connection)
                    connection.execute(
                        "INSERT INTO source_files (source_id, file_name, signature) VALUES (?, ?, ?)",
                        (1, "pod.zip", "same-source"),
                    )
                    connection.execute(
                        "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        state,
                    )
                    insert_valid_orbital_elements(connection, [state])
                    if include_quality:
                        create_quality_table(connection)
                        connection.execute(
                            "INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
                            (POD_TIME_US, 1, None, 1),
                        )
                    else:
                        connection.execute(
                            "INSERT INTO swarm_a_mean_orbital_elements VALUES (?, ?, ?)",
                            (POD_TIME_US, 6_800_000.0, None),
                        )
                        connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata)
                    connection.commit()
                finally:
                    connection.close()

            with patch.object(
                prep_mean_orbit_cache,
                "mean_orbit_metadata",
                return_value=metadata,
            ):
                result = prep_mean_orbit_cache.copy_verified_mean_orbit_cache(
                    target_path,
                    cache_path,
                )

            connection = sqlite3.connect(target_path)
            try:
                row = connection.execute(
                    "SELECT mean_semi_major_axis_m FROM swarm_a_mean_orbital_elements"
                ).fetchone()
                validation = connection.execute(
                    "SELECT value FROM metadata WHERE name = 'mean_orbit_cache_validation'"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(result["stored_rows"], 1)
        self.assertEqual(row[0], 6_800_000.0)
        self.assertEqual(validation, "exact_source_and_state_match")


@unittest.skipUnless(OREKIT_AVAILABLE, "requires .orekitvenv")
class MeanOrbitStorageTest(unittest.TestCase):
    """Input: small usable ITRF POD source
    Output: matching mean-orbit derived rows"""

    def test_writes_one_mean_orbit_row_for_each_usable_state(self):
        """Input: two usable ITRF states
        Output: two finite mean-orbit rows and metadata"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "mean_orbit.sqlite"
            with sqlite3.connect(database_path) as connection:
                create_tables(connection)
                create_quality_table(connection)
                create_orbital_elements_table(connection)
                connection.executemany(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            POD_TIME_US,
                            -1_755_312.7442,
                            -6_216_748.3248,
                            2_106_725.0718,
                            -739.75979859,
                            -2_268.53029107,
                            -7_271.54469795,
                            POD_TIME_US,
                            1,
                        ),
                        (
                            POD_TIME_US + 10_000_000,
                            -1_762_679.9878,
                            -6_239_113.5081,
                            2_033_927.2386,
                            -733.68238125,
                            -2_204.37304155,
                            -7_279.90140021,
                            POD_TIME_US,
                            1,
                        ),
                    ],
                )
                connection.executemany(
                    "INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
                    [
                        (POD_TIME_US, 1, None, 1),
                        (POD_TIME_US + 10_000_000, 1, None, 1),
                    ],
                )
                insert_valid_orbital_elements(
                    connection,
                    [(POD_TIME_US,), (POD_TIME_US + 10_000_000,)],
                )
            connection.close()

            result = write_mean_orbits(database_path)
            resumed_result = write_mean_orbits(database_path)

            with sqlite3.connect(database_path) as connection:
                rows = connection.execute(
                    "SELECT time_us, mean_semi_major_axis_m, rejection_reason "
                    "FROM swarm_a_mean_orbital_elements ORDER BY time_us"
                ).fetchall()
                algorithm = connection.execute(
                    "SELECT value FROM metadata WHERE name = 'mean_orbit_algorithm'"
                ).fetchone()[0]
            connection.close()

        self.assertEqual(result["stored_rows"], 2)
        self.assertEqual(result["rejected_rows"], 0)
        self.assertEqual(resumed_result["new_source_files"], 0)
        self.assertEqual(resumed_result["stored_rows"], 0)
        self.assertEqual([row[0] for row in rows], [POD_TIME_US, POD_TIME_US + 10_000_000])
        self.assertTrue(all(row[1] > 0.0 and row[2] is None for row in rows))
        self.assertEqual(algorithm, ALGORITHM_NAME)

    def test_writes_parallel_sources_through_one_sqlite_writer(self):
        """Input: two valid sources and two calculation threads
        Output: both source results are stored without concurrent SQLite writes"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "parallel_mean_orbit.sqlite"
            states = [
                (
                    POD_TIME_US,
                    7e6,
                    0.0,
                    0.0,
                    0.0,
                    7500.0,
                    0.0,
                    POD_TIME_US,
                    1,
                ),
                (
                    POD_TIME_US + 10_000_000,
                    7e6,
                    0.0,
                    0.0,
                    0.0,
                    7500.0,
                    0.0,
                    POD_TIME_US + 10_000_000,
                    2,
                ),
            ]
            connection = sqlite3.connect(database_path)
            try:
                create_tables(connection)
                create_orbital_elements_table(connection)
                connection.executemany(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    states,
                )
                insert_valid_orbital_elements(connection, states)
                connection.commit()
            finally:
                connection.close()

            def fake_mean_orbit_rows(source_rows):
                return [(time_us, 6_800_000.0, None) for time_us, _ in source_rows]

            with patch.object(
                prep_04_mean_orbit,
                "initialize_mean_orbit_context",
            ), patch.object(
                prep_04_mean_orbit,
                "mean_orbit_rows",
                side_effect=fake_mean_orbit_rows,
            ):
                result = write_mean_orbits(database_path, workers=2)

            connection = sqlite3.connect(database_path)
            try:
                stored_rows = connection.execute(
                    "SELECT count(*) FROM swarm_a_mean_orbital_elements"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(result["new_source_files"], 2)
        self.assertEqual(result["stored_rows"], 2)
        self.assertEqual(stored_rows, 2)

    def test_replaces_partial_source_output_when_resuming(self):
        """Input: one stale mean row from a two-state source
        Output: full source output replaces the partial checkpoint"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "partial_mean_orbit.sqlite"
            with sqlite3.connect(database_path) as connection:
                create_tables(connection)
                create_quality_table(connection)
                create_orbital_elements_table(connection)
                states = [
                    (
                        POD_TIME_US + offset_us,
                        -1_755_312.7442,
                        -6_216_748.3248,
                        2_106_725.0718,
                        -739.75979859,
                        -2_268.53029107,
                        -7_271.54469795,
                        POD_TIME_US,
                        1,
                    )
                    for offset_us in (0, 10_000_000)
                ]
                connection.executemany(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    states,
                )
                connection.executemany(
                    "INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
                    [(state[0], 1, None, 1) for state in states],
                )
                insert_valid_orbital_elements(connection, states)
            connection.close()
            write_mean_orbits(database_path, source_limit=1)
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "DELETE FROM swarm_a_mean_orbital_elements WHERE time_us = ?",
                    (POD_TIME_US + 10_000_000,),
                )
            connection.close()

            result = write_mean_orbits(database_path, source_limit=1)
            with sqlite3.connect(database_path) as connection:
                stored_rows = connection.execute(
                    "SELECT count(*) FROM swarm_a_mean_orbital_elements"
                ).fetchone()[0]
            connection.close()

        self.assertEqual(result["stored_rows"], 2)
        self.assertEqual(stored_rows, 2)


if __name__ == "__main__":
    unittest.main()
