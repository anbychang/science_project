"""Fit event offsets, event response times, and one shared SME gain."""

from dataclasses import dataclass
from typing import Callable

import numpy as np


TAU_STEP_HOURS = 0.1
TAU_MIN_HOURS = 0.0
TAU_MAX_HOURS = 15.0
INITIAL_TAU_HOURS = 2.5
BASELINE_TAU_HOURS = 4.65
MAX_R_VALUE = 2.0
MAX_OUTER_ITERATIONS = 20
MAX_GAIN_ITERATIONS = 100
GAIN_TOLERANCE = 1e-12
TAU_TIE_TOLERANCE = 1e-12
BASELINE_TAU_INDEX = -1


@dataclass(frozen=True)
class EventFitData:
    """Input: one event's density anomaly and phase response arrays. Output: fit input."""

    storm_id: str
    log_density_anomaly: np.ndarray
    r_rq: float
    h_baseline_nt: np.ndarray
    h_tau_grid_nt: np.ndarray


@dataclass(frozen=True)
class FitState:
    """Input: event offsets, tau grid indices, and gain. Output: one model state."""

    log_r_by_event: np.ndarray
    tau_index_by_event: np.ndarray
    gain_per_nt: float


@dataclass(frozen=True)
class FitResult:
    """Input: final state and iteration records. Output: model fit result."""

    state: FitState
    iteration_rows: list[dict]
    converged: bool


def tau_grid_hours() -> np.ndarray:
    """Input: fixed tau bounds. Output: [tau hours] at 0.1-hour spacing."""
    step_count = round((TAU_MAX_HOURS - TAU_MIN_HOURS) / TAU_STEP_HOURS)
    return np.linspace(TAU_MIN_HOURS, TAU_MAX_HOURS, step_count + 1)


def initial_state(events: list[EventFitData], gain_per_nt: float) -> FitState:
    """Input: [event fit data], positive initial gain. Output: initial joint state."""
    if gain_per_nt <= 0:
        raise ValueError("Initial gain must be positive.")
    grid = tau_grid_hours()
    tau_index = int(np.flatnonzero(np.isclose(grid, INITIAL_TAU_HOURS))[0])
    return FitState(
        log_r_by_event=np.log([event.r_rq for event in events]),
        tau_index_by_event=np.full(len(events), tau_index, dtype=np.int16),
        gain_per_nt=gain_per_nt,
    )


def event_response(event: EventFitData, tau_index: int) -> np.ndarray:
    """Input: event fit data and tau-grid index. Output: [phase H in nT]."""
    if tau_index == BASELINE_TAU_INDEX:
        return event.h_baseline_nt
    return event.h_tau_grid_nt[tau_index]


def update_offsets(events: list[EventFitData], state: FitState) -> FitState:
    """Input: [event fit data], fit state. Output: state with clipped log R offsets."""
    upper_log_r = np.log(np.nextafter(MAX_R_VALUE, 0.0))
    offsets = np.array([
        min(
            float(np.mean(event.log_density_anomaly
                          - state.gain_per_nt * event_response(event, tau_index))),
            upper_log_r,
        )
        for event, tau_index in zip(events, state.tau_index_by_event, strict=True)
    ])
    return FitState(offsets, state.tau_index_by_event, state.gain_per_nt)


def update_gain(events: list[EventFitData], state: FitState) -> FitState:
    """Input: [event fit data], fit state. Output: state with shared positive gain."""
    numerator = 0.0
    denominator = 0.0
    for event, log_r, tau_index in zip(
        events, state.log_r_by_event, state.tau_index_by_event, strict=True
    ):
        response = event_response(event, tau_index)
        residual_target = event.log_density_anomaly - log_r
        numerator += float(np.mean(response * residual_target))
        denominator += float(np.mean(response * response))
    gain = numerator / denominator
    if gain <= 0:
        raise ValueError("Joint fit requires nonpositive G.")
    return FitState(state.log_r_by_event, state.tau_index_by_event, gain)


def update_offsets_and_gain(events: list[EventFitData], state: FitState) -> FitState:
    """Input: [event fit data], fit state. Output: converged R and G at fixed tau."""
    current = state
    for _ in range(MAX_GAIN_ITERATIONS):
        updated = update_gain(events, update_offsets(events, current))
        if np.isclose(updated.gain_per_nt, current.gain_per_nt,
                      rtol=GAIN_TOLERANCE, atol=0):
            return updated
        current = updated
    raise RuntimeError("R and G update did not converge.")


def update_gain_at_fixed_r(events: list[EventFitData], state: FitState) -> FitState:
    """Input: [event fit data], fit state. Output: shared positive gain at fixed R."""
    return update_gain(events, state)


def select_tau_indices(events: list[EventFitData], state: FitState) -> FitState:
    """Input: [event fit data], fixed R and G state. Output: state with grid-best tau."""
    selected = state.tau_index_by_event.copy()
    for event_index, event in enumerate(events):
        residual = (event.log_density_anomaly - state.log_r_by_event[event_index]
                    - state.gain_per_nt * event.h_tau_grid_nt)
        loss_by_tau = np.mean(residual * residual, axis=1)
        best_loss = float(np.min(loss_by_tau))
        previous_index = selected[event_index]
        if loss_by_tau[previous_index] <= best_loss + TAU_TIE_TOLERANCE:
            continue
        selected[event_index] = int(np.flatnonzero(
            loss_by_tau <= best_loss + TAU_TIE_TOLERANCE
        )[0])
    return FitState(state.log_r_by_event, selected, state.gain_per_nt)


def fit_variable_tau(events: list[EventFitData], state: FitState,
                     parameter_update: Callable[[list[EventFitData], FitState], FitState]
                     ) -> FitResult:
    """Input: [event fit data], state, R/G updater. Output: variable-tau fit result."""
    current = state
    iteration_rows = []
    for iteration in range(1, MAX_OUTER_ITERATIONS + 1):
        fitted = parameter_update(events, current)
        updated = select_tau_indices(events, fitted)
        changed = int(np.count_nonzero(
            updated.tau_index_by_event != current.tau_index_by_event
        ))
        iteration_rows.append({
            "iteration": iteration,
            "gain_per_nt": fitted.gain_per_nt,
            "changed_tau_count": changed,
        })
        if changed == 0:
            return FitResult(fitted, iteration_rows, True)
        current = updated
    return FitResult(current, iteration_rows, False)


def mean_squared_error(target: np.ndarray, prediction: np.ndarray) -> float:
    """Input: [target log density], [predicted log density]. Output: mean square."""
    residual = target - prediction
    return float(np.mean(residual * residual))


def model_score(events: list[EventFitData], state: FitState) -> dict:
    """Input: [event fit data], state. Output: equal-weight score."""
    event_losses = [
        mean_squared_error(
            event.log_density_anomaly,
            log_r + state.gain_per_nt * event_response(event, tau_index),
        )
        for event, log_r, tau_index in zip(
            events, state.log_r_by_event, state.tau_index_by_event, strict=True
        )
    ]
    return {
        "event_equal_mse_log_density": float(np.mean(event_losses)),
        "event_equal_rmse_log_density": float(np.sqrt(np.mean(event_losses))),
    }
