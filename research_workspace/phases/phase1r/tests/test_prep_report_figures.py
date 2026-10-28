"""Check the twelve-year report's analysis-period boundary."""

import sqlite3
import unittest

from research_workspace.phases.phase1r.code.prep_report_figures import (
    REPORT_START_TIME_US,
    read_daily_mean_rows,
)


class TwelveYearReportFigureTest(unittest.TestCase):
    """Input: synthetic mean elements. Output: report rows after the cutoff."""

    def test_daily_mean_excludes_2014_first_half(self):
        """Input: one row before and two at/after cutoff. Output: July mean only."""
        with sqlite3.connect(":memory:") as connection:
            connection.execute(
                "CREATE TABLE swarm_a_mean_orbit_elements_v1 "
                "(time_us INTEGER, mean_semi_major_axis_m REAL, rejection_reason TEXT)"
            )
            connection.executemany(
                "INSERT INTO swarm_a_mean_orbit_elements_v1 VALUES (?, ?, NULL)",
                [
                    (REPORT_START_TIME_US - 10_000_000, 100.0),
                    (REPORT_START_TIME_US, 200.0),
                    (REPORT_START_TIME_US + 10_000_000, 300.0),
                ],
            )
            result = read_daily_mean_rows(connection)
        self.assertEqual(result, [(REPORT_START_TIME_US, 250.0)])


if __name__ == "__main__":
    unittest.main()
