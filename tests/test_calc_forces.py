"""Check gravity acceleration boundary conditions."""

import unittest

import numpy as np

from satellite_orbit.calculation.calc_forces import j2_acceleration, two_body_acceleration


class GravityAccelerationTest(unittest.TestCase):
    """Input: invalid orbit positions
    Output: a clear ValueError instead of division by zero"""

    def test_two_body_rejects_zero_distance(self):
        """Input: GCRF state at Earth's centre
        Output: ValueError"""
        state = {"frame": "GCRF", "position_m": np.zeros(3)}

        with self.assertRaises(ValueError):
            two_body_acceleration(state)

    def test_j2_rejects_zero_distance(self):
        """Input: ITRF state at Earth's centre
        Output: ValueError"""
        state = {"frame": "ITRF", "position_m": np.zeros(3)}

        with self.assertRaises(ValueError):
            j2_acceleration(state)


if __name__ == "__main__":
    unittest.main()
