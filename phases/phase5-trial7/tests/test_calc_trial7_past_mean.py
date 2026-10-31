"""Check that the past-only average never reads the scored minute."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("phases/phase5-trial7/code").resolve()))
from calc_trial7_past_mean import past_mean  # noqa: E402


def test_current_value_is_not_used() -> None:
    """Input: two series differing at target. Output: identical target estimate."""
    first = past_mean(np.array([1.0, 2.0, 3.0]), 2)
    second = past_mean(np.array([1.0, 2.0, 100.0]), 2)
    assert first[2] == second[2] == 1.5


def test_missing_minute_resets_history() -> None:
    """Input: series with a missing minute. Output: no cross-gap estimate."""
    result = past_mean(np.array([1.0, 2.0, np.nan, 4.0, 5.0, 6.0]), 2)
    assert np.allclose(result, [np.nan, np.nan, np.nan, np.nan, np.nan, 4.5],
                       equal_nan=True)
