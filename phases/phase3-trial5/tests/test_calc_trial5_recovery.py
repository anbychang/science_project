"""Check Trial5 recovery-shape and constrained-amplitude calculations."""

import math
import sys
from pathlib import Path

import numpy as np


CODE_DIRECTORY = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIRECTORY))

from calc_trial5_recovery import (
    RecoveryEvent,
    fit_nonnegative_amplitude,
    fit_recovery_grid,
    recovery_shape,
)


def test_recovery_shape_is_zero_before_t0() -> None:
    """Input: times before and after t0. Output: recovery starts only at t0."""
    shape = recovery_shape(np.array([-1.0, 0.0, 2.0]), 2.0)
    assert np.allclose(shape, [0.0, 1.0, math.exp(-1.0)])


def test_recovery_amplitude_is_clipped_at_zero() -> None:
    """Input: uniformly negative residual. Output: no negative recovery amplitude."""
    event = RecoveryEvent("S", np.array([0.0, 1.0]), np.array([-1.0, -1.0]))
    assert fit_nonnegative_amplitude(event, 1.0) == 0.0


def test_recovery_grid_finds_planted_time_scale() -> None:
    """Input: exact 2-hour exponential residual. Output: grid minimum at 2 hours."""
    hours = np.arange(-1.0, 12.1, 0.1)
    residual = 0.4 * recovery_shape(hours, 2.0)
    event = RecoveryEvent("S", hours, residual)
    best = min(fit_recovery_grid([event]), key=lambda fit: fit.event_equal_mse_log_density)
    assert best.recovery_time_hours == 2.0
