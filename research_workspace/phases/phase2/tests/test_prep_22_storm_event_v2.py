"""Check the new 72-hour and overlapping-window storm merge contract."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from research_workspace.phases.phase0.code.data.geomagnetic.down_supermag_sme import sha256_file
from research_workspace.phases.phase2.code.prep_21_geomag_1min import ALGORITHM_VERSION as INPUT_VERSION, create_tables
from research_workspace.phases.phase2.code.prep_22_storm_event import (
    HOUR_US,
    MINUTE_US,
    find_local_minima,
    merge_minima,
    write_storm_events,
)


def minimum(hour: int, value: int) -> dict:
    """Input: relative hour and SYM-H. Output: synthetic raw minimum."""
    return {
        "minimum_time_us": hour * HOUR_US,
        "symh_min_nt": value,
        "symh_version": 10,
        "symh_source_file_name": "source.csv",
    }


class StormEventTest(unittest.TestCase):
    """Input: synthetic minute values. Output: candidate and event contracts."""

    def test_equal_plateau_uses_first_minute(self):
        """Input: two-minute minimum plateau. Output: earliest minimum only."""
        values = [-80, -130, -130, -80]
        rows = ((index * MINUTE_US, value, 10, "source.csv") for index, value in enumerate(values))
        minima = find_local_minima(rows)
        self.assertEqual([(row["minimum_time_us"], row["symh_min_nt"]) for row in minima],
                         [(MINUTE_US, -130)])

    def test_missing_neighbor_cannot_create_minimum(self):
        """Input: gap beside deep value. Output: no inferred local minimum."""
        rows = [(0, -80, 10, "source.csv"), (2 * MINUTE_US, -130, 10, "source.csv"),
                (3 * MINUTE_US, -80, 10, "source.csv")]
        self.assertEqual(find_local_minima(rows), [])

    def test_nearby_then_overlapping_windows_form_one_compound_event(self):
        """Input: 70 h, 100 h, and distant gaps. Output: two events."""
        minima, events = merge_minima([
            minimum(0, -110), minimum(70, -130), minimum(170, -160), minimum(400, -120)
        ])
        self.assertEqual([event["n_minima"] for event in events], [3, 1])
        self.assertEqual([row["merge_reason"] for row in minima],
                         ["within_72h", "overlap_window", "representative", "representative"])
        self.assertEqual(events[0]["window_end_time_us"], 266 * HOUR_US)

    def test_touching_half_open_windows_do_not_merge(self):
        """Input: minima exactly 144 h apart. Output: two independent events."""
        _, events = merge_minima([minimum(0, -130), minimum(144, -140)])
        self.assertEqual(len(events), 2)

    def test_copy_preserves_p21_and_adds_new_event_tables(self):
        """Input: frozen small P2.1 SQLite. Output: separate P2.2 event SQLite."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            source = Path(folder) / "p21.sqlite"
            output = Path(folder) / "p22.sqlite"
            start_us = int(datetime(2024, 5, 10, tzinfo=timezone.utc).timestamp()) * 1_000_000
            with closing(sqlite3.connect(source)) as connection:
                connection.execute("PRAGMA foreign_keys = ON")
                create_tables(connection)
                with connection:
                    connection.execute(
                        "INSERT INTO geomag_source_files_v2 VALUES (?, ?, ?, ?, ?, ?)",
                        ("source.csv", "SYM-H", "test-hash", None, None, INPUT_VERSION),
                    )
                    connection.execute("INSERT INTO phase2_metadata VALUES (?, ?)",
                                       ("algorithm_version", INPUT_VERSION))
                    for offset, value in enumerate((-80, -130, -80)):
                        time_us = start_us + offset * MINUTE_US
                        connection.execute(
                            "INSERT INTO geomag_1min_v2 "
                            "(time_us, sme_station_count, sme_valid, symh_nt, symh_version, "
                            "sme_source_file_name, symh_source_file_name, sme_not_before_time_us, "
                            "kyoto_not_before_time_us, algorithm_version) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (time_us, 0, 0, value, 10, "source.csv", "source.csv",
                             time_us + MINUTE_US, time_us + MINUTE_US // 2, INPUT_VERSION),
                        )
            original_hash = sha256_file(source)
            result = write_storm_events(source, output)
            with closing(sqlite3.connect(output)) as connection:
                events = connection.execute("SELECT storm_id, symh_min_nt, n_minima FROM storm_event_v2").fetchall()
            self.assertEqual(sha256_file(source), original_hash)
            self.assertEqual(result["merged_events"], 1)
            self.assertEqual(events[0][1:], (-130, 1))


if __name__ == "__main__":
    unittest.main()
