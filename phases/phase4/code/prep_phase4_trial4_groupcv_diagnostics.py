"""Describe feature support and GPR corrections in fixed Phase 4 Trial2 folds."""

import csv
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase4.code.calc_phase4_trial4_gpr import FEATURE_NAMES
from phases.phase4.code.calc_phase4_trial4_groupcv_diagnostics import (
    feature_shift,
    nearest_distances,
    scaled_features,
)


ROOT = Path("phases/phase4")
SOURCE = ROOT / "data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite"
PREDICTION = ROOT / "data/sqlite/swarm_a_phase4_trial4_altitude_groupcv20_5_v2.sqlite"
HYPERPARAMS = ROOT / "data/analysis/phase4_trial4_groupcv20_5_hyperparams.csv"
FEATURE_SHIFT = ROOT / "data/analysis/phase4_trial4_groupcv20_5_feature_shift.csv"
EVENT_GEOMETRY = ROOT / "data/analysis/phase4_trial4_groupcv20_5_event_geometry.csv"
FOLD_GEOMETRY = ROOT / "data/analysis/phase4_trial4_groupcv20_5_fold_geometry.csv"


def load_anchors() -> list[dict]:
    """Input: Phase4 Trial1 SQLite. Output: [{storm_id, five features}]."""
    with closing(sqlite3.connect(f"file:{SOURCE.resolve().as_posix()}?mode=ro", uri=True)) as database:
        cursor = database.execute(
            "SELECT storm_id," + ",".join(FEATURE_NAMES)
            + " FROM phase4_trial4_gpr_prediction ORDER BY storm_id,time_us"
        )
        fields = [column[0] for column in cursor.description]
        return [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]


def load_predictions() -> list[dict]:
    """Input: Phase4 Trial2 SQLite. Output: [{storm_id, fold, residual, correction}]."""
    with closing(sqlite3.connect(f"file:{PREDICTION.resolve().as_posix()}?mode=ro", uri=True)) as database:
        cursor = database.execute("""
            SELECT storm_id,fold_index,residual_log_density,gp_log_residual_mean
            FROM phase4_groupcv20_5_prediction ORDER BY storm_id,time_us
        """)
        fields = [column[0] for column in cursor.description]
        return [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]


def load_fold_storms() -> dict[int, dict[str, set[str]]]:
    """Input: Phase4 Trial2 SQLite. Output: {fold: {role: {storm_id}}}."""
    with closing(sqlite3.connect(f"file:{PREDICTION.resolve().as_posix()}?mode=ro", uri=True)) as database:
        rows = database.execute("""
            SELECT fold_index,role,storm_id FROM phase4_groupcv20_5_fold_storm
            ORDER BY fold_index,role,storm_id
        """).fetchall()
    folds: dict[int, dict[str, set[str]]] = {}
    for fold_index, role, storm_id in rows:
        folds.setdefault(fold_index, {"train": set(), "test": set()})[role].add(storm_id)
    if len(folds) != 5 or any(len(item["train"]) != 20 or len(item["test"]) != 5 for item in folds.values()):
        raise ValueError("Trial2 fold assignments must contain five 20/5 storm splits.")
    return folds


def load_length_scales() -> dict[int, np.ndarray]:
    """Input: Trial2 hyperparameter CSV. Output: {fold: [five ARD length scales]}."""
    with HYPERPARAMS.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 5:
        raise ValueError("Trial2 diagnostics require five hyperparameter rows.")
    return {
        int(row["fold_index"]): np.array([
            float(row[f"length_scale_{feature}"]) for feature in FEATURE_NAMES
        ])
        for row in rows
    }


def feature_matrix(rows: list[dict]) -> np.ndarray:
    """Input: [{five feature fields}]. Output: [anchors x five features]."""
    return np.array([[row[feature] for feature in FEATURE_NAMES] for row in rows])


def write_csv(path: Path, rows: list[dict]) -> None:
    """Input: new CSV path, [{field: value}]. Output: saved UTF-8 CSV."""
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_diagnostics() -> dict[str, list[dict]]:
    """Input: fixed Trial1 and Trial2 outputs. Output: feature-shift and geometry rows."""
    anchors = load_anchors()
    predictions = load_predictions()
    if [row["storm_id"] for row in anchors] != [row["storm_id"] for row in predictions]:
        raise ValueError("Trial1 anchors and Trial2 predictions are not aligned.")
    features = feature_matrix(anchors)
    storm_ids = np.array([row["storm_id"] for row in anchors])
    folds = load_fold_storms()
    length_scales = load_length_scales()
    feature_rows = []
    event_rows = []
    fold_rows = []
    for fold_index, assignment in folds.items():
        train_mask = np.isin(storm_ids, list(assignment["train"]))
        test_mask = np.isin(storm_ids, list(assignment["test"]))
        train_features = features[train_mask]
        test_features = features[test_mask]
        scaled_train, scaled_test = scaled_features(train_features, test_features)
        ordinary_distance = nearest_distances(scaled_train, scaled_test)
        ard_distance = nearest_distances(scaled_train / length_scales[fold_index], scaled_test / length_scales[fold_index])
        non_altitude_ard_distance = nearest_distances(
            scaled_train[:, :-1] / length_scales[fold_index][:-1],
            scaled_test[:, :-1] / length_scales[fold_index][:-1],
        )
        altitude_distance_m = nearest_distances(
            train_features[:, -1:], test_features[:, -1:]
        )
        for feature_index, feature_name in enumerate(FEATURE_NAMES):
            feature_rows.append({
                "fold_index": fold_index,
                "feature_name": feature_name,
                **feature_shift(train_features[:, feature_index], test_features[:, feature_index]),
            })
        test_predictions = [row for row, selected in zip(predictions, test_mask, strict=True) if selected]
        for storm_id in sorted(assignment["test"]):
            event_mask = storm_ids[test_mask] == storm_id
            event_prediction = [row for row in test_predictions if row["storm_id"] == storm_id]
            residual = np.array([row["residual_log_density"] for row in event_prediction])
            correction = np.array([row["gp_log_residual_mean"] for row in event_prediction])
            event_rows.append({
                "fold_index": fold_index,
                "storm_id": storm_id,
                "anchor_count": int(event_mask.sum()),
                "median_nearest_standard_distance": float(np.median(ordinary_distance[event_mask])),
                "median_nearest_ard_distance": float(np.median(ard_distance[event_mask])),
                "median_nearest_non_altitude_ard_distance": float(
                    np.median(non_altitude_ard_distance[event_mask])
                ),
                "median_nearest_altitude_distance_m": float(
                    np.median(altitude_distance_m[event_mask])
                ),
                "median_abs_gpr_correction": float(np.median(np.abs(correction))),
                "trial4_rmse_log_density": float(np.sqrt(np.mean(residual ** 2))),
                "gpr_rmse_log_density": float(np.sqrt(np.mean((residual - correction) ** 2))),
            })
        fold_rows.append({
            "fold_index": fold_index,
            "test_anchor_count": int(test_mask.sum()),
            "median_nearest_standard_distance": float(np.median(ordinary_distance)),
            "p95_nearest_standard_distance": float(np.quantile(ordinary_distance, 0.95)),
            "median_nearest_ard_distance": float(np.median(ard_distance)),
            "p95_nearest_ard_distance": float(np.quantile(ard_distance, 0.95)),
            "median_nearest_non_altitude_ard_distance": float(
                np.median(non_altitude_ard_distance)
            ),
            "p95_nearest_non_altitude_ard_distance": float(
                np.quantile(non_altitude_ard_distance, 0.95)
            ),
            "median_nearest_altitude_distance_m": float(np.median(altitude_distance_m)),
            "median_abs_gpr_correction": float(np.median(np.abs([
                row["gp_log_residual_mean"] for row in test_predictions
            ]))),
        })
    return {"feature_rows": feature_rows, "event_rows": event_rows, "fold_rows": fold_rows}


def main() -> None:
    """Input: existing Phase4 Trial1/Trial2 outputs. Output: non-overwriting diagnostic CSVs."""
    outputs = (FEATURE_SHIFT, EVENT_GEOMETRY, FOLD_GEOMETRY)
    if any(path.exists() for path in outputs):
        raise FileExistsError("Phase 4 Trial2 diagnostic outputs already exist.")
    result = build_diagnostics()
    write_csv(FEATURE_SHIFT, result["feature_rows"])
    write_csv(EVENT_GEOMETRY, result["event_rows"])
    write_csv(FOLD_GEOMETRY, result["fold_rows"])
    print("Saved Phase 4 Trial2 GPR feature-support diagnostics")


if __name__ == "__main__":
    main()
