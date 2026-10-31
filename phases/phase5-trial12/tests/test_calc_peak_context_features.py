import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from calc_peak_context_features import build_feature_rows


def test_peak_context_uses_only_m1_and_does_not_integrate_gap():
    """Input: three M1 rows with a missing grid. Output: finite M1-only features."""
    rows = [
        {"storm_id": "storm", "grid_index": 0, "time_us": 0,
         "features": (math.log(2), 0, 0), "rho_l2_kg_m3": 3},
        {"storm_id": "storm", "grid_index": 1, "time_us": 86_400_000_000,
         "features": (math.log(4), 0, 0), "rho_l2_kg_m3": 5},
        {"storm_id": "storm", "grid_index": 3, "time_us": 3 * 86_400_000_000,
         "features": (math.log(3), 0, 0), "rho_l2_kg_m3": 4},
    ]
    first = [row["features"] for row in build_feature_rows(rows)]
    rows[1]["rho_l2_kg_m3"] = 99
    second = [row["features"] for row in build_feature_rows(rows)]
    assert first == second
    assert first[1][2] == 0.0
    assert first[2][3] == first[1][3]
