"""Check fixed-R tau scoring against direct residuals."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from calc_m2_tau import score_tau_grid, sufficient_statistics


def test_tau_grid_matches_direct_least_squares() -> None:
    """Input: known anomaly and SME responses. Output: direct RMSE agreement."""
    response = np.tile(np.arange(1, 42, dtype=float), (3, 1))
    anomaly = np.array([1.0, 2.0, 3.0])
    scores = score_tau_grid(sufficient_statistics(anomaly, response))
    tau, gain, rmse = scores[0]
    assert tau == 0
    assert np.isclose(gain, 2)
    assert np.isclose(rmse, np.sqrt(2 / 3))
