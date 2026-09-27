"""Check an ITRF-to-GCRF conversion at the latest local POD date."""

import unittest
import warnings
from datetime import datetime, timezone

import numpy as np
from astropy.utils.iers import IERSStaleWarning

from satellite_orbit.calculation.calc_coordinates import gcrf_to_itrf, itrf_to_gcrf


class CoordinateConversionTest(unittest.TestCase):
    """Input: latest local ITRF POD state
    Output: checked GCRF round-trip state"""

    def test_latest_pod_date_has_no_stale_iers_warning(self):
        """Input: ITRF state at latest local POD date
        Output: GCRF round trip without IERSStaleWarning"""
        state_itrf = {
            "time": datetime(2026, 8, 11, 23, 59, 42, tzinfo=timezone.utc),
            "frame": "ITRF",
            "position_m": np.array([-1755312.7442, -6216748.3248, 2106725.0718]),
            "velocity_m_s": np.array([-739.75979859, -2268.53029107, -7271.54469795]),
        }

        with warnings.catch_warnings():
            warnings.simplefilter("error", IERSStaleWarning)
            state_gcrf = itrf_to_gcrf(state_itrf)
            round_trip_itrf = gcrf_to_itrf(state_gcrf)

        np.testing.assert_allclose(
            round_trip_itrf["position_m"],
            state_itrf["position_m"],
            atol=1e-4,
        )
        np.testing.assert_allclose(
            round_trip_itrf["velocity_m_s"],
            state_itrf["velocity_m_s"],
            atol=1e-6,
        )
