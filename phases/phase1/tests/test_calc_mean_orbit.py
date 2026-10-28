"""Check the project Orekit mean-orbit calculation boundary."""

import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from phases.phase0.code.calculation.pod.calc_coordinates import itrf_states_to_gcrf
from phases.phase1.code import calc_mean_orbit
from phases.phase1.code.calc_mean_orbit import calculate_mean_semi_major_axis


OREKIT_AVAILABLE = (Path(__file__).resolve().parents[3] / ".orekitvenv").is_dir()


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

    def test_converts_orekit_convergence_error_to_rejected_state_error(self):
        """Input: Orekit convergence failure for one GCRF state
        Output: ValueError so P1.5 records a rejection and continues"""
        class FakeOrekitException(Exception):
            pass

        class FailingPropagator:
            call_arguments = None

            @staticmethod
            def computeMeanOrbit(*arguments):
                FailingPropagator.call_arguments = arguments
                raise FakeOrekitException("did not converge")

        provider = Mock()
        context = (
            lambda *_: object(),
            lambda *_: object(),
            lambda *_: object(),
            lambda *_: object(),
            provider,
            object(),
            object(),
            FailingPropagator,
            FakeOrekitException,
            object(),
        )
        state_gcrf = {
            "time": datetime(2024, 5, 10, tzinfo=timezone.utc),
            "frame": "GCRF",
            "position_m": [6_871_000.0, 0.0, 0.0],
            "velocity_m_s": [0.0, 7_616.0, 0.0],
        }

        with patch.object(calc_mean_orbit, "_orekit_context", return_value=context):
            with self.assertRaisesRegex(ValueError, "Brouwer-Lyddane"):
                calculate_mean_semi_major_axis(state_gcrf)

        self.assertEqual(
            FailingPropagator.call_arguments[-2:],
            (
                calc_mean_orbit.MEAN_ORBIT_CONVERGENCE_EPSILON,
                calc_mean_orbit.MEAN_ORBIT_MAX_ITERATIONS,
            ),
        )

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
