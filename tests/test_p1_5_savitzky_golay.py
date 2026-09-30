"""Test the rejected direct Savitzky-Golay P1.5-A candidate."""

from math import pi
import unittest

import numpy as np
from scipy.signal import savgol_filter


DAY_S = 86_400.0
SAMPLE_INTERVAL_S = 10.0
DOMINANT_SHORT_PERIOD_S = 2_780.0
TRUE_DECAY_RATE_M_DAY = 1.0
RAW_SG_WINDOWS = (279, 559, 837)
POLYNOMIAL_ORDERS = (2, 3)
MAX_MEDIAN_ERROR_M_DAY = 0.05
MAX_P95_ERROR_M_DAY = 0.2


def create_synthetic_osculating_series():
    """Input: none
    Output: (true_semi_major_axis_m, osculating_semi_major_axis_m)"""
    time_s = np.arange(0.0, DAY_S, SAMPLE_INTERVAL_S)
    true_semi_major_axis_m = 6_800_000.0 - TRUE_DECAY_RATE_M_DAY * time_s / DAY_S
    periodic_variation_m = (
        9_500.0 * np.sin(2.0 * pi * time_s / DOMINANT_SHORT_PERIOD_S)
        + 1_200.0 * np.sin(4.0 * pi * time_s / DOMINANT_SHORT_PERIOD_S + 0.6)
    )
    noise_m = np.random.default_rng(20_260_930).normal(0.0, 25.0, time_s.size)
    return true_semi_major_axis_m, true_semi_major_axis_m + periodic_variation_m + noise_m


def calculate_interior_decay_errors(observed_semi_major_axis_m, window_length, polynomial_order):
    """Input: regular series, odd window length, polynomial order
    Output: (median_decay_m_day, p95_absolute_error_m_day)"""
    decay_rate_m_day = -savgol_filter(
        observed_semi_major_axis_m,
        window_length,
        polynomial_order,
        deriv=1,
        delta=SAMPLE_INTERVAL_S,
    ) * DAY_S
    interior_decay_rate_m_day = decay_rate_m_day[window_length:-window_length]
    absolute_errors_m_day = np.abs(interior_decay_rate_m_day - TRUE_DECAY_RATE_M_DAY)
    return float(np.median(interior_decay_rate_m_day)), float(
        np.percentile(absolute_errors_m_day, 95.0)
    )


class DirectSavitzkyGolayTest(unittest.TestCase):
    """Input: synthetic 10-second semi-major-axis series
    Output: direct raw-SG candidate decision"""

    def test_preserves_a_linear_decay_without_short_period_variation(self):
        """Input: one m/day linear decline
        Output: one m/day interior decay rate"""
        time_s = np.arange(0.0, DAY_S, SAMPLE_INTERVAL_S)
        linear_series_m = 6_800_000.0 - TRUE_DECAY_RATE_M_DAY * time_s / DAY_S

        median_decay_rate_m_day, _ = calculate_interior_decay_errors(
            linear_series_m, RAW_SG_WINDOWS[0], POLYNOMIAL_ORDERS[0]
        )

        self.assertAlmostEqual(median_decay_rate_m_day, TRUE_DECAY_RATE_M_DAY, places=7)

    def test_rejects_direct_raw_sg_candidates_with_short_period_variation(self):
        """Input: decay plus dominant short-period variation and fixed noise
        Output: no acceptable direct raw-SG candidate"""
        _, observed_series_m = create_synthetic_osculating_series()
        qualifying_candidates = []

        for window_length in RAW_SG_WINDOWS:
            for polynomial_order in POLYNOMIAL_ORDERS:
                median_decay_m_day, p95_error_m_day = calculate_interior_decay_errors(
                    observed_series_m, window_length, polynomial_order
                )
                if (
                    abs(median_decay_m_day - TRUE_DECAY_RATE_M_DAY) <= MAX_MEDIAN_ERROR_M_DAY
                    and p95_error_m_day <= MAX_P95_ERROR_M_DAY
                ):
                    qualifying_candidates.append((window_length, polynomial_order))

        self.assertEqual(qualifying_candidates, [])


if __name__ == "__main__":
    unittest.main()
