"""Check that RK4 keeps non-kinematic state fields."""

import unittest
from datetime import datetime, timezone
from math import sqrt

import numpy as np

from satellite_orbit.calculation.calc_forces import MU_M3_S2
from satellite_orbit.calculation.calc_integrator import rk4_step, shifted_state


def circular_state():
    """Input: none
    Output: GCRF circular state with weather fields"""
    radius_m = 7_000_000.0
    return {
        "time": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "frame": "GCRF",
        "position_m": np.array([radius_m, 0.0, 0.0]),
        "velocity_m_s": np.array([0.0, sqrt(MU_M3_S2 / radius_m), 0.0]),
        "f107_sfu": 120.0,
        "ap_values": [10.0] * 7,
    }


class IntegratorStateTest(unittest.TestCase):
    """Input: GCRF state with supporting fields
    Output: fields remain available after an RK4 step"""

    def test_shifted_state_keeps_supporting_fields(self):
        """Input: state with weather and a zero derivative
        Output: shifted state keeps weather values"""
        state = circular_state()
        derivative = {
            "position_rate_m_s": np.zeros(3),
            "velocity_rate_m_s2": np.zeros(3),
        }

        shifted = shifted_state(state, derivative, 5.0)

        self.assertEqual(shifted["f107_sfu"], 120.0)
        self.assertEqual(shifted["ap_values"], [10.0] * 7)

    def test_rk4_step_keeps_supporting_fields(self):
        """Input: state with weather fields
        Output: next state keeps weather values"""
        next_state = rk4_step(circular_state(), 10.0)

        self.assertEqual(next_state["f107_sfu"], 120.0)
        self.assertEqual(next_state["ap_values"], [10.0] * 7)


if __name__ == "__main__":
    unittest.main()
