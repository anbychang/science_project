"""Filter minute SME and average its response over centered orbital phase."""

import math

import numpy as np
from scipy.signal import lfilter


def filtered_sme(sme_nt: np.ndarray, tau_hours: float) -> np.ndarray:
    """Input: [1-minute SME in nT], tau hours. Output: filtered SME in nT."""
    if tau_hours < 0:
        raise ValueError("tau_hours must be nonnegative.")
    if tau_hours == 0:
        return sme_nt.copy()
    alpha = math.exp(-1 / (60 * tau_hours))
    values, _ = lfilter([1 - alpha], [1, -alpha], sme_nt,
                        zi=[alpha * float(sme_nt[0])])
    return values


def phase_support(u_rad: np.ndarray, pair_count: np.ndarray) -> dict:
    """Input: [increasing u], [paired native counts]. Output: centered support arrays."""
    if len(u_rad) != len(pair_count) or np.any(np.diff(u_rad) <= 0):
        raise ValueError("Phase and pair counts need equal, increasing rows.")
    if np.any((pair_count < 0) | (pair_count > 2)):
        raise ValueError("Native 30-second pair count must be 0, 1, or 2.")
    left = np.searchsorted(u_rad, u_rad - math.pi, side="left")
    right = np.searchsorted(u_rad, u_rad + math.pi, side="right")
    cumulative_count = np.r_[0, np.cumsum(pair_count)]
    paired = cumulative_count[right] - cumulative_count[left]
    expected = 2 * (right - left)
    coverage = paired / expected
    full = (u_rad - math.pi >= u_rad[0]) & (u_rad + math.pi <= u_rad[-1])
    valid = full & (coverage >= 0.80) & (paired > 0)
    return {"left": left, "right": right, "paired": paired,
            "expected": expected, "coverage": coverage, "valid": valid}


def phase_weighted_mean(values: np.ndarray, pair_count: np.ndarray,
                        support: dict) -> np.ndarray:
    """Input: [minute values], [native pair counts], support. Output: [phase means]."""
    if len(values) != len(pair_count) or np.any(
        ~np.isfinite(values) & (pair_count > 0)
    ):
        raise ValueError("All paired minute values must be finite and aligned.")
    paired_values = np.where(pair_count > 0, values, 0.0)
    cumulative_sum = np.r_[0.0, np.cumsum(paired_values * pair_count)]
    window_sum = cumulative_sum[support["right"]] - cumulative_sum[support["left"]]
    means = np.full(len(values), np.nan)
    valid = support["valid"]
    means[valid] = window_sum[valid] / support["paired"][valid]
    return means
