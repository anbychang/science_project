import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from calc_temporal_shape_features import build_feature_rows


def test_features_depend_on_m1_and_time_not_l2():
    """Input: two M1 rows with changed L2 labels. Output: unchanged feature vectors."""
    rows = [
        {"storm_id": "storm", "time_us": 0, "features": (math.log(2), 0.1, 0.2),
         "rho_l2_kg_m3": 3.0, "target_log_residual": 0.4},
        {"storm_id": "storm", "time_us": 86_400_000_000,
         "features": (math.log(4), 0.3, -0.2),
         "rho_l2_kg_m3": 5.0, "target_log_residual": 0.6},
    ]
    original = [row["features"] for row in build_feature_rows(rows, {"storm": 0})]
    rows[0]["rho_l2_kg_m3"] = 99.0
    rows[0]["target_log_residual"] = -2.0
    changed = [row["features"] for row in build_feature_rows(rows, {"storm": 0})]
    assert original == changed
    assert original[0][0] == 0.0
    assert original[1][0] == 1.0
