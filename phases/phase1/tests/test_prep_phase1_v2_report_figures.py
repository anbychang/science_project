"""Check the report's hour bins against small v2-shaped tables."""

import sqlite3
import unittest

from phases.phase1.code.prep_phase1_v2_report_figures import hourly_candidates


class HourlyCandidateTest(unittest.TestCase):
    """Input: in-memory v2-shaped SQLite rows. Output: checked hourly medians."""

    def test_rate_units_and_hourly_median(self):
        """Input: two ten-second source rows. Output: one SI-to-m/day hour bin."""
        connection = sqlite3.connect(":memory:")
        connection.executescript("""
            CREATE TABLE swarm_a_phase_harmonic_decay_raw_b_l_sets_v2
                (time_us INTEGER PRIMARY KEY, orbit_3_decay_rate_m_s REAL,
                 orbit_5_decay_rate_m_s REAL);
            CREATE TABLE swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2
                (time_us INTEGER PRIMARY KEY, orbit_3_decay_rate_m_s REAL,
                 orbit_5_decay_rate_m_s REAL);
            CREATE TABLE swarm_a_phase_harmonic_features_v2
                (time_us INTEGER PRIMARY KEY, sym_h_nt REAL, ap_now REAL);
        """)
        connection.executemany(
            "INSERT INTO swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 VALUES (?, ?, ?)",
            [(0, 1 / 86400, 3 / 86400), (10_000_000, 3 / 86400, 5 / 86400)],
        )
        connection.executemany(
            "INSERT INTO swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2 VALUES (?, ?, ?)",
            [(0, 2 / 86400, 4 / 86400), (10_000_000, 4 / 86400, 6 / 86400)],
        )
        connection.executemany(
            "INSERT INTO swarm_a_phase_harmonic_features_v2 VALUES (?, ?, ?)",
            [(0, -10, 3), (10_000_000, -30, 5)],
        )
        rows = hourly_candidates(connection, 0, 3_600_000_000)
        connection.close()
        self.assertEqual(rows[0][1:], (2, 4, 3, 5, -20, 4))


if __name__ == "__main__":
    unittest.main()
