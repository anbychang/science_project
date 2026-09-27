"""Check semi-major-axis calculation guards and units."""

import unittest
from math import sqrt

import numpy as np

from satellite_orbit.calculation.calc_forces import MU_M3_S2
from satellite_orbit.calculation.calc_orbital_response import calculate_semi_major_axis


class SemiMajorAxisTest(unittest.TestCase):
    """Input: synthetic GCRF states
    Output: checked semi-major-axis results"""

    def test_circular_orbit(self):
        """Input: circular GCRF state
        Output: its radius as semi-major axis"""
        radius_m = 7_000_000.0
        state = {
            "frame": "GCRF",
            "position_m": np.array([radius_m, 0.0, 0.0]),
            "velocity_m_s": np.array([0.0, sqrt(MU_M3_S2 / radius_m), 0.0]),
        }

        self.assertAlmostEqual(calculate_semi_major_axis(state), radius_m)

    def test_rejects_non_gcrf_state(self):
        """Input: ITRF state
        Output: ValueError"""
        state = {
            "frame": "ITRF",
            "position_m": np.array([7_000_000.0, 0.0, 0.0]),
            "velocity_m_s": np.array([0.0, 7_500.0, 0.0]),
        }

        with self.assertRaises(ValueError):
            calculate_semi_major_axis(state)

    def test_rejects_unbound_state(self):
        """Input: escape GCRF state
        Output: ValueError"""
        state = {
            "frame": "GCRF",
            "position_m": np.array([7_000_000.0, 0.0, 0.0]),
            "velocity_m_s": np.array([0.0, 20_000.0, 0.0]),
        }

        with self.assertRaises(ValueError):
            calculate_semi_major_axis(state)


if __name__ == "__main__":
    unittest.main()
