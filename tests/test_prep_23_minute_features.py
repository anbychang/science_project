"""Check one-minute Phase 2 phase and decay alignment."""

import math
import sqlite3
import unittest
from unittest.mock import patch

from satellite_orbit.phase2.prep_23_minute_features import (
    EventSources,
    event_rows,
    orbit_at_time,
    phase_at_time,
)


def sample(time_us: int, phase_u_rad: float, chunk_id: int = 7) -> dict:
    """Input: UTC epoch, phase angle, chunk. Output: synthetic Phase 1 row."""
    row = {
        "time_us": time_us,
        "is_usable": 1,
        "chunk_id": chunk_id,
        "mean_semi_major_axis_m": 6_800_000.0 + time_us / 10_000_000,
        "mean_argument_of_perigee_rad": phase_u_rad,
        "mean_anomaly_rad": 0.0,
    }
    for field in ("raw_3", "raw_5", "joint_3", "joint_5"):
        for suffix in ("rate", "sigma", "count", "reject"):
            row[f"{field}_{suffix}"] = None
    return row


class MinuteFeatureTest(unittest.TestCase):
    """Input: synthetic Phase 1 samples. Output: checked minute feature alignment."""

    def test_phase_interpolates_across_zero_without_long_way_around(self):
        """Input: phases around 2pi/0. Output: midpoint phase close to zero."""
        rows = [sample(0, math.tau - 0.01), sample(10_000_000, 0.01)]
        result = phase_at_time(rows, [0, 10_000_000], 5_000_000)
        self.assertAlmostEqual(result["u_rad"], 0.0, places=10)

    def test_phase_uses_left_sample_only_for_decay(self):
        """Input: distinct past and future rates. Output: past four-method record."""
        rows = [sample(0, 0.0), sample(10_000_000, 0.1)]
        rows[0]["raw_3_rate"] = -0.5
        rows[1]["raw_3_rate"] = -9.0
        result = phase_at_time(rows, [0, 10_000_000], 5_000_000)
        self.assertEqual((result["left_us"], result["decay"][0]), (0, -0.5))

    def test_phase_rejects_cross_chunk_interpolation(self):
        """Input: two chunks around target. Output: no interpolated phase."""
        rows = [sample(0, 0.0), sample(10_000_000, 0.1, chunk_id=8)]
        self.assertEqual(
            phase_at_time(rows, [0, 10_000_000], 5_000_000)["status"],
            "gap_or_chunk",
        )

    def test_phase_rejects_gap_longer_than_twenty_seconds(self):
        """Input: 30-s source gap. Output: no phase interpolation."""
        rows = [sample(0, 0.0), sample(30_000_000, 0.3)]
        self.assertEqual(
            phase_at_time(rows, [0, 30_000_000], 15_000_000)["status"],
            "gap_or_chunk",
        )

    def test_empty_phase_source_stays_missing(self):
        """Input: no Phase 1 records. Output: explicit no-source status."""
        self.assertEqual(phase_at_time([], [], 30_000_000)["status"], "no_source")

    def test_orbit_link_excludes_end_boundary(self):
        """Input: complete orbit and its end. Output: no orbit at end boundary."""
        orbits = [(0, 5_000_000, 4_000_000, 6_800_000.0, 7)]
        self.assertEqual(orbit_at_time(orbits, [0], 5_000_000),
                         (None, None, None, None, None))

    def test_source_label_is_center_and_orbit_target(self):
        """Input: one source minute at 05:38. Output: centered support and exact target."""
        source_time_us = 1691041080000000
        with sqlite3.connect(":memory:") as storms:
            storms.execute(
                "CREATE TABLE geomag_1min_v2 (time_us INTEGER, sme_nt REAL, "
                "symh_nt REAL, sme_station_count INTEGER, "
                "sme_not_before_time_us INTEGER, kyoto_not_before_time_us INTEGER)"
            )
            storms.execute(
                "INSERT INTO geomag_1min_v2 VALUES (?, 153.613083, -2, 100, ?, ?)",
                (source_time_us, source_time_us + 60_000_000,
                 source_time_us + 30_000_000),
            )
            rows = [sample(source_time_us, 0.1)]
            orbit = (source_time_us - 1, source_time_us + 60_000_000,
                     source_time_us + 30_000_000, 6_800_000.0, 7)
            with patch("satellite_orbit.phase2.prep_23_minute_features.source_rows",
                       return_value=rows), patch(
                "satellite_orbit.phase2.prep_23_minute_features.complete_orbits",
                return_value=[orbit],
            ), patch("satellite_orbit.phase2.prep_23_minute_features.sample_drivers",
                     return_value=None):
                feature = next(event_rows(
                    ("S", source_time_us, source_time_us, source_time_us + 60_000_000),
                    EventSources(storms, storms, {}),
                ))
        self.assertEqual(feature[:5], (
            "S", source_time_us, source_time_us - 30_000_000,
            source_time_us + 30_000_000, source_time_us,
        ))


if __name__ == "__main__":
    unittest.main()
