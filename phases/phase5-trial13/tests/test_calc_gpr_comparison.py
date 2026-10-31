import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from calc_gpr_comparison import event_sums, rmse


def test_event_shape_and_change_skip_missing_orbit():
    """Input: three orbit errors with a missing grid. Output: centered shape and one change."""
    rows = [(0, math.exp(1), 1), (1, math.exp(2), 1), (3, math.exp(10), 1)]
    sums = event_sums(rows)
    assert sums["count"] == 3
    assert sums["change_count"] == 1
    assert math.isclose(sums["change_sse"], 1)
    assert math.isclose(rmse([sums], "shape"), math.sqrt(16.22222222222222))
