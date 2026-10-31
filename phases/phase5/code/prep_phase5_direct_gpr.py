"""Run the Phase 4 to Phase 5 next-orbit GPR path in one command."""

import math
import os
import sys
import tempfile
from pathlib import Path

import joblib
import numpy as np

from load_phase5_trial4_orbits import DENSITY, PHASE, load_events
from prep_phase5_gpr_sqlite import write_sqlite

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "phase5-trial9/code"))
from prep_trial9_pooled_orbit_gpr import build_pairs, feature_vector, fit_fold  # noqa: E402
from prep_trial9_save_models import FEATURE_NAMES  # noqa: E402
from phases.phase5.code.calc_phase5_trial4_groupcv import split_storm_folds  # noqa: E402


MODELS = Path("phases/phase5/data/models")
SQLITE = Path("phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite")
VERSION = "phase4_direct_trial4_pooled_orbit_gpr_v1"


def load_final_model() -> dict:
    """Input: saved all-25 model path. Output: validated scaler and GPR bundle."""
    bundle = joblib.load(MODELS / "all_25.joblib")
    if (bundle["algorithm_version"] != VERSION
            or bundle["role"] != "all_25_for_later_use"
            or tuple(bundle["feature_names"]) != FEATURE_NAMES):
        raise ValueError("Unexpected Phase5 direct model artifact.")
    return bundle


def predict_next_orbit(bundle: dict, current: dict, previous: dict) -> dict:
    """Input: model, {current Trial4}, {previous Trial4,L2}. Output: {density,log_std}."""
    if bundle["algorithm_version"] != VERSION:
        raise ValueError("Phase5 direct model version differs.")
    previous_residual = math.log(previous["rho_l2_phase_kg_m3"] /
                                 previous["rho_trial4_phase_kg_m3"])
    features = feature_vector(current, {**previous,
                                        "residual_log_density": previous_residual})
    changes, stds = bundle["model"].predict(
        bundle["scaler"].transform([features]), return_std=True)
    residual = previous_residual + float(changes[0])
    return {"rho_gpr_kg_m3": current["rho_trial4_phase_kg_m3"] * math.exp(residual),
            "log_residual_mean": residual,
            "log_residual_std": float(stds[0])}


def eligible_pair_keys(events: dict[str, list[dict]]) -> set[tuple[str, int]]:
    """Input: {storm: [orbit]}. Output: {(storm, time_us)} after six prior anchors."""
    eligible = set()
    for storm_id, rows in events.items():
        previous_grid = None
        completed = 0
        for row in rows:
            grid = round(row["u_rel_rad"] / (2 * math.pi))
            completed = completed + 1 if previous_grid is not None and grid == previous_grid + 1 else 0
            if completed >= 6:
                eligible.add((storm_id, row["time_us"]))
            previous_grid = grid
    return eligible


def score(rows: list[dict]) -> dict[str, float | int]:
    """Input: [held-out orbit predictions]. Output: three same-position log RMSEs."""
    actual = np.asarray([row["actual_log_residual"] for row in rows])
    previous = np.asarray([row["previous_log_residual"] for row in rows])
    pooled = np.asarray([row["pooled_gpr_log_residual"] for row in rows])
    return {"orbit_count": len(rows),
            "trial4_log_rmse": float(np.sqrt(np.mean(actual ** 2))),
            "previous_orbit_log_rmse": float(np.sqrt(np.mean((actual - previous) ** 2))),
            "pooled_gpr_log_rmse": float(np.sqrt(np.mean((actual - pooled) ** 2)))}


def run(output: Path) -> None:
    """Input: empty result directory, frozen Phase4 data. Output: derived SQLite and six models."""
    events, _ = load_events()
    pairs = build_pairs(events)
    if len(pairs) != 2265:
        raise ValueError(f"Expected 2,265 adjacent orbit pairs; found {len(pairs)}.")
    eligible = eligible_pair_keys(events)
    if len(eligible) != 2115:
        raise ValueError(f"Expected 2,115 comparable orbit points; found {len(eligible)}.")
    storm_ids = np.asarray([storm_id for storm_id, rows in events.items() for _ in rows])
    folds = split_storm_folds(storm_ids)
    predictions = []
    fold_records = []
    for fold_index, (train_indices, test_indices) in enumerate(folds, 1):
        train_ids = set(storm_ids[train_indices])
        test_ids = set(storm_ids[test_indices])
        training = [pair for pair in pairs if pair["storm_id"] in train_ids]
        testing = [pair for pair in pairs if pair["storm_id"] in test_ids]
        scaler, model = fit_fold(training)
        changes, stds = model.predict(scaler.transform(
            [pair["features"] for pair in testing]), return_std=True)
        fold_rows = []
        for pair, change, std in zip(testing, changes, stds, strict=True):
            estimate = pair["previous_log_residual"] + float(change)
            row = {"storm_id": pair["storm_id"], "time_us": pair["time_us"],
                   "previous_time_us": pair["previous_time_us"],
                   "fold_index": fold_index,
                   "comparable_2115": int((pair["storm_id"], pair["time_us"]) in eligible),
                   "rho_l2_phase_kg_m3": pair["rho_l2_phase_kg_m3"],
                   "rho_trial4_phase_kg_m3": pair["rho_trial4_phase_kg_m3"],
                   "actual_log_residual": pair["residual_log_density"],
                   "previous_log_residual": pair["previous_log_residual"],
                   "pooled_gpr_log_residual": estimate,
                   "pooled_gpr_log_std": float(std),
                   "rho_pooled_gpr_kg_m3": pair["rho_trial4_phase_kg_m3"] * math.exp(estimate)}
            fold_rows.append(row)
        predictions.extend(fold_rows)
        joblib.dump({"algorithm_version": VERSION, "fold_index": fold_index,
                     "feature_names": FEATURE_NAMES,
                     "train_storm_ids": sorted(train_ids),
                     "test_storm_ids": sorted(test_ids),
                     "scaler": scaler, "model": model},
                    output / f"fold_{fold_index}.joblib", compress=3)
        fold_records.append({"fold_index": fold_index,
                             "train_storm_ids": sorted(train_ids),
                             "test_storm_ids": sorted(test_ids),
                             "train_pair_count": len(training),
                             "test_pair_count": len(testing),
                             **score(fold_rows)})
        print(f"Fold {fold_index}: {len(training)} train, {len(testing)} test", flush=True)
    if len(predictions) != len(pairs) or len({(r["storm_id"], r["time_us"])
                                            for r in predictions}) != len(pairs):
        raise ValueError("Every adjacent orbit must be tested exactly once.")
    comparable = [row for row in predictions if row["comparable_2115"]]
    all_scaler, all_model = fit_fold(pairs)
    final_path = output / "all_25.joblib"
    joblib.dump({"algorithm_version": VERSION,
                 "role": "all_25_for_later_use",
                 "feature_names": FEATURE_NAMES,
                 "train_storm_ids": sorted(events),
                 "scaler": all_scaler, "model": all_model}, final_path, compress=3)
    loaded = joblib.load(final_path)
    sample = np.asarray([pair["features"] for pair in pairs[:10]])
    if not np.array_equal(all_model.predict(all_scaler.transform(sample)),
                          loaded["model"].predict(loaded["scaler"].transform(sample))):
        raise ValueError("Saved all-storm model changed its predictions.")
    event_metrics = [
        {"storm_id": storm_id, **score([row for row in comparable
                                        if row["storm_id"] == storm_id])}
        for storm_id in events]
    summary_metrics = {"all_adjacent_pairs": score(predictions),
                       "comparable_trial9_positions": score(comparable)}
    write_sqlite(output / SQLITE.name, {
        "events": events,
        "predictions": predictions,
        "event_metrics": event_metrics,
        "folds": fold_records,
        "summary_metrics": summary_metrics,
        "metadata": {
            "algorithm_version": VERSION,
            "source_phase4_phase_sqlite": str(PHASE),
            "source_phase4_density_sqlite": str(DENSITY),
            "feature_names": ",".join(FEATURE_NAMES),
            "final_model": final_path.name,
            "final_train_pair_count": str(len(pairs)),
            "limitation": "Phase4 D-model fitted full events; conditional residual validation, not end-to-end forecast",
        },
    })
    print(summary_metrics["comparable_trial9_positions"], flush=True)


def main() -> None:
    """Input: frozen Phase4 SQLite. Output: new Phase5 SQLite and model directory."""
    if MODELS.exists() or SQLITE.exists():
        raise FileExistsError("Phase 5 GPR result already exists.")
    MODELS.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase5_gpr_", dir=MODELS.parent) as name:
        temporary = Path(name)
        run(temporary)
        SQLITE.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary / SQLITE.name, SQLITE)
        os.replace(temporary, MODELS)
    print(f"Saved Phase 5 GPR SQLite: {SQLITE}")


if __name__ == "__main__":
    main()
