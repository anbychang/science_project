"""Define the small nested-CV GPR candidate set for Phase 4 Trial3."""

from dataclasses import dataclass
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler


RANDOM_STATE = 20261030
ALPHA = 1e-10
SELECTION_RESTARTS = 0
FINAL_RESTARTS = 5
GEOMAGNETIC_FEATURE_INDICES = (0, 1, 2, 3)


@dataclass(frozen=True)
class Candidate:
    """Input: candidate name, feature indices, kernel, restart count. Output: immutable model specification."""

    name: str
    feature_indices: tuple[int, ...]
    kernel_name: str
    optimizer_restarts: int


SELECTION_CANDIDATES = (
    Candidate("geomagnetic_rbf", GEOMAGNETIC_FEATURE_INDICES, "rbf", SELECTION_RESTARTS),
    Candidate("geomagnetic_matern32", GEOMAGNETIC_FEATURE_INDICES, "matern32", SELECTION_RESTARTS),
)


def candidate_features(features: np.ndarray, candidate: Candidate) -> np.ndarray:
    """Input: [anchors x source features], candidate. Output: [anchors x candidate features]."""
    if features.ndim != 2 or features.shape[1] <= max(candidate.feature_indices):
        raise ValueError("Trial3 source features do not satisfy the candidate specification.")
    return features[:, candidate.feature_indices]


def candidate_kernel(candidate: Candidate):
    """Input: candidate specification. Output: unfitted ARD signal-plus-noise kernel."""
    feature_count = len(candidate.feature_indices)
    if candidate.kernel_name == "rbf":
        correlation = RBF(np.ones(feature_count), (1e-2, 1e3))
    elif candidate.kernel_name == "matern32":
        correlation = Matern(np.ones(feature_count), (1e-2, 1e3), nu=1.5)
    else:
        raise ValueError(f"Unsupported Trial3 kernel: {candidate.kernel_name}")
    return ConstantKernel(1.0, (1e-3, 1e3)) * correlation + WhiteKernel(0.1, (1e-5, 1.0))


def fit_candidate(features: np.ndarray, residual: np.ndarray, candidate: Candidate) -> dict:
    """Input: [anchors x five features], [residual], candidate. Output: fitted scaler and GPR."""
    selected = candidate_features(features, candidate)
    if not np.isfinite(selected).all() or not np.isfinite(residual).all():
        raise ValueError("Trial3 features and residuals must be finite.")
    scaler = StandardScaler().fit(selected)
    if np.any(scaler.scale_ <= 0):
        raise ValueError("Trial3 has a zero-variance candidate feature.")
    model = GaussianProcessRegressor(
        kernel=candidate_kernel(candidate),
        alpha=ALPHA,
        normalize_y=False,
        n_restarts_optimizer=candidate.optimizer_restarts,
        random_state=RANDOM_STATE,
    )
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        model.fit(scaler.transform(selected), residual)
    return {
        "candidate": candidate,
        "scaler": scaler,
        "model": model,
        "warnings_count": sum(isinstance(item.message, ConvergenceWarning) for item in emitted),
    }


def predict_candidate(fitted: dict, features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Input: fitted Trial3 candidate, [anchors x five features]. Output: [mean], [standard deviation]."""
    candidate = fitted["candidate"]
    selected = candidate_features(features, candidate)
    return fitted["model"].predict(fitted["scaler"].transform(selected), return_std=True)


def select_candidate(metrics: list[dict]) -> str:
    """Input: [{candidate_name, inner_rmse_log_density}]. Output: lowest-RMSE candidate name."""
    if not metrics:
        raise ValueError("Trial3 requires at least one candidate metric.")
    return min(metrics, key=lambda row: row["inner_rmse_log_density"])["candidate_name"]
