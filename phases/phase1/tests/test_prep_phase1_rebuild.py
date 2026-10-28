"""Check the safe public seam for a fresh Phase 1 rebuild."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phases.phase1.code.prep_phase1_rebuild import (
    default_stages,
    write_mean_orbit_stage,
    write_phase1_raw_database,
    write_phase1_rebuild,
)


class Phase1RebuildTest(unittest.TestCase):
    """Input: clean target path and injectable Phase 1 stages
    Output: ordered rebuild without touching an existing database"""

    def test_phase_one_raw_stage_skips_density(self):
        """Input: new Phase 1 SQLite path.
        Output: raw stage does not import Phase 2 density."""
        database_path = Path("new-phase1.sqlite")

        with patch(
            "phases.phase1.code.prep_phase1_rebuild.write_sqlite_database"
        ) as raw_writer:
            write_phase1_raw_database(database_path)

        raw_writer.assert_called_once_with(database_path)

    def test_default_stages_follow_the_numbered_pod_pipeline(self):
        """Input: clean rebuild evidence
        Output: default stages use the documented linear order"""
        stage_names = [
            name
            for name, _ in default_stages(
                {"entry_point": "test"},
                mean_orbit_cache_database=Path("p1_5.sqlite"),
            )
        ]

        self.assertEqual(
            stage_names,
            [
                "01_raw",
                "02_provenance",
                "03_orbital_elements",
                "04_quality",
                "05_mean_orbit",
                "06_orbit_10min",
                "07_signed_rate",
                "08_analysis",
                "09_release_audit",
            ],
        )

    def test_mean_orbit_stage_requires_p1_5_cache(self):
        """Input: mean-orbit stage without a P1.5 cache.
        Output: clear error before Orekit can run again."""
        with self.assertRaisesRegex(ValueError, "requires a P1.5 mean-orbit cache"):
            write_mean_orbit_stage(Path("new-phase1.sqlite"), None)

    def test_default_rebuild_requires_p1_5_cache_before_writing(self):
        """Input: absent target with no P1.5 cache.
        Output: no partial database is created."""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "fresh.sqlite"

            with self.assertRaisesRegex(ValueError, "requires a P1.5 mean-orbit cache"):
                write_phase1_rebuild(database_path)

        self.assertFalse(database_path.exists())

    def test_rejects_an_existing_target_before_any_stage_runs(self):
        """Input: existing target SQLite path
        Output: no stage may replace the working database"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "existing.sqlite"
            database_path.touch()
            calls = []

            with self.assertRaisesRegex(ValueError, "already exists"):
                write_phase1_rebuild(
                    database_path,
                    stages=(("raw", lambda path: calls.append(path)),),
                )

        self.assertEqual(calls, [])

    def test_runs_each_stage_in_phase_order_on_the_new_target(self):
        """Input: new target SQLite path
        Output: every supplied Phase 1 stage receives that target in order"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "fresh.sqlite"
            calls = []

            def record(name):
                return lambda path: calls.append((name, path))

            result = write_phase1_rebuild(
                database_path,
                stages=(
                    ("raw", record("raw")),
                    ("provenance", record("provenance")),
                    ("p1_3", record("p1_3")),
                    ("p1_4", record("p1_4")),
                    ("p1_5", record("p1_5")),
                    ("p1_6", record("p1_6")),
                    ("p1_7", record("p1_7")),
                ),
            )

        self.assertEqual([name for name, _ in calls], [
            "raw", "provenance", "p1_3", "p1_4", "p1_5", "p1_6", "p1_7",
        ])
        self.assertTrue(all(path == database_path for _, path in calls))
        self.assertEqual(result["database_path"], database_path)
