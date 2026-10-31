"""Check storm boundaries and held-out labels in the shared GPR data."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path("phases/phase5-trial9/code").resolve()))
from prep_trial9_pooled_orbit_gpr import build_pairs, load_folds  # noqa: E402
from prep_trial9_storm_window import HOUR_US, within_window  # noqa: E402


def rows(storm_id: str, grids: list[int]) -> list[dict]:
    """Input: storm ID, [orbit phase grids]. Output: [minimal orbit rows]."""
    return [{"storm_id": storm_id, "time_us": index,
             "u_rel_rad": grid * 2 * math.pi,
             "rho_trial4_phase_kg_m3": 1e-12 * (1 + index / 10),
             "rho_l2_phase_kg_m3": 1e-12 * (1 + index / 10) * math.exp(index / 100),
             "residual_log_density": index / 100}
            for index, grid in enumerate(grids)]


def test_pairs_stay_within_storm_and_skip_phase_gap() -> None:
    """Input: two storms and one missing orbit. Output: only real adjacent pairs."""
    pairs = build_pairs({"first": rows("first", [0, 1, 3, 4]),
                         "second": rows("second", [0, 1])})
    assert [(pair["storm_id"], pair["time_us"]) for pair in pairs] == [
        ("first", 1), ("first", 3), ("second", 1)]


def test_current_l2_is_only_a_label() -> None:
    """Input: target orbit L2 changed. Output: identical input features, changed target."""
    first = rows("first", [0, 1])
    changed = rows("first", [0, 1])
    changed[-1]["rho_l2_phase_kg_m3"] *= 2
    changed[-1]["residual_log_density"] += math.log(2)
    original_pair = build_pairs({"first": first})[0]
    changed_pair = build_pairs({"first": changed})[0]
    assert original_pair["features"] == changed_pair["features"]
    assert original_pair["change"] != changed_pair["change"]


def test_historical_folds_hold_out_each_storm_once() -> None:
    """Input: saved Trial2 20/5 folds. Output: disjoint 20/5 assignments."""
    import json

    source = Path("phases/phase5-trial2/data/analysis/phase4_trial4_groupcv20_5_folds.json")
    saved = json.loads(source.read_text(encoding="utf-8"))
    storm_ids = set(saved[0]["train_storm_ids"] + saved[0]["test_storm_ids"])
    folds = load_folds(storm_ids)
    assert len(folds) == 5
    assert len({storm for fold in folds for storm in fold["test_storm_ids"]}) == 25


def test_window_uses_only_matched_rows_inside_48_hours() -> None:
    """Input: boundary, outside, unmatched rows. Output: matched boundary only."""
    rows_to_check = [
        {"time_us": -24 * HOUR_US, "same_storm_gpr_log_residual": 0.1},
        {"time_us": 24 * HOUR_US + 1, "same_storm_gpr_log_residual": 0.2},
        {"time_us": 0, "same_storm_gpr_log_residual": None},
    ]
    assert within_window(rows_to_check, 0) == rows_to_check[:1]
