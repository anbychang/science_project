"""Evaluate new direct geomagnetic drivers with nested storm-group GPR."""

import csv
from dataclasses import replace
import json
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase4.code.calc_phase4_trial4_gpr import score
from phases.phase4.code.calc_phase4_trial4_groupcv import split_storm_folds
from phases.phase4.code.calc_phase4_trial4_trial3 import (
    FINAL_RESTARTS,
    Candidate,
    fit_candidate,
    predict_candidate,
    select_candidate,
)
from phases.phase4.code.prep_phase4_trial4_trial3 import inner_folds


ROOT = Path("phases/phase4")
SOURCE = ROOT / "data/sqlite/swarm_a_phase4_trial5_driver_features_v5.sqlite"
OUTPUT = ROOT / "data/sqlite/swarm_a_phase4_trial5_driver_gpr_v5.sqlite"
EVENT_METRICS = ROOT / "data/analysis/phase4_trial5_event_metrics.csv"
FOLD_METRICS = ROOT / "data/analysis/phase4_trial5_fold_metrics.csv"
SELECTION_METRICS = ROOT / "data/analysis/phase4_trial5_inner_selection.csv"
FOLD_ASSIGNMENT = ROOT / "data/analysis/phase4_trial5_folds.json"
ALGORITHM_VERSION = "phase4_trial5_driver_gpr_v5"
FEATURE_NAMES = ("symh_rate_nt_s", "ap_step", "f107_sfu")
SELECTION_CANDIDATES = (
    Candidate("new_drivers_rbf", (0, 1, 2), "rbf", 0),
    Candidate("new_drivers_matern32", (0, 1, 2), "matern32", 0),
)


def load_rows() -> list[dict]:
    """Input: Trial5 feature SQLite. Output: [{anchor, three drivers, baseline, residual}]."""
    with closing(sqlite3.connect(f"file:{SOURCE.resolve().as_posix()}?mode=ro", uri=True)) as database:
        cursor = database.execute("""
            SELECT storm_id,time_us,symh_rate_nt_s,ap_step,f107_sfu,
                   rho_trial4_phase_kg_m3,residual_log_density
            FROM phase4_trial5_driver_feature ORDER BY storm_id,time_us
        """)
        fields = [column[0] for column in cursor.description]
        rows = [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]
    if len(rows) != 2295 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Trial5 requires 2,295 features from 25 storms.")
    return rows


def feature_matrix(rows: list[dict]) -> np.ndarray:
    """Input: [{three direct driver fields}]. Output: [anchors x three Trial5 features]."""
    features = np.array([[row[name] for name in FEATURE_NAMES] for row in rows])
    if not np.isfinite(features).all():
        raise ValueError("Trial5 direct drivers must be finite.")
    return features


def candidate_metrics(
    training_features: np.ndarray,
    training_residual: np.ndarray,
    training_storm_ids: np.ndarray,
    outer_fold_index: int,
) -> list[dict]:
    """Input: outer training arrays. Output: inner held-out scores for Trial5 candidates."""
    rows = []
    for candidate in SELECTION_CANDIDATES:
        validation_residual = []
        validation_mean = []
        for train_indices, validation_indices in inner_folds(training_storm_ids, outer_fold_index):
            fitted = fit_candidate(
                training_features[train_indices], training_residual[train_indices], candidate
            )
            mean, _ = predict_candidate(fitted, training_features[validation_indices])
            validation_residual.extend(training_residual[validation_indices])
            validation_mean.extend(mean)
        residual = np.array(validation_residual)
        mean = np.array(validation_mean)
        rows.append({
            "outer_fold_index": outer_fold_index,
            "candidate_name": candidate.name,
            "feature_names": ",".join(FEATURE_NAMES),
            "kernel_name": candidate.kernel_name,
            "inner_validation_anchor_count": len(residual),
            "inner_validation_storm_count": len(set(training_storm_ids)),
            "inner_rmse_log_density": float(np.sqrt(np.mean((residual - mean) ** 2))),
            "inner_mae_log_density": float(np.mean(np.abs(residual - mean))),
        })
    return rows


def final_candidate(candidate_name: str) -> Candidate:
    """Input: selected Trial5 candidate name. Output: final-restart candidate specification."""
    for candidate in SELECTION_CANDIDATES:
        if candidate.name == candidate_name:
            return replace(candidate, optimizer_restarts=FINAL_RESTARTS)
    raise ValueError(f"Unknown Trial5 candidate: {candidate_name}")


def add_predictions(rows: list[dict]) -> dict:
    """Input: Trial5 feature rows. Output: nested outer held-out predictions and metrics."""
    features = feature_matrix(rows)
    residual = np.array([row["residual_log_density"] for row in rows])
    storm_ids = np.array([row["storm_id"] for row in rows])
    event_metrics = []
    fold_metrics = []
    selection_metrics = []
    assignments = []
    for fold_index, (train_indices, test_indices) in enumerate(split_storm_folds(storm_ids), 1):
        candidates = candidate_metrics(
            features[train_indices], residual[train_indices], storm_ids[train_indices], fold_index
        )
        selected_name = select_candidate(candidates)
        for candidate in candidates:
            candidate["selected"] = int(candidate["candidate_name"] == selected_name)
        selection_metrics.extend(candidates)
        fitted = fit_candidate(
            features[train_indices], residual[train_indices], final_candidate(selected_name)
        )
        mean, std = predict_candidate(fitted, features[test_indices])
        for index, correction, uncertainty in zip(test_indices, mean, std, strict=True):
            row = rows[int(index)]
            row["outer_fold_index"] = fold_index
            row["selected_candidate_name"] = selected_name
            row["gp_log_residual_mean"] = float(correction)
            row["gp_log_residual_std"] = float(uncertainty)
            row["rho_gpr_median_kg_m3"] = float(
                row["rho_trial4_phase_kg_m3"] * math.exp(correction)
            )
            row["rho_95_lower_kg_m3"] = float(
                row["rho_trial4_phase_kg_m3"] * math.exp(correction - 1.96 * uncertainty)
            )
            row["rho_95_upper_kg_m3"] = float(
                row["rho_trial4_phase_kg_m3"] * math.exp(correction + 1.96 * uncertainty)
            )
        test_residual = residual[test_indices]
        test_storms = sorted(set(storm_ids[test_indices]))
        fold_metrics.append({
            "outer_fold_index": fold_index,
            "selected_candidate_name": selected_name,
            "selection_warning_count": fitted["warnings_count"],
            "test_anchor_count": len(test_indices),
            **score(test_residual, mean, std),
        })
        for storm_id in test_storms:
            mask = storm_ids[test_indices] == storm_id
            event_metrics.append({
                "outer_fold_index": fold_index,
                "selected_candidate_name": selected_name,
                "storm_id": storm_id,
                "test_anchor_count": int(mask.sum()),
                **score(test_residual[mask], mean[mask], std[mask]),
            })
        assignments.append({
            "outer_fold_index": fold_index,
            "train_storm_ids": sorted(set(storm_ids[train_indices])),
            "test_storm_ids": test_storms,
        })
    if any("outer_fold_index" not in row for row in rows):
        raise ValueError("Trial5 did not predict every anchor exactly once.")
    if len(event_metrics) != 25 or len({row["storm_id"] for row in event_metrics}) != 25:
        raise ValueError("Trial5 event metrics are incomplete.")
    mean = np.array([row["gp_log_residual_mean"] for row in rows])
    std = np.array([row["gp_log_residual_std"] for row in rows])
    return {
        "rows": rows,
        "event_metrics": event_metrics,
        "fold_metrics": fold_metrics,
        "selection_metrics": selection_metrics,
        "assignments": assignments,
        "overall": {
            "outer_fold_index": "all_held_out",
            "selected_candidate_name": "nested_selection",
            "storm_id": "all_anchors",
            "test_anchor_count": len(rows),
            **score(residual, mean, std),
        },
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    """Input: new CSV path and rows. Output: saved UTF-8 CSV."""
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(result: dict) -> None:
    """Input: Trial5 nested result. Output: atomic Trial5 prediction SQLite database."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="phase4_trial5.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE phase4_trial5_prediction (
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL, outer_fold_index INTEGER NOT NULL,
                    selected_candidate_name TEXT NOT NULL, symh_rate_nt_s REAL NOT NULL,
                    ap_step REAL NOT NULL, f107_sfu REAL NOT NULL, residual_log_density REAL NOT NULL,
                    rho_trial4_phase_kg_m3 REAL NOT NULL, rho_gpr_median_kg_m3 REAL NOT NULL,
                    gp_log_residual_mean REAL NOT NULL, gp_log_residual_std REAL NOT NULL,
                    rho_95_lower_kg_m3 REAL NOT NULL, rho_95_upper_kg_m3 REAL NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (storm_id,time_us)
                );
                CREATE TABLE phase4_trial5_inner_selection (
                    outer_fold_index INTEGER NOT NULL, candidate_name TEXT NOT NULL, feature_names TEXT NOT NULL,
                    kernel_name TEXT NOT NULL, inner_validation_anchor_count INTEGER NOT NULL,
                    inner_validation_storm_count INTEGER NOT NULL, inner_rmse_log_density REAL NOT NULL,
                    inner_mae_log_density REAL NOT NULL, selected INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (outer_fold_index,candidate_name)
                );
                CREATE TABLE phase4_trial5_fold_storm (
                    outer_fold_index INTEGER NOT NULL, role TEXT NOT NULL, storm_id TEXT NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (outer_fold_index,role,storm_id)
                );
                CREATE TABLE phase4_trial5_metadata (name TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            fields = [
                "storm_id", "time_us", "outer_fold_index", "selected_candidate_name",
                "symh_rate_nt_s", "ap_step", "f107_sfu", "residual_log_density",
                "rho_trial4_phase_kg_m3", "rho_gpr_median_kg_m3", "gp_log_residual_mean",
                "gp_log_residual_std", "rho_95_lower_kg_m3", "rho_95_upper_kg_m3",
            ]
            database.executemany(
                "INSERT INTO phase4_trial5_prediction VALUES (" + ",".join("?" for _ in range(15)) + ")",
                (tuple(row[field] for field in fields) + (ALGORITHM_VERSION,) for row in result["rows"]),
            )
            database.executemany(
                "INSERT INTO phase4_trial5_inner_selection VALUES (?,?,?,?,?,?,?,?,?,?)",
                (tuple(row[field] for field in (
                    "outer_fold_index", "candidate_name", "feature_names", "kernel_name",
                    "inner_validation_anchor_count", "inner_validation_storm_count",
                    "inner_rmse_log_density", "inner_mae_log_density", "selected",
                )) + (ALGORITHM_VERSION,) for row in result["selection_metrics"]),
            )
            fold_rows = []
            for assignment in result["assignments"]:
                for role, storm_ids in (("train", assignment["train_storm_ids"]), ("test", assignment["test_storm_ids"])):
                    fold_rows.extend((assignment["outer_fold_index"], role, storm_id, ALGORITHM_VERSION) for storm_id in storm_ids)
            database.executemany("INSERT INTO phase4_trial5_fold_storm VALUES (?,?,?,?)", fold_rows)
            metadata = {
                "evaluation": "five outer 20/5 storm splits; four inner 15/5 splits select kernel; Trial4 baseline fixed",
                "features": ",".join(FEATURE_NAMES),
                "source_trial5_features": str(SOURCE),
            }
            database.executemany("INSERT INTO phase4_trial5_metadata VALUES (?,?)", metadata.items())
            count = database.execute("SELECT count(*) FROM phase4_trial5_prediction").fetchone()[0]
            tested_once = database.execute("""
                SELECT count(*) FROM (SELECT storm_id,count(*) AS count FROM phase4_trial5_fold_storm
                WHERE role='test' GROUP BY storm_id HAVING count=1)
            """).fetchone()[0]
            if (count != 2295 or tested_once != 25
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Trial5 SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: Trial5 driver feature table. Output: non-overwriting nested Trial5 GPR outputs."""
    outputs = (OUTPUT, EVENT_METRICS, FOLD_METRICS, SELECTION_METRICS, FOLD_ASSIGNMENT)
    if any(path.exists() for path in outputs):
        raise FileExistsError("Trial5 GPR outputs already exist.")
    result = add_predictions(load_rows())
    EVENT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    write_sqlite(result)
    write_csv(EVENT_METRICS, result["event_metrics"] + [result["overall"]])
    write_csv(FOLD_METRICS, result["fold_metrics"])
    write_csv(SELECTION_METRICS, result["selection_metrics"])
    FOLD_ASSIGNMENT.write_text(json.dumps(result["assignments"], indent=2), encoding="utf-8")
    print("Saved Phase4 Trial5 direct-driver nested GPR for 2,295 held-out anchors")


if __name__ == "__main__":
    main()
