"""Check P1.5.4 Fourier-fit plotting inputs."""

import unittest
from math import pi

from satellite_orbit.data.pod.prep_11_phase_orbit_figures import (
    FourierFitOrbit,
    day_time_bounds,
    phase_fit_deviation_m,
    reconstruct_phase_orbit,
    time_window_rows,
)


class FourierFitFigureTest(unittest.TestCase):
    """Input: synthetic H2 phase orbit
    Output: matching raw and reconstructed deviations"""

    def test_reconstructs_h2_deviation_from_stored_coefficients(self):
        """Input: exact H2 samples
        Output: zero raw-minus-fit residual at each phase"""
        orbit = FourierFitOrbit(
            time_us=1_700_000_000_000_000,
            phase_weighted_mean_a_m=6_800_000.0,
            h2_cosine_m=10.0,
            h2_sine_m=0.0,
            h3_cosine_m=0.0,
            h3_sine_m=0.0,
            source_rows=[
                (1, 6_800_010.0, 0.0, 0.0),
                (2, 6_800_000.0, 0.0, pi / 4.0),
                (3, 6_799_990.0, 0.0, pi / 2.0),
            ],
        )

        reconstructed_rows = reconstruct_phase_orbit(orbit)

        self.assertEqual(
            [round(raw_value_m - fitted_value_m, 12) for _, raw_value_m, fitted_value_m in reconstructed_rows],
            [0.0, 0.0, 0.0],
        )

    def test_combines_h2_and_h3_terms_at_one_phase(self):
        """Input: H2/H3 coefficients and one phase.
        Output: combined fitted deviation in metres."""
        fitted_deviation_m = phase_fit_deviation_m((10.0, 0.0, 5.0, 0.0), 0.0)

        self.assertEqual(fitted_deviation_m, 15.0)

    def test_day_bounds_span_one_utc_day(self):
        """Input: leap-day label
        Output: consecutive UTC day bounds"""
        start_time_us, stop_time_us = day_time_bounds("2024-02-29")

        self.assertEqual(stop_time_us - start_time_us, 86_400_000_000)

    def test_time_window_rows_excludes_stop_endpoint(self):
        """Input: rows at both time-window endpoints
        Output: start-inclusive and stop-exclusive selection"""
        selected_rows = time_window_rows(
            [(10, 1.0, 0.1), (20, 2.0, 0.1), (30, 3.0, 0.1)], 20, 30,
        )

        self.assertEqual(selected_rows, [(20, 2.0, 0.1)])


if __name__ == "__main__":
    unittest.main()
