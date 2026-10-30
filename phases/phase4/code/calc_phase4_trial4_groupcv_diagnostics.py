"""Calculate geometry diagnostics for the fixed Phase 4 Trial2 folds."""

import numpy as np


def nearest_distances(
    training_features: np.ndarray, test_features: np.ndarray
) -> np.ndarray:
    """Input: [train anchors x features], [test anchors x features]. Output: [test nearest distances]."""
    if training_features.ndim != 2 or test_features.ndim != 2:
        raise ValueError("Nearest-distance inputs must be two-dimensional.")
    if training_features.shape[1] != test_features.shape[1]:
        raise ValueError("Nearest-distance inputs must have equal feature counts.")
    squared_distance = np.sum(
        (test_features[:, np.newaxis, :] - training_features[np.newaxis, :, :]) ** 2,
        axis=2,
    )
    return np.sqrt(np.min(squared_distance, axis=1))


def scaled_features(
    training_features: np.ndarray, test_features: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Input: [train anchors x features], [test anchors x features]. Output: standardized feature matrices."""
    mean = training_features.mean(axis=0)
    scale = training_features.std(axis=0)
    if np.any(scale <= 0):
        raise ValueError("Diagnostic training features contain a zero-variance column.")
    return (training_features - mean) / scale, (test_features - mean) / scale


def feature_shift(
    training_values: np.ndarray, test_values: np.ndarray
) -> dict[str, float]:
    """Input: [train feature], [test feature]. Output: range and standardized shift metrics."""
    training_mean = float(training_values.mean())
    training_std = float(training_values.std())
    if training_std <= 0:
        raise ValueError("Diagnostic training feature has zero variance.")
    return {
        "train_mean": training_mean,
        "train_std": training_std,
        "test_mean": float(test_values.mean()),
        "test_std": float(test_values.std()),
        "test_mean_shift_sd": float((test_values.mean() - training_mean) / training_std),
        "test_outside_train_range_fraction": float(np.mean(
            (test_values < training_values.min()) | (test_values > training_values.max())
        )),
    }
