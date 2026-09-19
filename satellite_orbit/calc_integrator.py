"""Numerically advance an orbital state with fourth-order Runge-Kutta."""

from datetime import timedelta

import numpy as np

from satellite_orbit.calc_forces import state_derivative


def rk4_step(time_utc, state, dt_s):
    """Input: {time_utc, [x, y, z, vx, vy, vz], dt_s}
    Output: [x, y, z, vx, vy, vz]"""
    half_time_utc = time_utc + timedelta(seconds=0.5 * dt_s)
    end_time_utc = time_utc + timedelta(seconds=dt_s)

    k1 = state_derivative(time_utc, state)
    k2 = state_derivative(half_time_utc, state + 0.5 * dt_s * k1)
    k3 = state_derivative(half_time_utc, state + 0.5 * dt_s * k2)
    k4 = state_derivative(end_time_utc, state + dt_s * k3)

    return state + (dt_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def make_gcrf_orbit_point(time_utc, state):
    """Input: {time_utc, [x, y, z, vx, vy, vz]}
    Output: {time, x_gcrf_m, ..., vz_gcrf_m_s}"""
    return {
        "time": time_utc,
        "x_gcrf_m": state[0],
        "y_gcrf_m": state[1],
        "z_gcrf_m": state[2],
        "vx_gcrf_m_s": state[3],
        "vy_gcrf_m_s": state[4],
        "vz_gcrf_m_s": state[5],
    }


def propagate(initial_state, dt_s, n_steps, start_time_utc):
    """Input: {initial_state, dt_s, n_steps, start_time_utc}
    Output: [{time, x_gcrf_m, ..., vz_gcrf_m_s}, ...]"""
    state = np.asarray(initial_state, dtype=float)
    orbit_points = []

    time_utc = start_time_utc
    orbit_points.append(make_gcrf_orbit_point(time_utc, state))

    for _ in range(n_steps):
        state = rk4_step(time_utc, state, dt_s)
        time_utc = time_utc + timedelta(seconds=dt_s)
        orbit_points.append(make_gcrf_orbit_point(time_utc, state))

    return orbit_points
