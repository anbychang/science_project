"""Check the project Orekit mean-orbit calculation boundary."""

import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from satellite_orbit.calculation.pod.calc_coordinates import itrf_states_to_gcrf
from satellite_orbit.calculation.pod.calc_mean_orbit import calculate_mean_semi_major_axis


OREKIT_AVAILABLE = (Path(__file__).resolve().parents[1] / ".orekitvenv").is_dir()


class MeanOrbitTest(unittest.TestCase):
    """Input: synthetic GCRF orbit states
    Output: Brouwer-Lyddane mean semi-major-axis checks"""

    def test_rejects_itrf_state(self):
        """Input: ITRF state
        Output: ValueError before calling Orekit"""
        state_itrf = {
            "time": datetime(2024, 5, 10, tzinfo=timezone.utc),
            "frame": "ITRF",
            "position_m": [6_871_000.0, 0.0, 0.0],
            "velocity_m_s": [0.0, 7_616.0, 0.0],
        }

        with self.assertRaises(ValueError):
            calculate_mean_semi_major_axis(state_itrf)

    @unittest.skipUnless(OREKIT_AVAILABLE, "requires .orekitvenv")
    def test_fixed_gcrf_state_has_expected_mean_semi_major_axis(self):
        """Input: fixed synthetic GCRF state
        Output: fixed Orekit mean semi-major axis"""
        state_gcrf = {
            "time": datetime(2024, 5, 10, 14, 20, 2, tzinfo=timezone.utc),
            "frame": "GCRF",
            "position_m": [6_871_000.0, 0.0, 0.0],
            "velocity_m_s": [0.0, 7_616.0, 0.0],
        }

        mean_semi_major_axis_m = calculate_mean_semi_major_axis(state_gcrf)

        self.assertAlmostEqual(mean_semi_major_axis_m, 6_870_017.991019535, places=3)

    @unittest.skipUnless(OREKIT_AVAILABLE, "requires .orekitvenv")
    def test_fixed_itrf_pod_state_has_expected_mean_semi_major_axis(self):
        """Input: fixed real POD ITRF state
        Output: fixed mean semi-major axis after the GCRF transform"""
        state_itrf = {
            "time": datetime(2026, 8, 11, 23, 59, 42, tzinfo=timezone.utc),
            "frame": "ITRF",
            "position_m": np.array([-1_755_312.7442, -6_216_748.3248, 2_106_725.0718]),
            "velocity_m_s": np.array([-739.75979859, -2_268.53029107, -7_271.54469795]),
        }

        state_gcrf = itrf_states_to_gcrf([state_itrf])[0]
        mean_semi_major_axis_m = calculate_mean_semi_major_axis(state_gcrf)

        self.assertAlmostEqual(mean_semi_major_axis_m, 6_791_172.238370249, places=2)


if __name__ == "__main__":
    unittest.main()
