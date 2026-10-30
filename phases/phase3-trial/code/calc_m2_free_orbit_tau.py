"""Fit a separate time constant for each Phase 2 orbit segment."""

import numpy as np

from phases.phase3.code.calc_h_tau import phase_weighted_mean
from calc_m2_orbit_tau import event_orbit_response


TAU_GRID_HOURS = tuple(index / 2 for index in range(21))
INITIAL_TAU_HOURS = 3.5
MAX_SWEEPS = 20
SSE_TOLERANCE = 1e-10


def event_squared_error(event: dict, tau_by_orbit: np.ndarray,
                        gain_per_nt: float) -> tuple[float, np.ndarray]:
    """Input: event arrays, [orbit tau h], gain 1/nT. Output: SSE, [phase H]."""
    response = event_orbit_response(
        event["sme_excess"], event["orbit_edges"], tau_by_orbit,
        event["initial_h"],
    )
    phase_response = phase_weighted_mean(
        response, event["pairs"], event["support"]
    )[event["support"]["valid"]]
    residual = event["anomaly"] - gain_per_nt * phase_response
    return float(residual @ residual), phase_response


def fit_event_orbit_tau(event: dict, gain_per_nt: float) -> dict:
    """Input: one event and fixed gain. Output: orbit tau, SSE, sweep history."""
    orbit_count = len(event["orbit_edges"]) - 1
    initial_tau_hours = event.get("initial_tau_hours", INITIAL_TAU_HOURS)
    tau_grid_hours = sorted(set(TAU_GRID_HOURS) | {initial_tau_hours})
    tau_by_orbit = np.full(orbit_count, initial_tau_hours)
    initial_sse, _ = event_squared_error(event, tau_by_orbit, gain_per_nt)
    current_sse = initial_sse
    sweeps = []
    for sweep in range(1, MAX_SWEEPS + 1):
        changed_count = 0
        for orbit in range(orbit_count):
            original_tau = tau_by_orbit[orbit]
            best_tau = original_tau
            best_sse = current_sse
            for trial_tau in tau_grid_hours:
                if trial_tau == original_tau:
                    continue
                tau_by_orbit[orbit] = trial_tau
                trial_sse, _ = event_squared_error(event, tau_by_orbit, gain_per_nt)
                if trial_sse < best_sse - SSE_TOLERANCE:
                    best_tau, best_sse = trial_tau, trial_sse
            tau_by_orbit[orbit] = best_tau
            current_sse = best_sse
            changed_count += int(best_tau != original_tau)
        sweeps.append((sweep, changed_count, current_sse))
        if changed_count == 0:
            break
    final_sse, phase_response = event_squared_error(event, tau_by_orbit, gain_per_nt)
    if abs(final_sse - current_sse) > 1e-7 or final_sse > initial_sse + 1e-7:
        raise ValueError("Orbit-tau fit did not preserve a non-increasing error")
    return {"tau_by_orbit": tau_by_orbit, "initial_sse": initial_sse,
            "final_sse": final_sse, "sweeps": sweeps,
            "phase_response": phase_response,
            "converged": sweeps[-1][1] == 0}
