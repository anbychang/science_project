"""Change satellite states between GCRF and ITRF.

Astropy calls these systems GCRS and ITRS. GCRF and ITRF are their practical
reference frames.
"""

import astropy.units as u
import numpy as np
from astropy.coordinates import (
    EarthLocation,
    GCRS,
    ITRS,
    CartesianDifferential,
    CartesianRepresentation,
)
from astropy.time import Time
from astropy.utils import iers


iers.conf.auto_download = False


def gcrf_to_itrf(state):
    """Input: GCRF state
    Output: ITRF state"""
    if state["frame"] != "GCRF":
        raise ValueError("Input state must use GCRF.")

    time = Time(state["time"], scale="utc")
    position = np.asarray(state["position_m"]) * u.m
    velocity = np.asarray(state["velocity_m_s"]) * u.m / u.s

    cartesian_state = CartesianRepresentation(
        position,
        differentials=CartesianDifferential(velocity),
    )
    gcrf_state = GCRS(cartesian_state, obstime=time)
    itrf_state = gcrf_state.transform_to(ITRS(obstime=time))

    position_m = itrf_state.cartesian.xyz.to_value(u.m)
    velocity_itrf = itrf_state.cartesian.differentials["s"].d_xyz
    velocity_m_s = velocity_itrf.to_value(u.m / u.s)

    return {
        "time": state["time"],
        "frame": "ITRF",
        "position_m": position_m,
        "velocity_m_s": velocity_m_s,
    }


def itrf_to_gcrf(state):
    """Input: ITRF state
    Output: GCRF state"""
    return itrf_states_to_gcrf([state])[0]


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
    gcrf_velocities_m_s = (
        gcrf_states.cartesian.differentials["s"].d_xyz.to_value(u.m / u.s).T
    )

    converted_states = []
    for index in range(len(states)):
        converted_states.append(
            {
                "time": states[index]["time"],
                "frame": "GCRF",
                "position_m": gcrf_positions_m[index],
                "velocity_m_s": gcrf_velocities_m_s[index],
            }
        )

    return converted_states


def gcrf_vector_to_itrf(time_utc, vector_gcrf):
    """Input: {time_utc, vector_gcrf = [x, y, z]}
    Output: vector_itrf = [x, y, z] with the same unit"""
    time = Time(time_utc, scale="utc")
    vector = CartesianRepresentation(np.asarray(vector_gcrf) * u.m)
    gcrf_vector = GCRS(vector, obstime=time)
    itrf_vector = gcrf_vector.transform_to(ITRS(obstime=time))
    return itrf_vector.cartesian.xyz.to_value(u.m)


def itrf_vector_to_gcrf(time_utc, vector_itrf):
    """Input: {time_utc, vector_itrf = [x, y, z]}
    Output: vector_gcrf = [x, y, z] with the same unit"""
    time = Time(time_utc, scale="utc")
    vector = CartesianRepresentation(np.asarray(vector_itrf) * u.m)
    itrf_vector = ITRS(vector, obstime=time)
    gcrf_vector = itrf_vector.transform_to(GCRS(obstime=time))
    return gcrf_vector.cartesian.xyz.to_value(u.m)


def itrf_to_geodetic(state):
    """Input: ITRF state
    Output: {time, longitude_rad, latitude_rad, altitude_m}"""
    if state["frame"] != "ITRF":
        raise ValueError("Input state must use ITRF.")

    x_m, y_m, z_m = state["position_m"]
    location = EarthLocation.from_geocentric(
        x_m * u.m,
        y_m * u.m,
        z_m * u.m,
    )

    return {
        "time": state["time"],
        "frame": "GEODETIC",
        "longitude_rad": float(location.lon.to_value(u.rad)),
        "latitude_rad": float(location.lat.to_value(u.rad)),
        "altitude_m": float(location.height.to_value(u.m)),
    }
