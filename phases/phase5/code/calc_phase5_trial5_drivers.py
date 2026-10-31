"""Calculate backward SYM-H rates for Phase5 Trial5 driver features."""

import numpy as np


MICROSECONDS_PER_SECOND = 1_000_000


def backward_rate(time_us: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Input: [UTC microseconds], [SYM-H nT]. Output: [backward rate nT/s]."""
    if time_us.ndim != 1 or values.ndim != 1 or len(time_us) != len(values):
        raise ValueError("SYM-H rate requires aligned one-dimensional arrays.")
    if len(time_us) < 2 or np.any(np.diff(time_us) <= 0):
        raise ValueError("SYM-H rate requires at least two increasing timestamps.")
    rate = np.empty(len(values))
    rate[0] = np.nan
    rate[1:] = np.diff(values) / (np.diff(time_us) / MICROSECONDS_PER_SECOND)
    return rate
