"""Run nested storm-group time, tau, and seasonal GPR for Phase5 Trial4."""

import csv
from dataclasses import replace
import json
import math
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PHASES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PHASES_ROOT / "phase5-trial2/code"))
sys.path.insert(0, str(PHASES_ROOT / "phase5-trial3/code"))

from phases.phase5.code.calc_phase5_trial4_gpr import score
from phases.phase5.code.calc_phase5_trial4_groupcv import split_storm_folds
from phases.phase5.code.calc_phase5_trial4_time_tau_season import FEATURE_NAMES, feature_matrix
from phases.phase5.code.calc_phase5_trial4_trial3 import (
    FINAL_RESTARTS,
    RANDOM_STATE,
    Candidate,
    fit_candidate,
    predict_candidate,
    select_candidate,
)
from prep_phase5_trial4_groupcv import load_anchor_rows
from prep_phase5_trial4_trial3 import inner_folds


ROOT = Path("phases/phase5-trial4")
OUTPUT = ROOT / "data/sqlite/swarm_a_phase4_trial4_time_tau_season_nested_v4.sqlite"
EVENT_METRICS = ROOT / "data/analysis/phase4_trial4_time_tau_season_event_metrics.csv"
FOLD_METRICS = ROOT / "data/analysis/phase4_trial4_time_tau_season_fold_metrics.csv"
SELECTION_METRICS = ROOT / "data/analysis/phase4_trial4_time_tau_season_inner_selection.csv"
FOLD_ASSIGNMENT = ROOT / "data/analysis/phase4_trial4_time_tau_season_folds.json"
ALGORITHM_VERSION = "phase4_trial4_time_tau_season_nested_v4"
SELECTION_CANDIDATES = (
    Candidate("time_tau_season_rbf", (0, 1, 2, 3), "rbf", 0),
    Candidate("time_tau_season_matern32", (0, 1, 2, 3), "matern32", 0),
)


def candidate_metrics(
    training_features: np.ndarray,
    training_residual: np.ndarray,
    training_storm_ids: np.ndarray,
    outer_fold_index: int,
) -> list[dict]:
    """Input: outer training arrays. Output: inner held-out metrics for two Trial4 candidates."""
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
    """Input: selected Trial4 candidate name. Output: same candidate with final optimizer restarts."""
    for candidate in SELECTION_CANDIDATES:
        if candidate.name == candidate_name:
            return replace(candidate, optimizer_restarts=FINAL_RESTARTS)
    raise ValueError(f"Unknown Trial4 candidate: {candidate_name}")


def add_predictions(rows: list[dict]) -> dict:
    """Input: Trial1 anchors. Output: nested outer held-out Trial4 prediction result."""
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
        raise ValueError("Trial4 did not predict every anchor exactly once.")
    if len(event_metrics) != 25 or len({row["storm_id"] for row in event_metrics}) != 25:
        raise ValueError("Trial4 event metrics are incomplete.")
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
    """Input: Trial4 result. Output: atomic Trial4 SQLite database."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="phase4_trial4_time_tau_season.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE phase4_trial4_prediction (
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL, outer_fold_index INTEGER NOT NULL,
                    selected_candidate_name TEXT NOT NULL, relative_time_hours REAL NOT NULL,
                    tau_hours REAL NOT NULL, season_sin REAL NOT NULL, season_cos REAL NOT NULL,
                    residual_log_density REAL NOT NULL, rho_trial4_phase_kg_m3 REAL NOT NULL,
                    rho_gpr_median_kg_m3 REAL NOT NULL, gp_log_residual_mean REAL NOT NULL,
                    gp_log_residual_std REAL NOT NULL, rho_95_lower_kg_m3 REAL NOT NULL,
                    rho_95_upper_kg_m3 REAL NOT NULL, algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id,time_us)
                );
                CREATE TABLE phase4_trial4_inner_selection (
                    outer_fold_index INTEGER NOT NULL, candidate_name TEXT NOT NULL, feature_names TEXT NOT NULL,
                    kernel_name TEXT NOT NULL, inner_validation_anchor_count INTEGER NOT NULL,
                    inner_validation_storm_count INTEGER NOT NULL, inner_rmse_log_density REAL NOT NULL,
                    inner_mae_log_density REAL NOT NULL, selected INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (outer_fold_index,candidate_name)
                );
                CREATE TABLE phase4_trial4_fold_storm (
                    outer_fold_index INTEGER NOT NULL, role TEXT NOT NULL, storm_id TEXT NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (outer_fold_index,role,storm_id)
                );
                CREATE TABLE phase4_trial4_metadata (name TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            database.executemany(
                "INSERT INTO phase4_trial4_prediction VALUES (" + ",".join("?" for _ in range(16)) + ")",
                (
                    (
                        row["storm_id"], row["time_us"], row["outer_fold_index"],
                        row["selected_candidate_name"], *feature_matrix([row])[0],
                        row["residual_log_density"], row["rho_trial4_phase_kg_m3"],
                        row["rho_gpr_median_kg_m3"], row["gp_log_residual_mean"],
                        row["gp_log_residual_std"], row["rho_95_lower_kg_m3"],
                        row["rho_95_upper_kg_m3"],
                    )
                    + (ALGORITHM_VERSION,)
                    for row in result["rows"]
                ),
            )
            database.executemany(
                "INSERT INTO phase4_trial4_inner_selection VALUES (?,?,?,?,?,?,?,?,?,?)",
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
            database.executemany("INSERT INTO phase4_trial4_fold_storm VALUES (?,?,?,?)", fold_rows)
            metadata = {
                "evaluation": "five outer 20/5 storm splits; four inner 15/5 splits select kernel; Trial4 baseline fixed",
                "features": ",".join(FEATURE_NAMES),
                "tau_boundary": "tau_hours is a fixed Trial4 event fit and is retrospective, not forecast input",
                "source_phase4_v1": "phases/phase5-trial1/data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite",
            }
            database.executemany("INSERT INTO phase4_trial4_metadata VALUES (?,?)", metadata.items())
            prediction_count = database.execute("SELECT count(*) FROM phase4_trial4_prediction").fetchone()[0]
            tested_once = database.execute("""
                SELECT count(*) FROM (SELECT storm_id,count(*) AS count FROM phase4_trial4_fold_storm
                WHERE role='test' GROUP BY storm_id HAVING count=1)
            """).fetchone()[0]
            if (prediction_count != 2295 or tested_once != 25
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Trial4 SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: Phase5 Trial1 anchors. Output: non-overwriting nested Trial4 outputs."""
    outputs = (OUTPUT, EVENT_METRICS, FOLD_METRICS, SELECTION_METRICS, FOLD_ASSIGNMENT)
    if any(path.exists() for path in outputs):
        raise FileExistsError("Phase5 Trial4 outputs already exist.")
    result = add_predictions(load_anchor_rows())
    EVENT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    write_sqlite(result)
    write_csv(EVENT_METRICS, result["event_metrics"] + [result["overall"]])
    write_csv(FOLD_METRICS, result["fold_metrics"])
    write_csv(SELECTION_METRICS, result["selection_metrics"])
    FOLD_ASSIGNMENT.write_text(json.dumps(result["assignments"], indent=2), encoding="utf-8")
    print("Saved Phase5 Trial4 time/tau/season nested GPR for 2,295 held-out anchors")


if __name__ == "__main__":
    main()
