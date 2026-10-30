"""Check the trial grid's scale and minimum selection."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from calc_m2_r_grid import choose_trial, score_r_grid


def test_grid_recovers_a_known_trial_multiplier() -> None:
    """Input: exact log ratio for R=1.23. Output: grid minimum at 1.23."""
    scores = score_r_grid([math.log(1.23)] * 3)
    assert len(scores) == 121
    assert scores[0][0] == 0.4
    assert scores[-1][0] == 1.6
    assert choose_trial(scores)[0] == 1.23
