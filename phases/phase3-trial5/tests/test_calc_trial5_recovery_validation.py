"""Check Trial5 leave-one-event recovery validation calculations."""

import sys
from pathlib import Path

import numpy as np


CODE_DIRECTORY = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIRECTORY))

from calc_trial5_recovery import (
    RecoveryEvent,
    recovery_grid_hours,
    recovery_shape,
    score_recovery_fit,
)
from calc_trial5_recovery_validation import (
    event_loss_grid,
    fit_initial_amplitude,
    mean_tail_square,
)


def test_initial_amplitude_ignores_tail_residual_values() -> None:
    """Input: equal first-day data and distinct tail. Output: equal fitted amplitudes."""
    hours = np.array([0.0, 12.0, 24.0, 48.0])
    first = RecoveryEvent("first", hours, np.array([0.4, 0.2, 0.0, 0.0]))
    second = RecoveryEvent("second", hours, np.array([0.4, 0.2, 99.0, -99.0]))
    assert fit_initial_amplitude(first, 12.0) == fit_initial_amplitude(second, 12.0)


def test_tail_score_uses_no_pre_24_hour_samples() -> None:
    """Input: residual only after 24 hours. Output: tail MSE uses the late residual."""
    hours = np.array([0.0, 12.0, 24.0, 48.0])
    event = RecoveryEvent("S", hours, np.array([99.0, -99.0, 0.5, 0.0]))
    assert mean_tail_square(event, 12.0, 0.0) == 0.125


def test_tail_score_rewards_matching_recovery_shape() -> None:
    """Input: exponential tail residual. Output: matching amplitude lowers tail MSE."""
    hours = np.array([0.0, 24.0, 36.0, 48.0])
    residual = 0.4 * recovery_shape(hours, 12.0)
    event = RecoveryEvent("S", hours, residual)
    assert mean_tail_square(event, 12.0, 0.4) < mean_tail_square(event, 12.0, 0.0)


def test_vectorized_event_loss_grid_matches_direct_score() -> None:
    """Input: one residual event. Output: vectorized and direct grid losses agree."""
    event = RecoveryEvent("S", np.array([-1.0, 0.0, 1.0]), np.array([0.0, 0.3, 0.1]))
    direct = [score_recovery_fit([event], float(time)).event_equal_mse_log_density
              for time in recovery_grid_hours()]
    assert np.allclose(event_loss_grid(event), direct)
