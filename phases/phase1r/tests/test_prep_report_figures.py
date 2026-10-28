"""Check the twelve-year report's analysis-period boundary."""

import sqlite3
import unittest

from phases.phase1r.code.prep_report_figures import (
    REPORT_START_TIME_US,
    read_daily_mean_rows,
    read_yearly_coverage,
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

    def test_yearly_coverage_excludes_cross_boundary_window(self):
        """Input: rows around 2014-07-01. Output: in-scope source and fit counts."""
        with sqlite3.connect(":memory:") as connection:
            connection.execute("""
                CREATE TABLE swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 (
                    time_us INTEGER PRIMARY KEY,
                    orbit_3_decay_rate_m_s REAL, orbit_3_window_start_time_us INTEGER,
                    orbit_5_decay_rate_m_s REAL, orbit_5_window_start_time_us INTEGER
                )
            """)
            connection.executemany(
                "INSERT INTO swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 VALUES (?, ?, ?, ?, ?)",
                [
                    (REPORT_START_TIME_US - 10_000_000, 1.0, REPORT_START_TIME_US - 20_000_000,
                     1.0, REPORT_START_TIME_US - 20_000_000),
                    (REPORT_START_TIME_US + 10_000_000, 1.0, REPORT_START_TIME_US - 10_000_000,
                     1.0, REPORT_START_TIME_US - 10_000_000),
                    (REPORT_START_TIME_US + 20_000_000, 1.0, REPORT_START_TIME_US,
                     1.0, REPORT_START_TIME_US),
                ],
            )
            coverage = read_yearly_coverage(connection)
        self.assertEqual(coverage[0][2:], (2, 1, 1))


if __name__ == "__main__":
    unittest.main()
