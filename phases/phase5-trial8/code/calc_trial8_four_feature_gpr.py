"""Estimate the next orbit correction from four available density inputs."""

import math
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler

from calc_trial8_next_orbit_gpr import MIN_TRAINING_PAIRS


def feature_vector(current: dict, previous: dict) -> list[float]:
    """Input: {current D-model}, {previous D-model, L2, residual}. Output: [4 logs]."""
    return [math.log(current["rho_trial4_phase_kg_m3"]),
            math.log(previous["rho_trial4_phase_kg_m3"]),
            math.log(previous["rho_l2_phase_kg_m3"]),
            previous["residual_log_density"]]


def predict_next_residual(completed: list[dict], current: dict) -> tuple[float, float]:
    """Input: [completed consecutive orbit rows], {current D-model}. Output: (mean, std)."""
    if len(completed) < MIN_TRAINING_PAIRS + 1:
        raise ValueError("At least five completed orbit transitions are required.")
    features = np.asarray([feature_vector(now, before)
                           for before, now in zip(completed, completed[1:])])
    changes = np.asarray([now["residual_log_density"] - before["residual_log_density"]
                          for before, now in zip(completed, completed[1:])])
    if not np.isfinite(features).all() or not np.isfinite(changes).all():
        raise ValueError("Training values must be finite.")
    scaler = StandardScaler().fit(features)
    kernel = (
        ConstantKernel(1.0, (1e-2, 1e2))
        * RBF(np.ones(4), (1e-1, 1e1))
        + WhiteKernel(0.1, (1e-3, 1.0))
    )
    model = GaussianProcessRegressor(
        kernel=kernel, alpha=1e-8, normalize_y=True, n_restarts_optimizer=0
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(scaler.transform(features), changes)
    query = scaler.transform([feature_vector(current, completed[-1])])
    estimated_change, uncertainty = model.predict(query, return_std=True)
    return (float(completed[-1]["residual_log_density"] + estimated_change[0]),
            float(uncertainty[0]))


def predict_event(rows: list[dict]) -> list[dict]:
    """Input: [time-ordered orbit rows]. Output: [eligible past-only prediction rows]."""
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
            estimate, uncertainty = predict_next_residual(completed, row)
            predictions.append({**row,
                                "previous_time_us": completed[-1]["time_us"],
                                "previous_trial4_density_kg_m3":
                                    completed[-1]["rho_trial4_phase_kg_m3"],
                                "previous_l2_density_kg_m3":
                                    completed[-1]["rho_l2_phase_kg_m3"],
                                "previous_log_residual": completed[-1]["residual_log_density"],
                                "gp_log_residual_mean": estimate,
                                "gp_log_residual_std": uncertainty,
                                "training_pair_count": len(completed) - 1})
        completed.append(row)
        previous_grid = grid
        previous_time = row["time_us"]
    return predictions
