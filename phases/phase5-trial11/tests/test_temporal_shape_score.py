import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from prep_temporal_shape_gpr import score


def test_constant_event_shift_changes_level_but_not_shape():
    """Input: one event and constant correction. Output: unchanged shape and change errors."""
    rows = [
        {"storm_id": "storm", "grid_index": index, "target_log_residual": value}
        for index, value in enumerate((1.0, 2.0, 3.0))
    ]
    baseline = score(rows, np.zeros(3))
    shifted = score(rows, np.ones(3))
    assert shifted[0] < baseline[0]
    assert math.isclose(shifted[1], baseline[1])
    assert math.isclose(shifted[2], baseline[2])
