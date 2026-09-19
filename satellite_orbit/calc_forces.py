"""Forces used by the satellite orbit model.

Distance is metres and time is seconds. The orbit state uses GCRF. The J2
function uses ITRF, where the z-axis follows the Earth's north pole.
"""

import numpy as np

from satellite_orbit.calc_coordinates import (
    gcrf_vector_to_itrf,
    itrf_vector_to_gcrf,
)

MU_M3_S2 = 3.986004418e14
R_EARTH_M = 6378137.0
J2 = 1.08262668e-3


def two_body_acceleration(position_gcrf_m):
    """Input: position_gcrf_m = [x, y, z]
    Output: [ax, ay, az]"""
    distance_m = np.linalg.norm(position_gcrf_m)
    return -MU_M3_S2 * position_gcrf_m / distance_m**3


def j2_acceleration(position_itrf_m):
    """Input: position_itrf_m = [x, y, z]
    Output: acceleration_itrf_m_s2 = [ax, ay, az]"""
    x_m, y_m, z_m = position_itrf_m

    distance_m = np.linalg.norm(position_itrf_m)
    distance_squared_m2 = distance_m * distance_m
    z_ratio_squared = z_m * z_m / distance_squared_m2

    scale = 1.5 * J2 * MU_M3_S2 * R_EARTH_M**2 / distance_m**5
    horizontal_shape = 5.0 * z_ratio_squared - 1.0
    vertical_shape = 5.0 * z_ratio_squared - 3.0

    ax_m_s2 = scale * x_m * horizontal_shape
    ay_m_s2 = scale * y_m * horizontal_shape
    az_m_s2 = scale * z_m * vertical_shape

    return np.array([ax_m_s2, ay_m_s2, az_m_s2])


def gravity_acceleration(time_utc, position_gcrf_m):
    """Input: {time_utc, position_gcrf_m}
    Output: acceleration_gcrf_m_s2 = [ax, ay, az]"""
    two_body_gcrf = two_body_acceleration(position_gcrf_m)

    position_itrf_m = gcrf_vector_to_itrf(time_utc, position_gcrf_m)
    j2_itrf_m_s2 = j2_acceleration(position_itrf_m)
    j2_gcrf_m_s2 = itrf_vector_to_gcrf(time_utc, j2_itrf_m_s2)

    return two_body_gcrf + j2_gcrf_m_s2


def state_derivative(time_utc, state):
    """Input: {time_utc, [x, y, z, vx, vy, vz]}
    Output: [vx, vy, vz, ax, ay, az]"""
    position, velocity = state[:3], state[3:]
    acceleration = gravity_acceleration(time_utc, position)
    return np.concatenate([velocity, acceleration])
