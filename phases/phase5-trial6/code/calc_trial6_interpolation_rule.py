"""Try a no-peeking rule for deciding when to interpolate a six-hour gap."""

import csv
from pathlib import Path

import numpy as np

from calc_trial6_ridge import block_masks, load_rows, write_csv


ROOT = Path("phases/phase5-trial6")
REGULAR = ROOT / "data/analysis/trial6_block_predictions.csv"
STRESS = ROOT / "data/analysis/trial6_stress_predictions.csv"
BLOCKS = ROOT / "data/analysis/trial6_interpolation_rule_blocks.csv"
PREDICTIONS = ROOT / "data/analysis/trial6_interpolation_rule_predictions.csv"
SUMMARY = ROOT / "data/analysis/trial6_interpolation_rule_summary.csv"
HOUR_US = 3_600_000_000
GAP_HOURS = 6.0
VERSION = "phase4_trial6_interpolation_rules_v1"


def read_predictions() -> dict[tuple[str, str, int], list[dict]]:
    """Input: regular/stress prediction CSVs. Output: {(selection,storm,start): [rows]}."""
    groups: dict[tuple[str, str, int], list[dict]] = {}
    for path, regular in ((REGULAR, True), (STRESS, False)):
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                selection = "regular_grid" if regular else row["selection"]
                key = (selection, row["storm_id"], int(row["block_start_us"]))
                groups.setdefault(key, []).append(row)
    return groups


def support_span(rows: list[dict], selected: np.ndarray) -> tuple[int, int]:
    """Input: [anchors], [selected bool]. Output: (first,last) native support us."""
    held = [row for row, chosen in zip(rows, selected, strict=True) if chosen]
    return (min(row["support_start_us"] for row in held),
            max(row["support_end_us"] for row in held))


def check_shadow(rows: list[dict], target_start: float,
                 shadow_start: float) -> dict | None:
    """Input: [anchors], target/shadow starts in h. Output: {scores,passed} or None."""
    elapsed = np.array([row["elapsed_hours"] for row in rows])
    residual = np.array([row["residual_log_density"] for row in rows])
    target = (elapsed >= target_start) & (elapsed < target_start + GAP_HOURS)
    shadow = (elapsed >= shadow_start) & (elapsed < shadow_start + GAP_HOURS)
    if target.sum() == 0 or shadow.sum() < 2:
        return None
    spans = [support_span(rows, selected) for selected in (target, shadow)]
    train = np.array([all(row["support_end_us"] < first
                          or row["support_start_us"] > last
                          for first, last in spans) for row in rows])
    if not np.any(train & (elapsed < shadow_start)) or not np.any(
        train & (elapsed >= shadow_start + GAP_HOURS)
    ):
        return None
    estimate = np.interp(elapsed[shadow], elapsed[train], residual[train])
    true = residual[shadow]
    baseline_rmse = float(np.sqrt(np.mean(true ** 2)))
    interpolation_rmse = float(np.sqrt(np.mean((true - estimate) ** 2)))
    return {"anchor_count": int(shadow.sum()), "baseline_rmse": baseline_rmse,
            "interpolation_rmse": interpolation_rmse,
            "passed": interpolation_rmse < baseline_rmse}


def decide(rows: list[dict], block_start_us: int) -> dict:
    """Input: [anchors], target start us. Output: {left,right,apply}."""
    target_start = (block_start_us - rows[0]["time_us"]) / HOUR_US
    left = check_shadow(rows, target_start, target_start - 12)
    right = check_shadow(rows, target_start, target_start + 12)
    return {"left": left, "right": right,
            "apply": left is not None and right is not None
            and left["passed"] and right["passed"]}


def same_sign_decision(rows: list[dict], block_start_us: int) -> bool:
    """Input: [anchors], target start us. Output: both visible endpoints have same sign."""
    start_hour = (block_start_us - rows[0]["time_us"]) / HOUR_US
    masks = block_masks(rows, start_hour)
    if masks is None:
        return False
    elapsed = np.array([row["elapsed_hours"] for row in rows])
    residual = np.array([row["residual_log_density"] for row in rows])
    left = np.flatnonzero(masks["train"] & (elapsed < start_hour))[-1]
    right = np.flatnonzero(masks["train"] & (elapsed >= start_hour + GAP_HOURS))[0]
    return bool(residual[left] * residual[right] > 0)


def error_metrics(rows: list[dict], prediction_field: str) -> tuple[float, float]:
    """Input: [scored rows], prediction field. Output: (RMSE,MAE) in log density."""
    error = np.array([float(row["residual_true"]) - float(row[prediction_field])
                      for row in rows])
    return float(np.sqrt(np.mean(error ** 2))), float(np.mean(np.abs(error)))


def main() -> None:
    """Input: Trial6 anchors/predictions. Output: rule blocks, points, summary CSVs."""
    if any(path.exists() for path in (BLOCKS, PREDICTIONS, SUMMARY)):
        raise FileExistsError("Trial6 interpolation rule output already exists.")
    anchors = load_rows()
    grouped = read_predictions()
    blocks = []
    predictions = []
    for (selection, storm_id, start_us), targets in sorted(grouped.items()):
        decision = decide(anchors[storm_id], start_us)
        same_sign = same_sign_decision(anchors[storm_id], start_us)
        scored = []
        for target in targets:
            row = {"selection": selection, "storm_id": storm_id,
                   "block_start_us": start_us, "time_us": int(target["time_us"]),
                   "residual_true": float(target["residual_true"]),
                   "trial4": 0.0,
                   "always_interpolate": float(target["interpolation"]),
                   "rule_prediction": (float(target["interpolation"])
                                       if decision["apply"] else 0.0),
                   "apply_interpolation": int(decision["apply"]),
                   "same_sign_prediction": (float(target["interpolation"])
                                            if same_sign else 0.0),
                   "same_sign_apply": int(same_sign),
                   "algorithm_version": VERSION}
            scored.append(row)
            predictions.append(row)
        baseline_rmse, _ = error_metrics(scored, "trial4")
        always_rmse, _ = error_metrics(scored, "always_interpolate")
        rule_rmse, _ = error_metrics(scored, "rule_prediction")
        same_sign_rmse, _ = error_metrics(scored, "same_sign_prediction")
        blocks.append({
            "selection": selection, "storm_id": storm_id,
            "block_start_us": start_us, "heldout_count": len(targets),
            "left_shadow_count": decision["left"]["anchor_count"] if decision["left"] else 0,
            "right_shadow_count": decision["right"]["anchor_count"] if decision["right"] else 0,
            "left_shadow_improved": (int(decision["left"]["passed"])
                                     if decision["left"] else ""),
            "right_shadow_improved": (int(decision["right"]["passed"])
                                      if decision["right"] else ""),
            "apply_interpolation": int(decision["apply"]),
            "same_sign_apply": int(same_sign),
            "trial4_rmse": baseline_rmse,
            "always_interpolate_rmse": always_rmse,
            "rule_rmse": rule_rmse,
            "same_sign_rmse": same_sign_rmse,
            "algorithm_version": VERSION,
        })
    summary = []
    for selection in ("regular_grid", "t0_centered", "symh_variation_outside_t0"):
        chosen_blocks = [row for row in blocks if row["selection"] == selection]
        chosen_points = [row for row in predictions if row["selection"] == selection]
        baseline_rmse, baseline_mae = error_metrics(chosen_points, "trial4")
        always_rmse, always_mae = error_metrics(chosen_points, "always_interpolate")
        rule_rmse, rule_mae = error_metrics(chosen_points, "rule_prediction")
        same_sign_rmse, same_sign_mae = error_metrics(chosen_points, "same_sign_prediction")
        summary.append({
            "selection": selection,
            "block_count": len(chosen_blocks),
            "eligible_count": sum(row["left_shadow_improved"] != ""
                                  and row["right_shadow_improved"] != ""
                                  for row in chosen_blocks),
            "apply_count": sum(row["apply_interpolation"] for row in chosen_blocks),
            "same_sign_apply_count": sum(row["same_sign_apply"] for row in chosen_blocks),
            "heldout_count": len(chosen_points),
            "trial4_rmse": baseline_rmse, "always_interpolate_rmse": always_rmse,
            "rule_rmse": rule_rmse, "same_sign_rmse": same_sign_rmse,
            "trial4_mae": baseline_mae, "always_interpolate_mae": always_mae,
            "rule_mae": rule_mae, "same_sign_mae": same_sign_mae,
            "always_worse_blocks": sum(row["always_interpolate_rmse"] > row["trial4_rmse"]
                                       for row in chosen_blocks),
            "rule_worse_blocks": sum(row["rule_rmse"] > row["trial4_rmse"]
                                     for row in chosen_blocks),
            "same_sign_worse_blocks": sum(row["same_sign_rmse"] > row["trial4_rmse"]
                                            for row in chosen_blocks),
            "algorithm_version": VERSION,
        })
    write_csv(BLOCKS, blocks)
    write_csv(PREDICTIONS, predictions)
    write_csv(SUMMARY, summary)
    print(f"Scored {len(blocks)} blocks with two interpolation decision rules", flush=True)


if __name__ == "__main__":
    main()
