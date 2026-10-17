"""Calculate the instantaneous orbit size from one GCRF state."""

from math import hypot, isfinite

MU_M3_S2 = 3.986004418e14


def calculate_semi_major_axis(state):
    """Input: GCRF state
    Output: semi_major_axis_m"""
    if state["frame"] != "GCRF":
        raise ValueError("Semi-major-axis state must use GCRF.")

    x_m, y_m, z_m = state["position_m"]
    vx_m_s, vy_m_s, vz_m_s = state["velocity_m_s"]

    distance_m = hypot(x_m, y_m, z_m)
    speed_m_s = hypot(vx_m_s, vy_m_s, vz_m_s)
    if not isfinite(distance_m) or not isfinite(speed_m_s) or distance_m <= 0.0:
        raise ValueError("Orbit state has an invalid distance or speed.")

    specific_energy_m2_s2 = speed_m_s**2 / 2.0 - MU_M3_S2 / distance_m
    if not isfinite(specific_energy_m2_s2) or specific_energy_m2_s2 >= 0.0:
        raise ValueError("Orbit state is not bound to Earth.")

    return -MU_M3_S2 / (2.0 * specific_energy_m2_s2)
