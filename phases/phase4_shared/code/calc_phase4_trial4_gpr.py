"""Fit the zero-mean GPR residual correction above the fixed Trial4 baseline."""

import warnings
from dataclasses import dataclass

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler


FEATURE_NAMES = (
    "h_tau_phase_nt",
    "h_24h_phase_nt",
    "sme_phase_nt",
    "symh_phase_nt",
    "altitude_phase_m",
)
RANDOM_STATE = 20261030
ALPHA = 1e-10


@dataclass(frozen=True)
class GprSettings:
    """Input: feature names, optimizer restarts. Output: immutable GPR fitting settings."""

    feature_names: tuple[str, ...] = FEATURE_NAMES
    optimizer_restarts: int = 5


DEFAULT_GPR_SETTINGS = GprSettings()


def fit_gpr(
    features: np.ndarray,
    residual: np.ndarray,
    settings: GprSettings = DEFAULT_GPR_SETTINGS,
) -> dict:
    """Input: [anchors x features], [log residual], settings. Output: fitted scaler and GPR."""
    feature_names = settings.feature_names
    if not feature_names or len(set(feature_names)) != len(feature_names):
        raise ValueError("Phase 4 feature names must be nonempty and unique.")
    if settings.optimizer_restarts < 0:
        raise ValueError("Phase 4 GPR optimizer restarts cannot be negative.")
    if features.ndim != 2 or features.shape[1] != len(feature_names):
        raise ValueError("Phase 4 feature matrix does not match its feature names.")
    if not np.isfinite(features).all() or not np.isfinite(residual).all():
        raise ValueError("Phase 4 features and residuals must be finite.")
    scaler = StandardScaler().fit(features)
    if np.any(scaler.scale_ <= 0):
        raise ValueError("Phase 4 has a zero-variance feature.")
    kernel = (
        ConstantKernel(1.0, (1e-3, 1e3))
        * RBF(np.ones(len(feature_names)), (1e-2, 1e3))
        + WhiteKernel(0.1, (1e-5, 1.0))
    )
    model = GaussianProcessRegressor(
        kernel=kernel,
        alpha=ALPHA,
        normalize_y=False,
        n_restarts_optimizer=settings.optimizer_restarts,
        random_state=RANDOM_STATE,
    )
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        model.fit(scaler.transform(features), residual)
    warnings_count = sum(
        isinstance(item.message, ConvergenceWarning) for item in emitted
    )
    return {"scaler": scaler, "model": model, "warnings_count": warnings_count}


def score(residual: np.ndarray, mean: np.ndarray, std: np.ndarray) -> dict:
    """Input: [Trial4 residual], [GPR mean], [GPR std]. Output: evaluation metrics."""
    corrected_error = residual - mean
    return {
        "trial4_rmse_log_density": float(np.sqrt(np.mean(residual * residual))),
        "trial4_mae_log_density": float(np.mean(np.abs(residual))),
        "gpr_rmse_log_density": float(np.sqrt(np.mean(corrected_error * corrected_error))),
        "gpr_mae_log_density": float(np.mean(np.abs(corrected_error))),
        "gpr_coverage_95": float(np.mean(np.abs(corrected_error) <= 1.96 * std)),
    }


def hyperparameters(
    model: GaussianProcessRegressor, feature_names: tuple[str, ...] = FEATURE_NAMES
) -> dict:
    """Input: fitted GPR, feature names. Output: ARD scales, variance, noise, and evidence."""
    kernel = model.kernel_
    if len(kernel.k1.k2.length_scale) != len(feature_names):
        raise ValueError("GPR ARD scale count does not match feature names.")
    output = {
        f"length_scale_{name}": float(value)
        for name, value in zip(feature_names, kernel.k1.k2.length_scale)
    }
    output.update({
        "signal_variance": float(kernel.k1.k1.constant_value),
        "noise_variance": float(kernel.k2.noise_level),
        "log_marginal_likelihood": float(model.log_marginal_likelihood_value_),
        "convergence_warning_count": 0,
    })
    return output
