"""Check SQLite storage for Brouwer-Lyddane mean-orbit results."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from satellite_orbit.data.pod import prep_derived_mean_orbit
from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_derived_mean_orbit import write_mean_orbits
from satellite_orbit.data.pod.prep_derived_pod_quality import create_quality_table


OREKIT_AVAILABLE = (Path(__file__).resolve().parents[1] / ".orekitvenv").is_dir()
POD_TIME_US = 1_715_350_802_000_000


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
                prep_derived_mean_orbit.create_mean_orbit_table(connection)
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
                prep_derived_mean_orbit,
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
                prep_derived_mean_orbit.create_mean_orbit_table(connection)
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
                prep_derived_mean_orbit,
                "mean_orbit_metadata",
                return_value=metadata,
            ), patch.object(
                prep_derived_mean_orbit,
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
        self.assertEqual(algorithm, "orekit_brouwer_lyddane_j2_to_j5_m2_0_v1")

    def test_replaces_partial_source_output_when_resuming(self):
        """Input: one stale mean row from a two-state source
        Output: full source output replaces the partial checkpoint"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "partial_mean_orbit.sqlite"
            with sqlite3.connect(database_path) as connection:
                create_tables(connection)
                create_quality_table(connection)
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
