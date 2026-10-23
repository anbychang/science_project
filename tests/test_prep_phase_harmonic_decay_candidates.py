"""Test rolling P1.5.6 raw and joint-H2/H3 decay outputs."""

import sqlite3
import unittest

import numpy as np

from satellite_orbit.calculation.pod.calc_rolling_phase_decay import (
    PhaseSeries,
    RESULT_JOINT_RATE,
    RESULT_PHASE_SPAN_RAD,
    RESULT_VALID,
    calculate_window_estimate,
    solve_window_estimate,
)
from satellite_orbit.data.pod.prep_14_phase_harmonic_decay_candidates import (
    JOINT_H2_H3_SET_TABLE,
    RAW_B_L_SET_TABLE,
    REJECT_GAP,
    REJECT_INITIAL,
    PhaseSegment,
    _write_phase_segment,
    create_decay_tables,
    phase_segments,
)


MICROSECONDS_PER_SECOND = 1_000_000
SAMPLE_PERIOD_S = 10
ORBIT_PERIOD_S = 5_600
TRUE_RATE_M_S = -3.0e-4
START_TIME_US = 1_700_000_000_000_000


class RollingPhaseDecayTests(unittest.TestCase):
    """Input: synthetic 10-second B-L phase data.
    Output: verified exact-phase raw and joint-H2/H3 P1.5.6 rows."""

    def test_joint_fit_recovers_slope_after_h2_h3_removal(self):
        """Input: linear a plus known H2/H3 phase terms.
        Output: joint 3-orbit fit returns the physical slope in m/s."""
        estimate = solve_window_estimate(calculate_window_estimate(
            synthetic_series(4_000), 3,
        ))
        valid = estimate[:, RESULT_VALID] == 1.0

        self.assertGreater(valid.sum(), 0)
        self.assertAlmostEqual(
            estimate[valid][-1, RESULT_JOINT_RATE], TRUE_RATE_M_S, places=12,
        )

    def test_window_uses_exact_interpolated_phase_span(self):
        """Input: cadence not commensurate with the orbit period.
        Output: each accepted window spans exactly three phase orbits."""
        estimate = solve_window_estimate(calculate_window_estimate(
            synthetic_series(4_000), 3,
        ))
        valid = estimate[:, RESULT_VALID] == 1.0

        self.assertTrue(np.allclose(
            estimate[valid, RESULT_PHASE_SPAN_RAD], 6.0 * np.pi,
        ))

    def test_two_tables_keep_matching_10_second_keys(self):
        """Input: one continuous synthetic phase segment.
        Output: raw and joint tables keep one matching row per source time."""
        connection = sqlite3.connect(":memory:")
        try:
            create_decay_tables(connection)
            series = synthetic_series(4_000)
            with connection:
                _write_phase_segment(connection, PhaseSegment(
                    1, series, REJECT_INITIAL,
                ))
            raw_count = connection.execute(
                f"SELECT COUNT(*) FROM {RAW_B_L_SET_TABLE}",
            ).fetchone()[0]
            joint_count = connection.execute(
                f"SELECT COUNT(*) FROM {JOINT_H2_H3_SET_TABLE}",
            ).fetchone()[0]
            first_reject = connection.execute(f"""
                SELECT orbit_3_reject_reason, orbit_5_reject_reason
                FROM {RAW_B_L_SET_TABLE}
                ORDER BY time_us
                LIMIT 1
            """).fetchone()
        finally:
            connection.close()

        self.assertEqual(raw_count, 4_000)
        self.assertEqual(joint_count, 4_000)
        self.assertEqual(first_reject, ("insufficient_3_orbits", "insufficient_5_orbits"))

    def test_gap_starts_a_new_segment(self):
        """Input: one 30-second source interruption.
        Output: post-gap output begins with the explicit gap rejection reason."""
        series = synthetic_series(20)
        times = series.time_us.copy()
        times[10:] += 30 * MICROSECONDS_PER_SECOND
        segments = list(phase_segments(1, times, series.values))

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[1].initial_reject_reason, REJECT_GAP)


def synthetic_series(sample_count):
    """Input: requested synthetic 10-second sample count.
    Output: PhaseSeries with linear decay plus H2/H3 terms."""
    sample_index = np.arange(sample_count)
    time_us = START_TIME_US + sample_index * SAMPLE_PERIOD_S * MICROSECONDS_PER_SECOND
    phase_rad = sample_index * SAMPLE_PERIOD_S * 2.0 * np.pi / ORBIT_PERIOD_S
    semi_major_axis_m = (
        6_800_000.0
        + TRUE_RATE_M_S * sample_index * SAMPLE_PERIOD_S
        + 30.0 * np.cos(2.0 * phase_rad)
        + 20.0 * np.sin(3.0 * phase_rad)
    )
    return PhaseSeries(
        time_us.astype(np.int64),
        np.column_stack((semi_major_axis_m, phase_rad)),
    )
