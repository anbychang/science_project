"""Check P1.5.4--P1.5.6 phase-orbit products."""

import unittest
from math import cos, pi, sin

from phases.phase1.code.prep_10_phase_orbit_mean import (
    MICROSECONDS_PER_SECOND,
    MeanElementSample,
    daily_decay_rows,
    local_decay_rows,
    ordinary_least_squares,
    phase_orbit_rows,
    trailing_decay_rows,
)


START_TIME_US = 1_700_000_000_000_000
TWO_PI = 2.0 * pi


def mean_element_rows(chunk_id=1, semi_major_axis_at_phase=None):
    """Input: chunk ID and optional a(phase)
    Output: one complete synthetic mean-element orbit"""
    phase_step_rad = TWO_PI / 600
    return [
        (
            chunk_id,
            START_TIME_US + index * 10 * MICROSECONDS_PER_SECOND,
            (
                semi_major_axis_at_phase(index * phase_step_rad)
                if semi_major_axis_at_phase
                else 6_800_000.0
            ),
            0.0,
            0.01 + index * phase_step_rad,
        )
        for index in range(600)
    ]


def one_hour_residual_rows():
    """Input: H2/H3-subtracted one-hour signal with known linear decay
    Output: usable one-second residual rows"""
    decay_rate_m_s = -48.0 / 86_400
    orbit_period_s = 5_700
    return [
        MeanElementSample(
            1,
            START_TIME_US + index * MICROSECONDS_PER_SECOND,
            (
                6_800_000.0
                + decay_rate_m_s * index
            ),
            TWO_PI * index / orbit_period_s,
        )
        for index in range(3_601)
    ]


class PhaseOrbitMeanTest(unittest.TestCase):
    """Input: synthetic B-L mean-element rows
    Output: chunk-local phase means and OLS slopes"""

    def test_phase_weighted_mean_removes_h2_and_h3(self):
        """Input: one orbit with H2/H3 components
        Output: baseline mean and harmonic amplitudes"""
        rows = mean_element_rows(
            semi_major_axis_at_phase=lambda phase: (
                6_800_000.0 + 40.0 * cos(2.0 * phase) + 15.0 * sin(3.0 * phase)
            )
        )

        output_row = next(phase_orbit_rows(rows))

        self.assertAlmostEqual(output_row[2], 6_800_000.0, places=0)
        self.assertAlmostEqual(output_row[5], 40.0, places=0)
        self.assertAlmostEqual(output_row[8], 15.0, places=0)

    def test_rejects_orbit_at_chunk_boundary(self):
        """Input: complete phase orbit split by chunk
        Output: no cross-chunk orbit mean"""
        rows = mean_element_rows()
        rows[300] = (2, *rows[300][1:])

        output_rows = list(phase_orbit_rows(rows))

        self.assertEqual(output_rows, [])

    def test_recovers_known_ols_slope(self):
        """Input: linear phase-orbit decline
        Output: matching decay rate"""
        points = [
            (
                START_TIME_US + index * 5_700 * MICROSECONDS_PER_SECOND,
                6_800_000.0 - index * 5_700 / 86_400 * 100.0,
            )
            for index in range(15)
        ]

        fit = ordinary_least_squares(points)

        self.assertAlmostEqual(fit["rate_m_day"], -100.0, places=9)

    def test_daily_ols_does_not_cross_chunks(self):
        """Input: one day split into insufficient chunk-local groups
        Output: no daily slope"""
        rows = [
            (
                START_TIME_US + index * 5_700 * MICROSECONDS_PER_SECOND,
                6_800_000.0 - index,
                1 if index < 8 else 2,
                START_TIME_US + (index - 1) * 5_700 * MICROSECONDS_PER_SECOND,
            )
            for index in range(15)
        ]

        output_rows = list(daily_decay_rows(rows))

        self.assertEqual(output_rows, [])

    def test_centered_local_ols_recovers_linear_slope(self):
        """Input: one chunk with linear 24-hour decline
        Output: centered local 12-hour slope"""
        rows = [
            (
                START_TIME_US + index * 3_600 * MICROSECONDS_PER_SECOND,
                6_800_000.0 - index * 3_600 / 86_400 * 48.0,
                1,
                START_TIME_US + (index - 1) * 3_600 * MICROSECONDS_PER_SECOND,
            )
            for index in range(30)
        ]

        output_rows = list(local_decay_rows(rows, 12))

        self.assertAlmostEqual(output_rows[0][2], -48.0, places=9)

    def test_centered_local_ols_counts_complete_orbit_support(self):
        """Input: 94-minute orbit means over a 12-hour window
        Output: accepted fit using orbit start-to-end coverage"""
        orbit_period_s = 5_640
        rows = [
            (
                START_TIME_US + index * orbit_period_s * MICROSECONDS_PER_SECOND,
                6_800_000.0 - index * orbit_period_s / 86_400 * 24.0,
                1,
                START_TIME_US + (index - 1) * orbit_period_s * MICROSECONDS_PER_SECOND,
            )
            for index in range(20)
        ]

        output_rows = list(local_decay_rows(rows, 12))

        self.assertTrue(output_rows)
        self.assertAlmostEqual(output_rows[0][2], -24.0, places=9)

    def test_trailing_fit_recovers_one_hour_residual_decay(self):
        """Input: one hour of H2/H3-subtracted linear decline
        Output: matching trailing slope"""
        output_rows = list(trailing_decay_rows(one_hour_residual_rows()))

        self.assertAlmostEqual(output_rows[0][2], -48.0, places=8)


if __name__ == "__main__":
    unittest.main()
