"""Physical terms used by the ISS orbit propagator.

The current model contains only two-body gravity. Coordinates use the EME2000
frame; distance is kilometres and time is seconds.
"""

import numpy as np


MU = 398600.4418
R_EARTH = 6378.137


def two_body_acceleration(time, position, velocity):
    """輸入：{time_s, position_km, velocity_km_s}
    輸出：[ax, ay, az]"""
    distance = np.linalg.norm(position)
    return -MU * position / distance**3


def state_derivative(time, state):
    """輸入：[x, y, z, vx, vy, vz]
    輸出：[vx, vy, vz, ax, ay, az]"""
    position, velocity = state[:3], state[3:]
    acceleration = two_body_acceleration(time, position, velocity)
    return np.concatenate([velocity, acceleration])
