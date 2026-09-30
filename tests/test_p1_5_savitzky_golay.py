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
MEAN_SERIES_SAMPLE_INTERVAL_S = 600.0
MEAN_SERIES_WINDOW_SAMPLES = 73
MEAN_SERIES_POLYNOMIAL_ORDER = 2
MEAN_SERIES_NOISE_STD_M = 0.1
MEAN_SERIES_FIT_NOISE_SEED = 20_260_930
MEAN_SERIES_HELD_OUT_NOISE_SEED = 7
MAX_MEAN_SERIES_MEDIAN_ERROR_M_DAY = 0.1
MAX_MEAN_SERIES_P95_ERROR_M_DAY = 0.2


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


def create_synthetic_mean_series(noise_seed):
    """Input: deterministic Gaussian-noise seed
    Output: (true_semi_major_axis_m, mean_like_semi_major_axis_m)"""
    time_s = np.arange(0.0, DAY_S, MEAN_SERIES_SAMPLE_INTERVAL_S)
    true_semi_major_axis_m = 6_800_000.0 - TRUE_DECAY_RATE_M_DAY * time_s / DAY_S
    noise_m = np.random.default_rng(noise_seed).normal(
        0.0, MEAN_SERIES_NOISE_STD_M, time_s.size
    )
    return true_semi_major_axis_m, true_semi_major_axis_m + noise_m


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
    half_window_samples = window_length // 2
    interior_decay_rate_m_day = decay_rate_m_day[
        half_window_samples:-half_window_samples
    ]
    absolute_errors_m_day = np.abs(interior_decay_rate_m_day - TRUE_DECAY_RATE_M_DAY)
    return float(np.median(interior_decay_rate_m_day)), float(
        np.percentile(absolute_errors_m_day, 95.0)
    )


def calculate_mean_series_interior_decay_rates(mean_like_series_m):
    """Input: regular 10-minute mean-like series
    Output: interior decay_rate_m_day[]"""
    decay_rate_m_day = -savgol_filter(
        mean_like_series_m,
        MEAN_SERIES_WINDOW_SAMPLES,
        MEAN_SERIES_POLYNOMIAL_ORDER,
        deriv=1,
        delta=MEAN_SERIES_SAMPLE_INTERVAL_S,
    ) * DAY_S
    half_window_samples = MEAN_SERIES_WINDOW_SAMPLES // 2
    return decay_rate_m_day[half_window_samples:-half_window_samples]


class SavitzkyGolayCandidateTest(unittest.TestCase):
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

    def test_mean_series_candidate_recovers_median_decay(self):
        """Input: mean-like 10-minute series with 0.1 m residual noise
        Output: median decay within 0.1 m/day of truth"""
        _, mean_like_series_m = create_synthetic_mean_series(MEAN_SERIES_FIT_NOISE_SEED)
        interior_decay_rate_m_day = calculate_mean_series_interior_decay_rates(
            mean_like_series_m
        )

        self.assertLessEqual(
            abs(float(np.median(interior_decay_rate_m_day)) - TRUE_DECAY_RATE_M_DAY),
            MAX_MEAN_SERIES_MEDIAN_ERROR_M_DAY,
        )

    def test_mean_series_candidate_limits_pointwise_decay_error(self):
        """Input: mean-like 10-minute series with 0.1 m residual noise
        Output: 95th-percentile error within 0.2 m/day"""
        _, mean_like_series_m = create_synthetic_mean_series(MEAN_SERIES_FIT_NOISE_SEED)
        interior_decay_rate_m_day = calculate_mean_series_interior_decay_rates(
            mean_like_series_m
        )
        p95_error_m_day = float(
            np.percentile(
                np.abs(interior_decay_rate_m_day - TRUE_DECAY_RATE_M_DAY),
                95.0,
            )
        )

        self.assertLessEqual(p95_error_m_day, MAX_MEAN_SERIES_P95_ERROR_M_DAY)

    def test_mean_series_candidate_limits_held_out_pointwise_error(self):
        """Input: mean-like series with a different residual-noise seed
        Output: held-out 95th-percentile error within 0.2 m/day"""
        _, mean_like_series_m = create_synthetic_mean_series(
            MEAN_SERIES_HELD_OUT_NOISE_SEED
        )
        interior_decay_rate_m_day = calculate_mean_series_interior_decay_rates(
            mean_like_series_m
        )
        p95_error_m_day = float(
            np.percentile(
                np.abs(interior_decay_rate_m_day - TRUE_DECAY_RATE_M_DAY),
                95.0,
            )
        )

        self.assertLessEqual(p95_error_m_day, MAX_MEAN_SERIES_P95_ERROR_M_DAY)


if __name__ == "__main__":
    unittest.main()
