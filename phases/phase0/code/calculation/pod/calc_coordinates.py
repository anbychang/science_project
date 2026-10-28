"""Change satellite states between GCRF and ITRF.

Astropy calls these systems GCRS and ITRS. GCRF and ITRF are their practical
reference frames.
"""

import astropy.units as u
import numpy as np
from astropy.coordinates import (
    GCRS,
    ITRS,
    CartesianDifferential,
    CartesianRepresentation,
)
from astropy.time import Time
from astropy.utils import iers

iers.conf.auto_download = False


def itrf_states_to_gcrf(states):
    """Input: [ITRF state_1, ITRF state_2, ...]
    Output: [GCRF state_1, GCRF state_2, ...]"""
    if not states:
        return []

    for state in states:
        if state["frame"] != "ITRF":
            raise ValueError("Input states must use ITRF.")

    times = Time([state["time"] for state in states], scale="utc")
    positions_m = np.array([state["position_m"] for state in states]).T
    velocities_m_s = np.array([state["velocity_m_s"] for state in states]).T

    cartesian_states = CartesianRepresentation(
        positions_m * u.m,
        differentials=CartesianDifferential(velocities_m_s * u.m / u.s),
    )
    itrf_states = ITRS(cartesian_states, obstime=times)
    gcrf_states = itrf_states.transform_to(GCRS(obstime=times))

    gcrf_positions_m = gcrf_states.cartesian.xyz.to_value(u.m).T
    gcrf_velocities_m_s = gcrf_states.cartesian.differentials["s"].d_xyz.to_value(u.m / u.s).T

    converted_states = []
    for index in range(len(states)):
        converted_state = states[index].copy()
        converted_state["frame"] = "GCRF"
        converted_state["position_m"] = gcrf_positions_m[index]
        converted_state["velocity_m_s"] = gcrf_velocities_m_s[index]
        converted_states.append(converted_state)

    return converted_states
