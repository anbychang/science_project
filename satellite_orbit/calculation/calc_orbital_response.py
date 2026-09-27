"""Calculate the instantaneous orbit size from one GCRF state."""

from math import isfinite, sqrt

from satellite_orbit.calculation.calc_forces import MU_M3_S2


def calculate_semi_major_axis(state):
    """Input: GCRF state
    Output: semi_major_axis_m"""
    if state["frame"] != "GCRF":
        raise ValueError("Semi-major-axis state must use GCRF.")

    x_m, y_m, z_m = state["position_m"]
    vx_m_s, vy_m_s, vz_m_s = state["velocity_m_s"]

    distance_m = sqrt(x_m**2 + y_m**2 + z_m**2)
    speed_m_s = sqrt(vx_m_s**2 + vy_m_s**2 + vz_m_s**2)
    if not isfinite(distance_m) or not isfinite(speed_m_s) or distance_m <= 0.0:
        raise ValueError("Orbit state has an invalid distance or speed.")

    specific_energy_m2_s2 = speed_m_s**2 / 2.0 - MU_M3_S2 / distance_m
    if not isfinite(specific_energy_m2_s2) or specific_energy_m2_s2 >= 0.0:
        raise ValueError("Orbit state is not bound to Earth.")

    return -MU_M3_S2 / (2.0 * specific_energy_m2_s2)
