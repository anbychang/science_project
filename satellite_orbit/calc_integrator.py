"""Numerically advance an orbital state with fourth-order Runge-Kutta."""

import numpy as np

from satellite_orbit.calc_forces import state_derivative


def rk4_step(time, state, dt):
    """Input: {time_s, [x, y, z, vx, vy, vz], dt_s}
    Output: [x, y, z, vx, vy, vz]"""
    k1 = state_derivative(time, state)
    k2 = state_derivative(time + 0.5 * dt, state + 0.5 * dt * k1)
    k3 = state_derivative(time + 0.5 * dt, state + 0.5 * dt * k2)
    k4 = state_derivative(time + dt, state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def propagate(initial_state, dt, n_steps, start_time=0.0):
    """Input: {initial_state, dt_s, n_steps}
    Output: {times_s, states}"""
    times = start_time + dt * np.arange(n_steps + 1)
    states = np.empty((n_steps + 1, initial_state.size))
    states[0] = initial_state

    for step in range(n_steps):
        states[step + 1] = rk4_step(times[step], states[step], dt)

    return times, states
