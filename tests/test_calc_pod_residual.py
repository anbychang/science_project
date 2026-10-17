"""Check local POD discontinuity metrics."""

import unittest
from datetime import datetime, timedelta, timezone

from satellite_orbit.calculation.pod.calc_pod_residual import centered_residuals


UTC = timezone.utc


def state(second, position_m, velocity_m_s, source_id=1, frame="ITRF"):
    """Input: local state components
    Output: one complete synthetic orbit state"""
    return {
        "time": datetime(2024, 1, 1, tzinfo=UTC) + timedelta(seconds=second),
        "frame": frame,
        "position_m": position_m,
        "velocity_m_s": velocity_m_s,
        "source_id": source_id,
    }


class PodResidualTest(unittest.TestCase):
    """Input: three synthetic POD states
    Output: local residual metrics or no result"""

    def test_returns_zero_for_constant_velocity_trio(self):
        """Input: continuous linear motion
        Output: zero curvature and velocity residual"""
        result = centered_residuals(
            [
                state(0, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
                state(10, [10.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
                state(20, [20.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
            ]
        )
        self.assertEqual(result, {"position_curvature_m": 0.0, "velocity_residual_m_s": 0.0})

    def test_detects_position_jump(self):
        """Input: central position jump
        Output: nonzero position curvature"""
        result = centered_residuals(
            [
                state(0, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
                state(10, [110.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
                state(20, [20.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
            ]
        )
        self.assertEqual(result["position_curvature_m"], 100.0)

    def test_detects_velocity_jump(self):
        """Input: central velocity jump
        Output: nonzero velocity residual"""
        result = centered_residuals(
            [
                state(0, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
                state(10, [10.0, 0.0, 0.0], [4.0, 0.0, 0.0]),
                state(20, [20.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
            ]
        )
        self.assertEqual(result["velocity_residual_m_s"], 3.0)

    def test_returns_none_for_source_frame_or_cadence_break(self):
        """Input: discontinuous source, frame, or cadence
        Output: no residual"""
        baseline = [
            state(0, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
            state(10, [10.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
            state(20, [20.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
        ]
        source_break = [*baseline]
        source_break[1] = state(10, [10.0, 0.0, 0.0], [1.0, 0.0, 0.0], source_id=2)
        frame_break = [*baseline]
        frame_break[1] = state(10, [10.0, 0.0, 0.0], [1.0, 0.0, 0.0], frame="GCRF")
        gap_break = [*baseline]
        gap_break[2] = state(30, [30.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        self.assertIsNone(centered_residuals(source_break))
        self.assertIsNone(centered_residuals(frame_break))
        self.assertIsNone(centered_residuals(gap_break))
