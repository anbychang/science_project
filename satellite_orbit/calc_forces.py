"""Forces used by the satellite orbit model.

Distance is kilometres and time is seconds. The orbit state uses GCRF. The J2
function uses ITRF, where the z-axis follows the Earth's north pole.
"""

import numpy as np


MU = 398600.4418
R_EARTH = 6378.137
J2 = 1.08262668e-3


def two_body_acceleration(time, position, velocity):
    """Input: {time_s, position_km, velocity_km_s}
    Output: [ax, ay, az]"""
    distance = np.linalg.norm(position)
    return -MU * position / distance**3


def j2_acceleration(position_itrf_km):
    """Input: position_itrf_km = [x, y, z]
    Output: acceleration_itrf_km_s2 = [ax, ay, az]"""
    x_km, y_km, z_km = position_itrf_km

    distance_km = np.linalg.norm(position_itrf_km)
    distance_squared_km2 = distance_km * distance_km
    z_ratio_squared = z_km * z_km / distance_squared_km2

    scale = 1.5 * J2 * MU * R_EARTH**2 / distance_km**5
    horizontal_shape = 5.0 * z_ratio_squared - 1.0
    vertical_shape = 5.0 * z_ratio_squared - 3.0

    ax_km_s2 = scale * x_km * horizontal_shape
    ay_km_s2 = scale * y_km * horizontal_shape
    az_km_s2 = scale * z_km * vertical_shape

    return np.array([ax_km_s2, ay_km_s2, az_km_s2])


def state_derivative(time, state):
    """Input: [x, y, z, vx, vy, vz]
    Output: [vx, vy, vz, ax, ay, az]"""
    position, velocity = state[:3], state[3:]
    acceleration = two_body_acceleration(time, position, velocity)
    return np.concatenate([velocity, acceleration])
