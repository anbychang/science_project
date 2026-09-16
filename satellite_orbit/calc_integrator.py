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


def propagate(initial_state, dt_s, n_steps, start_time_utc):
    """Input: {initial_state, dt_s, n_steps, start_time_utc}
    Output: {times_utc, states}"""
    initial_state = np.asarray(initial_state, dtype=float)
    times_utc = []
    states = np.empty((n_steps + 1, initial_state.size))
    states[0] = initial_state

    time_utc = start_time_utc
    times_utc.append(time_utc)

    for step in range(n_steps):
        states[step + 1] = rk4_step(time_utc, states[step], dt_s)
        time_utc = time_utc + timedelta(seconds=dt_s)
        times_utc.append(time_utc)

    return times_utc, states
