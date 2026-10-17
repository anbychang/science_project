"""Check the safe public seam for a fresh Phase 1 rebuild."""

import tempfile
import unittest
from pathlib import Path

from satellite_orbit.phase1.prep_phase1_rebuild import write_phase1_rebuild


class Phase1RebuildTest(unittest.TestCase):
    """Input: clean target path and injectable Phase 1 stages
    Output: ordered rebuild without touching an existing database"""

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
