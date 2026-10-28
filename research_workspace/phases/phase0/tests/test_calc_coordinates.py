"""Check a fixed ITRF-to-GCRF POD regression state."""

import unittest
import warnings
from datetime import datetime, timezone

import numpy as np
from astropy.utils.iers import IERSStaleWarning

from research_workspace.phases.phase0.code.calculation.pod.calc_coordinates import itrf_states_to_gcrf


class CoordinateConversionTest(unittest.TestCase):
    """Input: fixed ITRF POD regression state
    Output: checked GCRF state"""

    def test_fixed_pod_epoch_has_no_stale_iers_warning(self):
        """Input: fixed ITRF POD epoch
        Output: expected GCRF state without IERSStaleWarning"""
        state_itrf = {
            "time": datetime(2026, 8, 11, 23, 59, 42, tzinfo=timezone.utc),
            "frame": "ITRF",
            "position_m": np.array([-1755312.7442, -6216748.3248, 2106725.0718]),
            "velocity_m_s": np.array([-739.75979859, -2268.53029107, -7271.54469795]),
        }

        with warnings.catch_warnings():
            warnings.simplefilter("error", IERSStaleWarning)
            state_gcrf = itrf_states_to_gcrf([state_itrf])[0]

        np.testing.assert_allclose(
            state_gcrf["position_m"],
            [-5332391.83829446, -3638051.83754017, 2120742.60632132],
            atol=1e-5,
        )
        np.testing.assert_allclose(
            state_gcrf["velocity_m_s"],
            [-1777.53964896, -1653.33027528, -7266.88517196],
            atol=1e-5,
        )
