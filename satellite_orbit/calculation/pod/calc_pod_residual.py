"""Calculate local POD discontinuity metrics from three orbit states."""

from math import sqrt

EXPECTED_CADENCE_S = 10.0


def centered_residuals(states, expected_cadence_s=EXPECTED_CADENCE_S):
    """Input: [{time, frame, position_m, velocity_m_s, source_id}, ...]
    Output: {position_curvature_m, velocity_residual_m_s} or None"""
    if len(states) != 3:
        raise ValueError("Exactly three orbit states are required.")

    previous_state, current_state, next_state = states
    if not _is_continuous_trio(
        previous_state, current_state, next_state, expected_cadence_s
    ):
        return None

    total_time_s = 2.0 * expected_cadence_s
    centered_velocity_m_s = [
        (next_value - previous_value) / total_time_s
        for previous_value, next_value in zip(
            previous_state["position_m"], next_state["position_m"]
        )
    ]
    return {
        "position_curvature_m": _norm(
            [
                current_value - (previous_value + next_value) / 2.0
                for previous_value, current_value, next_value in zip(
                    previous_state["position_m"],
                    current_state["position_m"],
                    next_state["position_m"],
                )
            ]
        ),
        "velocity_residual_m_s": _norm(
            [
                current_value - centered_value
                for current_value, centered_value in zip(
                    current_state["velocity_m_s"], centered_velocity_m_s
                )
            ]
        ),
    }


def _is_continuous_trio(previous_state, current_state, next_state, cadence_s):
    """Input: three state dictionaries and expected cadence
    Output: True when the states form one continuous source/frame trio"""
    if cadence_s <= 0.0:
        raise ValueError("expected_cadence_s must be positive.")
    if len({state["source_id"] for state in (previous_state, current_state, next_state)}) != 1:
        return False
    if len({state["frame"] for state in (previous_state, current_state, next_state)}) != 1:
        return False
    first_gap_s = (current_state["time"] - previous_state["time"]).total_seconds()
    second_gap_s = (next_state["time"] - current_state["time"]).total_seconds()
    return first_gap_s == cadence_s and second_gap_s == cadence_s


def _norm(values):
    """Input: numeric vector
    Output: Euclidean norm"""
    return sqrt(sum(value * value for value in values))
