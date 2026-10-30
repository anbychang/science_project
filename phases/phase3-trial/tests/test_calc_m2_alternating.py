"""Check the alternating trial's sufficient-statistic calculations."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from calc_m2_alternating import choose_r_trial, common_tau_grid, event_sums


def test_trial_r_update_uses_corrected_residual() -> None:
    """Input: exact corrected ratio R=1.20. Output: chosen trial R=1.20."""
    response = np.ones((3, 41)) * 10
    residual = np.log(1.20) + 0.02 * response[:, 0]
    event = event_sums(residual, response)
    chosen_r, rmse = choose_r_trial(event, 0, 0.02)
    assert chosen_r == 1.2
    assert rmse < 1e-7


def test_common_grid_matches_direct_gain() -> None:
    """Input: two events with fixed R. Output: direct common G at tau zero."""
    response = np.tile(np.arange(1, 42, dtype=float), (2, 1))
    events = {
        "a": event_sums(np.array([1.0, 2.0]), response),
        "b": event_sums(np.array([3.0, 4.0]), response),
    }
    tau, gain, _ = common_tau_grid(events, {"a": 1.0, "b": 1.0})[0]
    assert tau == 0
    assert np.isclose(gain, 2.5)
