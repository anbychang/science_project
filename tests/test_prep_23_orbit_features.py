"""Check per-orbit Phase 2 boundaries and minute quality rules."""

import math
import sqlite3
import unittest

from satellite_orbit.phase2.prep_23_orbit_features import (
    MINUTE_US,
    crossing_time_us,
    fill_short_gaps,
    orbit_means,
)


class OrbitFeatureTest(unittest.TestCase):
    """Input: synthetic Phase 1 and geomagnetic rows. Output: checked orbit features."""

    def test_crossing_uses_both_ten_second_samples(self):
        """Input: two phases surrounding u=0. Output: interpolated midpoint."""
        with sqlite3.connect(":memory:") as database:
            database.executescript(
                "CREATE TABLE swarm_a_mean_orbit_elements_v1 "
                "(time_us INTEGER, mean_argument_of_perigee_rad REAL, mean_anomaly_rad REAL);"
                "CREATE TABLE swarm_a_pod_quality (time_us INTEGER, chunk_id INTEGER);"
            )
            database.executemany(
                "INSERT INTO swarm_a_mean_orbit_elements_v1 VALUES (?,?,?)",
                [(0, 2 * math.pi - 0.01, 0.0), (10_000_000, 0.01, 0.0)],
            )
            database.executemany(
                "INSERT INTO swarm_a_pod_quality VALUES (?,?)",
                [(0, 7), (10_000_000, 7)],
            )
            self.assertEqual(crossing_time_us(database, 10_000_000, 7), 5_000_000)

    def test_short_gap_interpolates_but_long_gap_stays_missing(self):
        """Input: 10- and 11-minute gaps. Output: only short gap filled."""
        short = [[index * MINUTE_US, 0.0 if index == 0 else 11.0 if index == 11 else None]
                 for index in range(12)]
        long = [[index * MINUTE_US, 0.0 if index == 0 else 12.0 if index == 12 else None]
                for index in range(13)]
        fill_short_gaps(short, 1)
        fill_short_gaps(long, 1)
        self.assertEqual(short[5][1], 5.0)
        self.assertIsNone(long[5][1])

    def test_orbit_validity_requires_eighty_percent_of_each_index(self):
        """Input: five minute values with one SME gap. Output: valid orbit."""
        minutes = [[index * MINUTE_US, None if index == 1 else 20.0, -50.0, 100]
                   for index in range(5)]
        result = orbit_means(minutes, 0, 5)
        self.assertEqual(result[3:7], (5, 4, 5, 1))


if __name__ == "__main__":
    unittest.main()
