"""Check the next-orbit GPR does not read the orbit it scores."""

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("phases/phase5-trial8/code").resolve()))
from calc_trial8_next_orbit_gpr import predict_event  # noqa: E402


def orbit_rows(residuals: list[float], grids: list[int] | None = None) -> list[dict]:
    """Input: [residuals], optional [phase grids]. Output: [minimal orbit rows]."""
    if grids is None:
        grids = list(range(len(residuals)))
    return [{"time_us": index * 5_600_000_000,
             "u_rel_rad": grid * 2 * math.pi,
             "residual_log_density": residual}
            for index, (grid, residual) in enumerate(zip(grids, residuals, strict=True))]


def test_target_residual_is_not_used() -> None:
    """Input: two events differing only at target orbit. Output: same GPR estimate."""
    prefix = [0.02, 0.04, 0.03, 0.05, 0.04, 0.06]
    first = predict_event(orbit_rows([*prefix, 0.08]))[0]
    second = predict_event(orbit_rows([*prefix, 0.80]))[0]
    assert first["gp_log_residual_mean"] == second["gp_log_residual_mean"]
    assert first["previous_log_residual"] == second["previous_log_residual"] == 0.06
    assert first["training_pair_count"] == 5


def test_missing_orbit_resets_training() -> None:
    """Input: two consecutive segments separated by a phase gap. Output: only second segment scored."""
    residuals = np.linspace(-0.05, 0.07, 13).tolist()
    grids = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13]
    predictions = predict_event(orbit_rows(residuals, grids))
    assert len(predictions) == 1
    assert predictions[0]["u_rel_rad"] == 13 * 2 * math.pi
