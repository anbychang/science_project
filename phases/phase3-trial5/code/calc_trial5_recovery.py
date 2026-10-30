"""Fit a post-t0 exponential recovery term to fixed Trial4 residuals."""

from dataclasses import dataclass

import numpy as np


RECOVERY_MIN_HOURS = 0.1
RECOVERY_MAX_HOURS = 96.0
RECOVERY_STEP_HOURS = 0.1


@dataclass(frozen=True)
class RecoveryEvent:
    """Input: one event's relative times and Trial4 residuals. Output: fit input."""

    storm_id: str
    hours_from_t0: np.ndarray
    trial4_residual_log_density: np.ndarray


@dataclass(frozen=True)
class RecoveryFit:
    """Input: one recovery time and fitted amplitudes. Output: scored fit state."""

    recovery_time_hours: float
    amplitude_by_storm: dict[str, float]
    event_equal_mse_log_density: float


def recovery_grid_hours() -> np.ndarray:
    """Input: fixed recovery bounds. Output: [recovery time hours] at 0.1-hour spacing."""
    step_count = round((RECOVERY_MAX_HOURS - RECOVERY_MIN_HOURS) / RECOVERY_STEP_HOURS)
    return np.linspace(RECOVERY_MIN_HOURS, RECOVERY_MAX_HOURS, step_count + 1)


def recovery_shape(hours_from_t0: np.ndarray, recovery_time_hours: float) -> np.ndarray:
    """Input: [hours from t0], positive recovery time. Output: post-t0 decay shape."""
    if recovery_time_hours <= 0:
        raise ValueError("Recovery time must be positive.")
    shape = np.zeros_like(hours_from_t0, dtype=float)
    post_t0 = hours_from_t0 >= 0
    shape[post_t0] = np.exp(-hours_from_t0[post_t0] / recovery_time_hours)
    return shape


def fit_nonnegative_amplitude(event: RecoveryEvent, recovery_time_hours: float) -> float:
    """Input: one event and recovery time. Output: nonnegative recovery amplitude."""
    shape = recovery_shape(event.hours_from_t0, recovery_time_hours)
    denominator = float(shape @ shape)
    if denominator == 0:
        raise ValueError(f"Recovery shape has no post-t0 support: {event.storm_id}")
    amplitude = float(shape @ event.trial4_residual_log_density) / denominator
    return max(amplitude, 0.0)


def score_recovery_fit(events: list[RecoveryEvent], recovery_time_hours: float) -> RecoveryFit:
    """Input: [event residuals], shared recovery time. Output: amplitudes and equal score."""
    amplitude_by_storm = {}
    event_losses = []
    for event in events:
        amplitude = fit_nonnegative_amplitude(event, recovery_time_hours)
        residual = event.trial4_residual_log_density - amplitude * recovery_shape(
            event.hours_from_t0, recovery_time_hours
        )
        amplitude_by_storm[event.storm_id] = amplitude
        event_losses.append(float(np.mean(residual * residual)))
    if len(amplitude_by_storm) != len(events):
        raise ValueError("Recovery fit has duplicate storm IDs.")
    return RecoveryFit(
        recovery_time_hours=recovery_time_hours,
        amplitude_by_storm=amplitude_by_storm,
        event_equal_mse_log_density=float(np.mean(event_losses)),
    )


def fit_recovery_grid(events: list[RecoveryEvent]) -> list[RecoveryFit]:
    """Input: [event residuals]. Output: one scored fit per recovery-time grid point."""
    if not events:
        raise ValueError("Recovery fit requires at least one event.")
    return [score_recovery_fit(events, float(recovery_time_hours))
            for recovery_time_hours in recovery_grid_hours()]
