"""Estimate each minute's residual from previous observed minutes only."""

from collections import deque

import numpy as np


def past_mean(residual: np.ndarray, history_minutes: int) -> np.ndarray:
    """Input: [one-minute residual or NaN], history length. Output: [past means]."""
    if history_minutes < 1:
        raise ValueError("Moving-average history must be positive.")
    prediction = np.full(len(residual), np.nan)
    history: deque[float] = deque(maxlen=history_minutes)
    for index, value in enumerate(residual):
        if not np.isfinite(value):
            history.clear()
            continue
        if len(history) == history_minutes:
            prediction[index] = sum(history) / history_minutes
        history.append(float(value))
    return prediction
