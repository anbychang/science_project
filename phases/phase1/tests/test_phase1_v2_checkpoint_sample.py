"""Independently recompute a small set of stored v2 candidate slopes."""

import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


DATABASE = (
    Path(__file__).resolve().parents[3]
    / "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite"
)
SAMPLE_DATES = (
    (2023, 7, 15), (2024, 3, 15), (2024, 9, 15),
    (2025, 3, 15), (2025, 9, 15), (2026, 6, 15),
)


def recompute_slopes(connection, fit, orbit_count):
    """Input: SQLite connection, stored {end, start, raw, joint}, and orbit count.
    Output: {recomputed_start_us, raw_slope_m_s, joint_slope_m_s}."""
    end_us, start_us, _, _ = fit
    rows = list(connection.execute("""
        SELECT time_us, mean_semi_major_axis_m,
               mean_argument_of_perigee_rad + mean_anomaly_rad
        FROM swarm_a_mean_orbit_elements_v1
        WHERE time_us BETWEEN ? AND ? ORDER BY time_us
    """, (start_us - 20_000_000, end_us)))
    time_us = np.array([row[0] for row in rows], dtype=np.int64)
    semi_major_axis_m = np.array([row[1] for row in rows])
    phase_rad = np.unwrap([row[2] for row in rows])
    target_phase_rad = phase_rad[-1] - orbit_count * 2 * np.pi
    boundary_index = int(np.searchsorted(phase_rad, target_phase_rad))
    phase_fraction = (
        (target_phase_rad - phase_rad[boundary_index - 1])
        / (phase_rad[boundary_index] - phase_rad[boundary_index - 1])
    )
    boundary_us = int(round(
        time_us[boundary_index - 1]
        + phase_fraction * (time_us[boundary_index] - time_us[boundary_index - 1])
    ))
    boundary_axis_m = (
        semi_major_axis_m[boundary_index - 1]
        + phase_fraction * (semi_major_axis_m[boundary_index] - semi_major_axis_m[boundary_index - 1])
    )
    first_sample = int(np.searchsorted(time_us, start_us))
    time_us = time_us[first_sample:]
    semi_major_axis_m = semi_major_axis_m[first_sample:]
    phase_rad = phase_rad[first_sample:]
    if time_us[0] != boundary_us:
        time_us = np.r_[boundary_us, time_us]
        semi_major_axis_m = np.r_[boundary_axis_m, semi_major_axis_m]
        phase_rad = np.r_[target_phase_rad, phase_rad]
    elapsed_s = (time_us - time_us[0]) / 1_000_000
    centered_axis_m = semi_major_axis_m - semi_major_axis_m[0]
    raw_design = np.column_stack((np.ones(len(time_us)), elapsed_s))
    joint_design = np.column_stack((
        np.ones(len(time_us)), elapsed_s,
        np.cos(2 * phase_rad), np.sin(2 * phase_rad),
        np.cos(3 * phase_rad), np.sin(3 * phase_rad),
    ))
    raw_slope = np.linalg.lstsq(raw_design, centered_axis_m, rcond=None)[0][1]
    joint_slope = np.linalg.lstsq(joint_design, centered_axis_m, rcond=None)[0][1]
    return boundary_us, raw_slope, joint_slope


@unittest.skipUnless(DATABASE.is_file(), "Local Phase 1 candidate SQLite is unavailable")
class StoredCandidateSlopeTest(unittest.TestCase):
    """Input: local three-year v2 checkpoint. Output: sampled OLS agreement."""

    def test_six_dates_and_two_orbit_windows(self):
        """Input: six dates across three years and 3/5-orbit windows.
        Output: exact boundary keys and near-equal independent OLS slopes."""
        with sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            for year, month, day in SAMPLE_DATES:
                epoch_us = int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1_000_000)
                for orbit_count in (3, 5):
                    fit = connection.execute(f"""
                        SELECT raw.time_us, raw.orbit_{orbit_count}_window_start_time_us,
                               raw.orbit_{orbit_count}_decay_rate_m_s,
                               joint.orbit_{orbit_count}_decay_rate_m_s
                        FROM swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 raw
                        JOIN swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2 joint USING(time_us)
                        WHERE raw.time_us >= ?
                          AND raw.orbit_{orbit_count}_decay_rate_m_s IS NOT NULL
                        ORDER BY raw.time_us LIMIT 1
                    """, (epoch_us,)).fetchone()
                    self.assertIsNotNone(fit)
                    boundary_us, raw_slope, joint_slope = recompute_slopes(
                        connection, fit, orbit_count,
                    )
                    self.assertEqual(boundary_us, fit[1])
                    self.assertAlmostEqual(raw_slope, fit[2], delta=1e-8)
                    self.assertAlmostEqual(joint_slope, fit[3], delta=1e-8)


if __name__ == "__main__":
    unittest.main()
