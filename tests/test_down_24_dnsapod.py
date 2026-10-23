"""Check DNSAPOD day selection for the current storm schema."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from satellite_orbit.data.density.down_24_dnsapod import required_days


class CurrentDnsapodDaysTest(unittest.TestCase):
    """Input: P2.3 storm windows. Output: exact intersected UTC days."""

    def test_partial_boundary_days_are_included(self):
        """Input: window from noon to next noon. Output: both UTC days."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "p23.sqlite"
            with closing(sqlite3.connect(path)) as database:
                database.execute("CREATE TABLE storm_event_v2 "
                                 "(window_start_time_us INTEGER, window_end_time_us INTEGER)")
                start = int(datetime(2024, 5, 10, 12, tzinfo=timezone.utc).timestamp()
                            * 1_000_000)
                database.execute("INSERT INTO storm_event_v2 VALUES (?, ?)",
                                 (start, start + 86_400_000_000))
                database.commit()
            days = required_days(path)
        self.assertEqual(days, {"20240510", "20240511"})

    def test_right_open_midnight_excludes_next_day(self):
        """Input: window ending at midnight. Output: only preceding day."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "p23.sqlite"
            with closing(sqlite3.connect(path)) as database:
                database.execute("CREATE TABLE storm_event_v2 "
                                 "(window_start_time_us INTEGER, window_end_time_us INTEGER)")
                start = int(datetime(2024, 5, 10, tzinfo=timezone.utc).timestamp()
                            * 1_000_000)
                database.execute("INSERT INTO storm_event_v2 VALUES (?, ?)",
                                 (start, start + 86_400_000_000))
                database.commit()
            days = required_days(path)
        self.assertEqual(days, {"20240510"})


if __name__ == "__main__":
    unittest.main()
