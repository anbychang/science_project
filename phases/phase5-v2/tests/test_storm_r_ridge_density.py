import math
import runpy
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "code/prep_storm_r_ridge_density.py"


def test_ridge_density_substitutes_r_in_v2_formula():
    """Input: one aligned V1/V2 minute and Ridge R. Output: V2 density with new R."""
    calculate_event = runpy.run_path(str(SCRIPT))["calculate_event"]
    quiet = 2e-12
    h_phase = 100.0
    gain = 0.001
    r_fit = 1.2
    r_pred = 0.8
    v2_density = quiet * r_fit * math.exp(gain * h_phase)
    prediction = {"storm_id": "S1", "fold_index": 1, "r_fit": r_fit,
                  "r_pred": r_pred, "t0_time_us": 0}
    minutes, score = calculate_event(
        [(60_000_000, 2.1e-12, quiet, 2.2e-12)],
        [(60_000_000, 2.1e-12, quiet, v2_density, h_phase, gain, r_fit)],
        prediction,
    )
    assert math.isclose(minutes[0][6], quiet * r_pred * math.exp(gain * h_phase))
    assert score[2] == 1


def test_density_comparison_rejects_misaligned_minutes():
    """Input: different V1/V2 minute keys. Output: alignment error."""
    calculate_event = runpy.run_path(str(SCRIPT))["calculate_event"]
    prediction = {"storm_id": "S1", "fold_index": 1, "r_fit": 1.0,
                  "r_pred": 1.0, "t0_time_us": 0}
    with pytest.raises(ValueError, match="mismatch"):
        calculate_event([(0, 1.0, 1.0, 1.0)],
                        [(60_000_000, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0)],
                        prediction)
