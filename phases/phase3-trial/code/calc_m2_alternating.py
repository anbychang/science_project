"""Alternate a shared SME response fit with per-event trial multipliers."""

import math

import numpy as np

from calc_m2_tau import score_tau_grid


TRIAL_R = np.arange(40, 161, dtype=float) / 100
TRIAL_LOG_R = np.log(TRIAL_R)


def event_sums(residual: np.ndarray, response: np.ndarray) -> dict:
    """Input: [ln(L2/M0)], [minute x 41 response nT]. Output: event sums."""
    if residual.ndim != 1 or response.shape != (len(residual), 41):
        raise ValueError("Expected one residual and 41 responses per minute")
    if not len(residual) or not np.isfinite(residual).all() or not np.isfinite(response).all():
        raise ValueError("Event inputs must be nonempty and finite")
    return {
        "minutes": len(residual),
        "residual_sum": float(np.sum(residual)),
        "residual_squared": float(residual @ residual),
        "response_sum": np.sum(response, axis=0),
        "cross": response.T @ residual,
        "response_squared": np.sum(response * response, axis=0),
    }


def common_tau_grid(events: dict, r_by_storm: dict) -> list[tuple[float, float, float]]:
    """Input: {storm: event sums}, {storm: R}. Output: [(tau, G, RMSE), ...]."""
    total = {
        "minutes": 0,
        "anomaly_squared": 0.0,
        "cross": np.zeros(41),
        "response_squared": np.zeros(41),
    }
    for storm_id, event in events.items():
        log_r = math.log(r_by_storm[storm_id])
        total["minutes"] += event["minutes"]
        total["anomaly_squared"] += (
            event["residual_squared"] - 2 * log_r * event["residual_sum"]
            + event["minutes"] * log_r * log_r
        )
        total["cross"] += event["cross"] - log_r * event["response_sum"]
        total["response_squared"] += event["response_squared"]
    return score_tau_grid(total)


def choose_r_trial(event: dict, tau_hours: float, gain_per_nt: float) -> tuple[float, float]:
    """Input: event sums, tau h, gain 1/nT. Output: (trial R, RMSE)."""
    index = round(tau_hours * 4)
    if abs(index / 4 - tau_hours) > 1e-12 or not 0 <= index <= 40:
        raise ValueError("Tau must lie on the 0.25-hour grid")
    corrected_sum = event["residual_sum"] - gain_per_nt * event["response_sum"][index]
    corrected_squared = (
        event["residual_squared"]
        - 2 * gain_per_nt * event["cross"][index]
        + gain_per_nt * gain_per_nt * event["response_squared"][index]
    )
    squared_error = (corrected_squared - 2 * TRIAL_LOG_R * corrected_sum
                     + event["minutes"] * TRIAL_LOG_R * TRIAL_LOG_R)
    best_index = int(np.argmin(squared_error))
    rmse = math.sqrt(max(float(squared_error[best_index]), 0) / event["minutes"])
    return float(TRIAL_R[best_index]), rmse
