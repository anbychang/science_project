"""Predict the next orbit's log-density residual from completed orbits."""

import math
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler


MIN_TRAINING_PAIRS = 5


def predict_next_residual(completed_residuals: np.ndarray) -> tuple[float, float]:
    """Input: [completed consecutive orbit log residuals]. Output: (next mean, std)."""
    if len(completed_residuals) < MIN_TRAINING_PAIRS + 1:
        raise ValueError("At least five completed orbit transitions are required.")
    if not np.isfinite(completed_residuals).all():
        raise ValueError("Completed orbit residuals must be finite.")

    previous = completed_residuals[:-1].reshape(-1, 1)
    change = np.diff(completed_residuals)
    scaler = StandardScaler().fit(previous)
    kernel = (
        ConstantKernel(1.0, (1e-2, 1e2))
        * RBF(1.0, (1e-1, 1e1))
        + WhiteKernel(0.1, (1e-3, 1.0))
    )
    model = GaussianProcessRegressor(
        kernel=kernel, alpha=1e-8, normalize_y=True, n_restarts_optimizer=0
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(scaler.transform(previous), change)
    latest = scaler.transform(completed_residuals[-1:].reshape(-1, 1))
    estimated_change, uncertainty = model.predict(latest, return_std=True)
    return (float(completed_residuals[-1] + estimated_change[0]),
            float(uncertainty[0]))


def predict_event(rows: list[dict]) -> list[dict]:
    """Input: [{time_us, u_rel_rad, residual_log_density, ...}]. Output: [scored orbit rows]."""
    predictions = []
    completed = []
    previous_grid = None
    previous_time = None
    for row in rows:
        grid = round(row["u_rel_rad"] / (2 * math.pi))
        if previous_grid is not None and (grid != previous_grid + 1
                                          or row["time_us"] <= previous_time):
            completed.clear()
        if previous_grid is not None and grid <= previous_grid:
            raise ValueError("Orbit anchors must have increasing phase grids.")
        if len(completed) >= MIN_TRAINING_PAIRS + 1:
            estimate, uncertainty = predict_next_residual(np.asarray(completed))
            predictions.append({**row,
                                "previous_log_residual": completed[-1],
                                "gp_log_residual_mean": estimate,
                                "gp_log_residual_std": uncertainty,
                                "training_pair_count": len(completed) - 1})
        completed.append(row["residual_log_density"])
        previous_grid = grid
        previous_time = row["time_us"]
    return predictions
