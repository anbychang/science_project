"""Fit SME response gain at each trial time constant with R held fixed."""

import numpy as np


def sufficient_statistics(anomaly: np.ndarray, response: np.ndarray) -> dict:
    """Input: [log anomaly], [minute x tau response nT]. Output: fit sums."""
    if anomaly.ndim != 1 or response.shape != (len(anomaly), 41):
        raise ValueError("Expected one anomaly and 41 responses per minute")
    if not len(anomaly) or not np.isfinite(anomaly).all() or not np.isfinite(response).all():
        raise ValueError("Fit inputs must be nonempty and finite")
    return {
        "minutes": len(anomaly),
        "anomaly_squared": float(anomaly @ anomaly),
        "cross": response.T @ anomaly,
        "response_squared": np.sum(response * response, axis=0),
    }


def score_tau_grid(statistics: dict) -> list[tuple[float, float, float]]:
    """Input: {fit sums}. Output: [(tau h, gain 1/nT, RMSE log density), ...]."""
    cross = statistics["cross"]
    response_squared = statistics["response_squared"]
    if np.any(response_squared <= 0):
        raise ValueError("Cannot estimate gain for a zero SME response")
    gain = cross / response_squared
    error_squared = (statistics["anomaly_squared"]
                     - 2 * gain * cross + gain * gain * response_squared)
    rmse = np.sqrt(np.maximum(error_squared, 0) / statistics["minutes"])
    return [(index / 4, float(gain[index]), float(rmse[index]))
            for index in range(41)]
