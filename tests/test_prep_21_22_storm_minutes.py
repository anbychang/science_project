"""Check P2.1 screening and P2.2 copy-only minute windows."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from satellite_orbit.phase2.prep_20_symh_1min import (
    ALGORITHM_VERSION,
    create_tables,
    sha256_file,
)
from satellite_orbit.phase2.prep_21_22_storm_minutes import (
    HOUR_US,
    MINUTE_US,
    find_local_minima,
    screen_candidates,
    write_phase2_through_p22,
)


def utc_us(time_text: str) -> int:
    """Input: ISO UTC time text. Output: Unix microseconds."""
    return round(
        datetime.fromisoformat(time_text).replace(tzinfo=timezone.utc).timestamp() * 1_000_000
    )


def raw_candidate(hour: int, symh_nt: int) -> dict:
    """Input: relative hour and signed SYM-H. Output: candidate row for screening."""
    return {
        "time_us": hour * HOUR_US,
        "symh_nt": symh_nt,
        "compound": False,
        "status": "selected",
        "note": "",
    }


class StormMinuteTest(unittest.TestCase):
    """Input: small minute tables. Output: checked P2.1/P2.2 behavior."""

    def test_local_minimum_uses_first_minute_of_equal_plateau(self):
        """Input: contiguous equal minimum. Output: one earliest candidate."""
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.execute(
                "CREATE TABLE symh_1min_v1 (source_time_us INTEGER, symh_nt INTEGER)"
            )
            connection.executemany(
                "INSERT INTO symh_1min_v1 VALUES (?, ?)",
                ((minute * MINUTE_US, value) for minute, value in enumerate(
                    [-40, -80, -150, -150, -80, -40]
                )),
            )
            minima = find_local_minima(connection, (0, 5 * MINUTE_US))
        self.assertEqual([(item["time_us"], item["symh_nt"]) for item in minima], [(2 * MINUTE_US, -150)])

    def test_local_minimum_does_not_cross_missing_minute(self):
        """Input: gap next to deep value. Output: no invented minimum."""
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.execute(
                "CREATE TABLE symh_1min_v1 (source_time_us INTEGER, symh_nt INTEGER)"
            )
            connection.executemany(
                "INSERT INTO symh_1min_v1 VALUES (?, ?)",
                [(0, -40), (2 * MINUTE_US, -150), (3 * MINUTE_US, -40)],
            )
            minima = find_local_minima(connection, (0, 3 * MINUTE_US))
        self.assertEqual(minima, [])

    def test_screening_keeps_deeper_compound_and_independent_event(self):
        """Input: sub-24, compound, overlap, independent minima. Output: statuses."""
        candidates = [
            raw_candidate(0, -110),
            raw_candidate(5, -150),
            raw_candidate(30, -180),
            raw_candidate(100, -120),
            raw_candidate(300, -130),
        ]
        selected = screen_candidates(candidates)
        self.assertEqual([item["time_us"] // HOUR_US for item in selected], [30, 300])
        self.assertEqual(
            [item["status"] for item in candidates],
            ["excluded_sub24", "merged_compound", "selected", "excluded_overlap", "selected"],
        )
        self.assertTrue(candidates[2]["compound"])

    def test_copy_preserves_p20_and_stores_selected_minute_window(self):
        """Input: frozen P2.0 and Phase 1 bounds. Output: separate P2.2 SQLite."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_dir:
            root = Path(temporary_dir)
            p20_db = root / "p20.sqlite"
            phase1_db = root / "phase1.sqlite"
            output_db = root / "p22.sqlite"
            storm_us = utc_us("2024-05-10T00:00:00")
            with closing(sqlite3.connect(p20_db)) as connection:
                create_tables(connection)
                with connection:
                    connection.execute(
                        "INSERT INTO symh_source_files_v1 VALUES (?, ?, ?, ?)",
                        ("source.csv", "test-sha", "2024-05-10T00:00:00Z", ALGORITHM_VERSION),
                    )
                    connection.execute(
                        "INSERT INTO phase2_metadata VALUES (?, ?)",
                        ("algorithm_version", ALGORITHM_VERSION),
                    )
                    connection.executemany(
                        "INSERT INTO symh_1min_v1 VALUES (?, ?, ?, ?, ?)",
                        [
                            (storm_us - MINUTE_US, -40, 10, "source.csv", ALGORITHM_VERSION),
                            (storm_us, -150, 10, "source.csv", ALGORITHM_VERSION),
                            (storm_us + MINUTE_US, -40, 10, "source.csv", ALGORITHM_VERSION),
                        ],
                    )
            with closing(sqlite3.connect(phase1_db)) as connection:
                with connection:
                    connection.execute(
                        "CREATE TABLE swarm_a_mean_orbit_elements_v1 (time_us INTEGER PRIMARY KEY)"
                    )
                    connection.executemany(
                        "INSERT INTO swarm_a_mean_orbit_elements_v1 VALUES (?)",
                        [
                            (storm_us - 48 * HOUR_US - MINUTE_US + 2_000_000,),
                            (storm_us + 96 * HOUR_US + MINUTE_US + 32_000_000,),
                        ],
                    )
            frozen_hash = sha256_file(p20_db)
            result = write_phase2_through_p22(p20_db, phase1_db, output_db)
            with closing(sqlite3.connect(output_db)) as connection:
                selected = connection.execute(
                    "SELECT candidate_id, t0_time_us, symh_min_nt "
                    "FROM storm_candidate_v1 WHERE symh_screening_status='selected'"
                ).fetchall()
                window = connection.execute(
                    "SELECT source_time_us, symh_nt, t_rel_h "
                    "FROM storm_symh_1min_v1 ORDER BY source_time_us"
                ).fetchall()
            self.assertEqual(sha256_file(p20_db), frozen_hash)
            self.assertEqual(selected[0][1:], (storm_us, -150))
            self.assertEqual(window, [
                (storm_us - MINUTE_US, -40, -1 / 60),
                (storm_us, -150, 0.0),
                (storm_us + MINUTE_US, -40, 1 / 60),
            ])
            self.assertEqual(result, {"candidate_rows": 1, "selected_events": 1, "window_minute_rows": 3})


if __name__ == "__main__":
    unittest.main()
