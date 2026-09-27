"""Numerically advance an orbital state with fourth-order Runge-Kutta."""

from datetime import timedelta

from satellite_orbit.calculation.calc_forces import state_derivative


def shifted_state(state, derivative, shift_s):
    """Input: {state, derivative, shift_s}
    Output: shifted GCRF state"""
    shifted = state.copy()
    shifted["time"] = state["time"] + timedelta(seconds=shift_s)
    shifted["position_m"] = (
        state["position_m"] + shift_s * derivative["position_rate_m_s"]
    )
    shifted["velocity_m_s"] = (
        state["velocity_m_s"] + shift_s * derivative["velocity_rate_m_s2"]
    )
    return shifted


def rk4_step(state, dt_s):
    """Input: {GCRF state, dt_s}
    Output: GCRF state after dt_s"""
    if state["frame"] != "GCRF":
        raise ValueError("RK4 state must use GCRF.")

    k1 = state_derivative(state)
    k2 = state_derivative(shifted_state(state, k1, 0.5 * dt_s))
    k3 = state_derivative(shifted_state(state, k2, 0.5 * dt_s))
    k4 = state_derivative(shifted_state(state, k3, dt_s))

    position_change_m = (dt_s / 6.0) * (
        k1["position_rate_m_s"]
        + 2.0 * k2["position_rate_m_s"]
        + 2.0 * k3["position_rate_m_s"]
        + k4["position_rate_m_s"]
    )
    velocity_change_m_s = (dt_s / 6.0) * (
        k1["velocity_rate_m_s2"]
        + 2.0 * k2["velocity_rate_m_s2"]
        + 2.0 * k3["velocity_rate_m_s2"]
        + k4["velocity_rate_m_s2"]
    )

    next_state = state.copy()
    next_state["time"] = state["time"] + timedelta(seconds=dt_s)
    next_state["position_m"] = state["position_m"] + position_change_m
    next_state["velocity_m_s"] = state["velocity_m_s"] + velocity_change_m_s
    return next_state


def propagate(initial_state, dt_s, n_steps):
    """Input: {initial_state, dt_s, n_steps}
    Output: [GCRF state, ...]"""
    orbit_states = [initial_state]
    state = initial_state

    for _ in range(n_steps):
        state = rk4_step(state, dt_s)
        orbit_states.append(state)

    return orbit_states
