"""Fit fold-local physical response and zero-mean GPR residuals."""

import math
import warnings

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning

from phases.phase4.code.load_phase4_inputs import FEATURE_NAMES


TAU_STEP_HOURS = 0.05
TAU_STEPS = 201
RANDOM_STATE = 20261028
ALPHA = 1e-10


def fit_physics(z: np.ndarray, h_grid: np.ndarray) -> dict:
    """Input: [train log anomaly], [train x 201 response nT]. Output: tau, G, RMSE."""
    cross = h_grid.T @ z
    response_squared = np.sum(h_grid * h_grid, axis=0)
    if np.any(response_squared <= 0):
        raise ValueError("Physical response grid contains a zero column.")
    gain = cross / response_squared
    squared_error = np.sum(z * z) - 2 * gain * cross + gain * gain * response_squared
    best = int(np.argmin(squared_error))
    return {"tau_index": best, "tau_hours": best * TAU_STEP_HOURS,
            "gain_per_nt": float(gain[best]),
            "train_rmse_log_density": math.sqrt(max(float(squared_error[best]), 0) / len(z))}


def make_features(h_tau: np.ndarray, fixed: np.ndarray) -> np.ndarray:
    """Input: [fold H_tau nT], [N x 3 fixed features]. Output: [N x 4 features]."""
    features = np.column_stack((h_tau, fixed))
    if features.shape[1] != len(FEATURE_NAMES) or not np.isfinite(features).all():
        raise ValueError("GPR feature matrix must contain four finite columns.")
    return features


def fit_gpr(train_features: np.ndarray, train_residual: np.ndarray) -> dict:
    """Input: [train x 4 features], [train log residual]. Output: scaler and GP."""
    scaler = StandardScaler().fit(train_features)
    if np.any(scaler.scale_ <= 0):
        raise ValueError("Standardized feature has zero scale.")
    kernel = (ConstantKernel(1.0, (1e-3, 1e3))
              * RBF(np.ones(len(FEATURE_NAMES)), (1e-2, 1e3))
              + WhiteKernel(0.1, (1e-5, 1)))
    model = GaussianProcessRegressor(
        kernel=kernel, alpha=ALPHA, normalize_y=False,
        n_restarts_optimizer=5, random_state=RANDOM_STATE,
    )
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        model.fit(scaler.transform(train_features), train_residual)
    convergence_warning_count = sum(
        isinstance(item.message, ConvergenceWarning) for item in emitted)
    return {"scaler": scaler, "model": model,
            "convergence_warning_count": convergence_warning_count}


def score(y_true: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> dict:
    """Input: [observed log residual], [GP mean], [GP std]. Output: error/coverage."""
    error = y_true - mu
    return {"rmse_log_density": float(np.sqrt(np.mean(error * error))),
            "mae_log_density": float(np.mean(np.abs(error))),
            "coverage_95": float(np.mean(np.abs(error) <= 1.96 * sigma))}


def hyperparameters(model: GaussianProcessRegressor) -> dict:
    """Input: fitted zero-mean GPR. Output: ARD scales, variances and evidence."""
    kernel = model.kernel_
    output = {f"length_scale_{name}": float(value)
              for name, value in zip(FEATURE_NAMES, kernel.k1.k2.length_scale)}
    output.update({"signal_variance": float(kernel.k1.k1.constant_value),
                   "noise_variance": float(kernel.k2.noise_level),
                   "log_marginal_likelihood": float(model.log_marginal_likelihood_value_)})
    return output
