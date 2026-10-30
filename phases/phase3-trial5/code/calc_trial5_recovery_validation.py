"""Validate recovery time and amplitude without using the evaluated event tail."""

from dataclasses import dataclass

import numpy as np

from calc_trial5_recovery import RecoveryEvent, recovery_grid_hours, recovery_shape


AMPLITUDE_FIT_END_HOURS = 24.0


@dataclass(frozen=True)
class ValidationScore:
    """Input: held-out event and selected recovery time. Output: tail-error comparison."""

    storm_id: str
    selected_recovery_time_hours: float
    nonnegative_amplitude: float
    signed_amplitude: float
    baseline_tail_mse_log_density: float
    nonnegative_tail_mse_log_density: float
    signed_tail_mse_log_density: float


@dataclass(frozen=True)
class RecoveryValidationPlan:
    """Input: selected recovery time and fit end. Output: one validation split definition."""

    recovery_time_hours: float
    fit_end_hours: float


def event_loss_grid(event: RecoveryEvent) -> np.ndarray:
    """Input: one event residual series. Output: MSE at every nonnegative-amplitude grid point."""
    grid = recovery_grid_hours()
    post_t0_hours = np.maximum(event.hours_from_t0, 0.0)
    shapes = np.exp(-post_t0_hours[None, :] / grid[:, None])
    shapes[:, event.hours_from_t0 < 0] = 0.0
    numerator = shapes @ event.trial4_residual_log_density
    denominator = np.sum(shapes * shapes, axis=1)
    amplitudes = np.maximum(numerator / denominator, 0.0)
    residual_sum_squares = float(
        event.trial4_residual_log_density @ event.trial4_residual_log_density
    )
    losses = (residual_sum_squares - 2 * amplitudes * numerator
              + amplitudes * amplitudes * denominator)
    return losses / len(event.trial4_residual_log_density)


def fit_window_mask(event: RecoveryEvent, fit_end_hours: float) -> np.ndarray:
    """Input: event and positive fit end. Output: post-t0 amplitude-fit sample mask."""
    if fit_end_hours <= 0:
        raise ValueError("Recovery fit end must be positive.")
    return (event.hours_from_t0 >= 0) & (event.hours_from_t0 < fit_end_hours)


def tail_window_mask(event: RecoveryEvent, fit_end_hours: float) -> np.ndarray:
    """Input: event and positive fit end. Output: independent tail-evaluation sample mask."""
    if fit_end_hours <= 0:
        raise ValueError("Recovery fit end must be positive.")
    return event.hours_from_t0 >= fit_end_hours


def fit_nonnegative_amplitude_before(
        event: RecoveryEvent, plan: RecoveryValidationPlan
) -> float:
    """Input: event, recovery time, fit end. Output: nonnegative amplitude before fit end."""
    mask = fit_window_mask(event, plan.fit_end_hours)
    shape = recovery_shape(event.hours_from_t0[mask], plan.recovery_time_hours)
    denominator = float(shape @ shape)
    if denominator == 0:
        raise ValueError(f"No initial recovery samples: {event.storm_id}")
    amplitude = float(shape @ event.trial4_residual_log_density[mask]) / denominator
    return max(amplitude, 0.0)


def fit_signed_amplitude_before(event: RecoveryEvent, plan: RecoveryValidationPlan) -> float:
    """Input: event, recovery time, fit end. Output: unrestricted diagnostic amplitude."""
    mask = fit_window_mask(event, plan.fit_end_hours)
    shape = recovery_shape(event.hours_from_t0[mask], plan.recovery_time_hours)
    denominator = float(shape @ shape)
    if denominator == 0:
        raise ValueError(f"No initial recovery samples: {event.storm_id}")
    return float(shape @ event.trial4_residual_log_density[mask]) / denominator


def mean_tail_square_after(
        event: RecoveryEvent, plan: RecoveryValidationPlan, amplitude: float
) -> float:
    """Input: event, recovery time, amplitude, fit end. Output: tail MSE after fit end."""
    mask = tail_window_mask(event, plan.fit_end_hours)
    if not np.any(mask):
        raise ValueError(f"No recovery-tail samples: {event.storm_id}")
    residual = event.trial4_residual_log_density[mask] - amplitude * recovery_shape(
        event.hours_from_t0[mask], plan.recovery_time_hours
    )
    return float(np.mean(residual * residual))


def fit_initial_amplitude(event: RecoveryEvent, recovery_time_hours: float) -> float:
    """Input: event and selected time. Output: nonnegative amplitude from first 24 hours."""
    return fit_nonnegative_amplitude_before(event, RecoveryValidationPlan(
        recovery_time_hours, AMPLITUDE_FIT_END_HOURS
    ))


def fit_signed_initial_amplitude(event: RecoveryEvent, recovery_time_hours: float) -> float:
    """Input: event and selected time. Output: unrestricted diagnostic amplitude from first 24 hours."""
    return fit_signed_amplitude_before(event, RecoveryValidationPlan(
        recovery_time_hours, AMPLITUDE_FIT_END_HOURS
    ))


def mean_tail_square(event: RecoveryEvent, recovery_time_hours: float, amplitude: float) -> float:
    """Input: event, recovery time, amplitude. Output: MSE on post-24-hour tail only."""
    return mean_tail_square_after(event, RecoveryValidationPlan(
        recovery_time_hours, AMPLITUDE_FIT_END_HOURS
    ), amplitude)


def validate_leave_one_event_out(events: list[RecoveryEvent]) -> list[ValidationScore]:
    """Input: [Trial4 residual events]. Output: one independent tail score per event."""
    if len({event.storm_id for event in events}) != len(events):
        raise ValueError("Recovery validation requires unique storm IDs.")
    losses_by_event = np.array([event_loss_grid(event) for event in events])
    total_loss = np.sum(losses_by_event, axis=0)
    grid = recovery_grid_hours()
    scores = []
    for event_index, event in enumerate(events):
        selected_index = int(np.argmin(
            (total_loss - losses_by_event[event_index]) / (len(events) - 1)
        ))
        selected_time = float(grid[selected_index])
        nonnegative_amplitude = fit_initial_amplitude(event, selected_time)
        signed_amplitude = fit_signed_initial_amplitude(event, selected_time)
        baseline_tail_mse = mean_tail_square(event, selected_time, 0.0)
        nonnegative_tail_mse = mean_tail_square(
            event, selected_time, nonnegative_amplitude
        )
        signed_tail_mse = mean_tail_square(event, selected_time, signed_amplitude)
        scores.append(ValidationScore(
            storm_id=event.storm_id,
            selected_recovery_time_hours=selected_time,
            nonnegative_amplitude=nonnegative_amplitude,
            signed_amplitude=signed_amplitude,
            baseline_tail_mse_log_density=baseline_tail_mse,
            nonnegative_tail_mse_log_density=nonnegative_tail_mse,
            signed_tail_mse_log_density=signed_tail_mse,
        ))
    return scores
