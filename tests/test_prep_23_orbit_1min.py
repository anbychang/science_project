"""Check the Phase 2 one-minute orbit checkpoint."""

import math
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from satellite_orbit.data.geomagnetic.down_supermag_sme import sha256_file
from satellite_orbit.phase2.prep_23_orbit_1min import (
    MINUTE_US,
    summarize_minute,
    write_orbit_1min,
)


class OrbitMinuteTest(unittest.TestCase):
    """Input: 10-second Phase 1 rows. Output: traceable minute summaries."""

    def test_complete_minute_uses_last_phase_and_mean_axis(self):
        """Input: six valid 10-s rows. Output: mean axis and last-sample phase."""
        rows = [(index * 10_000_000 + 2_000_000, 1, 7, 6_800_000.0 + index,
                 math.pi, math.pi + 0.1) for index in range(6)]
        result = summarize_minute("S", 0, rows)
        self.assertEqual((result[3], result[8], result[9], result[11], result[12]),
                         (6_800_002.5, 6, 6, 7, "complete"))
        self.assertAlmostEqual(result[4], 0.1)
        self.assertEqual(result[5], 52_000_000)

    def test_mixed_chunks_have_no_mean_axis(self):
        """Input: valid rows from two chunks. Output: rejected minute mean."""
        rows = [(2_000_000, 1, 7, 6_800_000.0, 0.0, 0.0),
                (12_000_000, 1, 8, 6_800_001.0, 0.0, 0.1)]
        result = summarize_minute("S", 0, rows)
        self.assertEqual((result[3], result[11], result[12]), (None, None, "mixed_chunk"))

    def test_empty_minute_keeps_missing_as_null(self):
        """Input: no source rows. Output: missing bin, not zero orbital values."""
        result = summarize_minute("S", 0, [])
        self.assertEqual((result[3], result[4], result[8], result[12]),
                         (None, None, 0, "no_usable_source"))

    def test_writer_copies_p22_and_keeps_source_immutable(self):
        """Input: small P2.2 and Phase 1 SQLite. Output: two minute bins."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            root = Path(folder)
            input_db = root / "p22.sqlite"
            phase1_db = root / "phase1.sqlite"
            output_db = root / "p23.sqlite"
            with closing(sqlite3.connect(input_db)) as database:
                database.execute("CREATE TABLE phase2_metadata (name TEXT PRIMARY KEY, value TEXT)")
                database.execute(
                    "CREATE TABLE storm_event_v2 (storm_id TEXT PRIMARY KEY, "
                    "window_start_time_us INTEGER, window_end_time_us INTEGER)"
                )
                database.execute("INSERT INTO phase2_metadata VALUES (?, ?)",
                                 ("p2_2_algorithm_version", "storm_event_symh_v2"))
                database.execute("INSERT INTO storm_event_v2 VALUES (?, ?, ?)",
                                 ("S", 0, 2 * MINUTE_US))
                database.commit()
            with closing(sqlite3.connect(phase1_db)) as database:
                database.execute("CREATE TABLE swarm_a_states (time_us INTEGER PRIMARY KEY)")
                database.execute(
                    "CREATE TABLE swarm_a_pod_quality "
                    "(time_us INTEGER PRIMARY KEY, is_usable INTEGER, chunk_id INTEGER)"
                )
                database.execute(
                    "CREATE TABLE swarm_a_mean_orbit_elements_v1 "
                    "(time_us INTEGER PRIMARY KEY, mean_semi_major_axis_m REAL, "
                    "mean_argument_of_perigee_rad REAL, mean_anomaly_rad REAL)"
                )
                for index in range(6):
                    time_us = index * 10_000_000 + 2_000_000
                    database.execute("INSERT INTO swarm_a_states VALUES (?)", (time_us,))
                    database.execute("INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?)",
                                     (time_us, 1, 7))
                    database.execute(
                        "INSERT INTO swarm_a_mean_orbit_elements_v1 VALUES (?, ?, ?, ?)",
                        (time_us, 6_800_000.0 + index, 0.0, 0.1 * index),
                    )
                database.commit()
            input_hash = sha256_file(input_db)
            phase1_hash = sha256_file(phase1_db)
            counts = write_orbit_1min(input_db, phase1_db, output_db)
            with closing(sqlite3.connect(output_db)) as database:
                rows = database.execute(
                    "SELECT bin_end_time_us, orbit_status, mean_semi_major_axis_m "
                    "FROM storm_orbit_1min_v2 ORDER BY bin_end_time_us"
                ).fetchall()
            self.assertEqual(counts["minute_rows"], 2)
            self.assertEqual(rows, [(MINUTE_US, "complete", 6_800_002.5),
                                    (2 * MINUTE_US, "no_usable_source", None)])
            self.assertEqual((sha256_file(input_db), sha256_file(phase1_db)),
                             (input_hash, phase1_hash))


if __name__ == "__main__":
    unittest.main()
