"""Evaluate the fixed Trial4 baseline with 20-train/5-test storm-group GPR."""

import csv
import json
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase4.code.calc_phase4_trial4_gpr import (
    FEATURE_NAMES,
    fit_gpr,
    hyperparameters,
    score,
)
from phases.phase4.code.calc_phase4_trial4_groupcv import split_storm_folds


ROOT = Path("phases/phase4")
SOURCE = ROOT / "data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite"
OUTPUT = ROOT / "data/sqlite/swarm_a_phase4_trial4_altitude_groupcv20_5_v2.sqlite"
EVENT_METRICS = ROOT / "data/analysis/phase4_trial4_groupcv20_5_event_metrics.csv"
FOLD_METRICS = ROOT / "data/analysis/phase4_trial4_groupcv20_5_fold_metrics.csv"
HYPERPARAMS = ROOT / "data/analysis/phase4_trial4_groupcv20_5_hyperparams.csv"
FOLD_ASSIGNMENT = ROOT / "data/analysis/phase4_trial4_groupcv20_5_folds.json"
ALGORITHM_VERSION = "phase4_trial4_altitude_groupcv20_5_v2"


def load_anchor_rows() -> list[dict]:
    """Input: read-only Phase 4 v1 SQLite. Output: [{Trial4 anchor and feature fields}]."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        cursor = database.execute("""
            SELECT storm_id,time_us,u_rel_rad,h_tau_phase_nt,h_24h_phase_nt,
                   sme_phase_nt,symh_phase_nt,altitude_phase_m,
                   rho_l2_phase_kg_m3,rho_trial4_phase_kg_m3,residual_log_density,
                   r_fit,tau_hours,gain_per_nt
            FROM phase4_trial4_gpr_prediction ORDER BY storm_id,time_us
        """)
        fields = [column[0] for column in cursor.description]
        rows = [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]
    if len(rows) != 2295 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Phase 4 v1 anchor input must contain 2,295 rows from 25 storms.")
    return rows


def feature_matrix(rows: list[dict]) -> np.ndarray:
    """Input: [{anchor fields}]. Output: [anchors x five GPR features]."""
    return np.array([[row[name] for name in FEATURE_NAMES] for row in rows])


def add_held_out_predictions(rows: list[dict]) -> dict:
    """Input: [{anchor fields}]. Output: held-out rows, metrics, hyperparameters, folds."""
    features = feature_matrix(rows)
    residual = np.array([row["residual_log_density"] for row in rows])
    storm_ids = np.array([row["storm_id"] for row in rows])
    folds = split_storm_folds(storm_ids)
    event_metrics = []
    fold_metrics = []
    parameters = []
    assignments = []
    for fold_index, (train_indices, test_indices) in enumerate(folds, 1):
        train_storms = sorted(set(storm_ids[train_indices]))
        test_storms = sorted(set(storm_ids[test_indices]))
        fitted = fit_gpr(features[train_indices], residual[train_indices])
        mean, std = fitted["model"].predict(
            fitted["scaler"].transform(features[test_indices]), return_std=True
        )
        for index, correction, uncertainty in zip(
            test_indices, mean, std, strict=True
        ):
            row = rows[int(index)]
            row["fold_index"] = fold_index
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
        fold_metrics.append({
            "fold_index": fold_index,
            "train_storm_count": len(train_storms),
            "test_storm_count": len(test_storms),
            "test_anchor_count": len(test_indices),
            **score(test_residual, mean, std),
        })
        for storm_id in test_storms:
            mask = storm_ids[test_indices] == storm_id
            event_metrics.append({
                "fold_index": fold_index,
                "storm_id": storm_id,
                "test_anchor_count": int(mask.sum()),
                **score(test_residual[mask], mean[mask], std[mask]),
            })
        fold_parameters = hyperparameters(fitted["model"])
        fold_parameters.update({
            "fold_index": fold_index,
            "train_anchor_count": len(train_indices),
            "test_anchor_count": len(test_indices),
            "convergence_warning_count": fitted["warnings_count"],
        })
        parameters.append(fold_parameters)
        assignments.append({
            "fold_index": fold_index,
            "train_storm_ids": train_storms,
            "test_storm_ids": test_storms,
        })
    if any("fold_index" not in row for row in rows):
        raise ValueError("Phase 4 group CV did not predict every anchor exactly once.")
    if len(event_metrics) != 25 or len({row["storm_id"] for row in event_metrics}) != 25:
        raise ValueError("Phase 4 group CV event metrics are incomplete.")
    held_out_mean = np.array([row["gp_log_residual_mean"] for row in rows])
    held_out_std = np.array([row["gp_log_residual_std"] for row in rows])
    overall = {
        "fold_index": "all_held_out",
        "storm_id": "all_anchors",
        "test_anchor_count": len(rows),
        **score(residual, held_out_mean, held_out_std),
    }
    return {
        "rows": rows,
        "event_metrics": event_metrics,
        "fold_metrics": fold_metrics,
        "parameters": parameters,
        "assignments": assignments,
        "overall": overall,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    """Input: new CSV path, [{field: value}]. Output: saved UTF-8 CSV."""
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(result: dict) -> None:
    """Input: held-out Phase 4 result. Output: atomic group-CV SQLite."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="phase4_trial4_groupcv.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE phase4_groupcv20_5_prediction (
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL, fold_index INTEGER NOT NULL,
                    u_rel_rad REAL NOT NULL, h_tau_phase_nt REAL NOT NULL,
                    h_24h_phase_nt REAL NOT NULL, sme_phase_nt REAL NOT NULL,
                    symh_phase_nt REAL NOT NULL, altitude_phase_m REAL NOT NULL,
                    rho_l2_phase_kg_m3 REAL NOT NULL, rho_trial4_phase_kg_m3 REAL NOT NULL,
                    residual_log_density REAL NOT NULL, rho_gpr_median_kg_m3 REAL NOT NULL,
                    gp_log_residual_mean REAL NOT NULL, gp_log_residual_std REAL NOT NULL,
                    rho_95_lower_kg_m3 REAL NOT NULL, rho_95_upper_kg_m3 REAL NOT NULL,
                    r_fit REAL NOT NULL, tau_hours REAL NOT NULL, gain_per_nt REAL NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (storm_id,time_us)
                );
                CREATE TABLE phase4_groupcv20_5_fold_storm (
                    fold_index INTEGER NOT NULL, role TEXT NOT NULL, storm_id TEXT NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (fold_index,role,storm_id)
                );
                CREATE TABLE phase4_groupcv20_5_metadata (
                    name TEXT PRIMARY KEY,value TEXT NOT NULL
                );
            """)
            fields = [
                "storm_id", "time_us", "fold_index", "u_rel_rad", "h_tau_phase_nt",
                "h_24h_phase_nt", "sme_phase_nt", "symh_phase_nt", "altitude_phase_m",
                "rho_l2_phase_kg_m3", "rho_trial4_phase_kg_m3", "residual_log_density",
                "rho_gpr_median_kg_m3", "gp_log_residual_mean", "gp_log_residual_std",
                "rho_95_lower_kg_m3", "rho_95_upper_kg_m3", "r_fit", "tau_hours",
                "gain_per_nt",
            ]
            database.executemany(
                "INSERT INTO phase4_groupcv20_5_prediction VALUES ("
                + ",".join("?" for _ in range(21)) + ")",
                (tuple(row[field] for field in fields) + (ALGORITHM_VERSION,)
                 for row in result["rows"]),
            )
            fold_rows = []
            for assignment in result["assignments"]:
                for role, storm_ids in (
                    ("train", assignment["train_storm_ids"]),
                    ("test", assignment["test_storm_ids"]),
                ):
                    fold_rows.extend(
                        (assignment["fold_index"], role, storm_id, ALGORITHM_VERSION)
                        for storm_id in storm_ids
                    )
            database.executemany(
                "INSERT INTO phase4_groupcv20_5_fold_storm VALUES (?,?,?,?)", fold_rows
            )
            metadata = {
                "evaluation": "five-fold storm-group 20-train/5-test; Trial4 baseline fixed; held-out GPR only",
                "feature_names": ",".join(FEATURE_NAMES),
                "source_phase4_v1": str(SOURCE),
            }
            database.executemany(
                "INSERT INTO phase4_groupcv20_5_metadata VALUES (?,?)", metadata.items()
            )
            prediction_count = database.execute(
                "SELECT count(*) FROM phase4_groupcv20_5_prediction"
            ).fetchone()[0]
            tested_once = database.execute("""
                SELECT count(*) FROM (
                    SELECT storm_id,count(*) AS count FROM phase4_groupcv20_5_fold_storm
                    WHERE role='test' GROUP BY storm_id HAVING count=1
                )
            """).fetchone()[0]
            if (prediction_count != 2295 or tested_once != 25
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Phase 4 group CV SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: Phase 4 v1 anchors. Output: 20-train/5-test held-out GPR result."""
    outputs = (OUTPUT, EVENT_METRICS, FOLD_METRICS, HYPERPARAMS, FOLD_ASSIGNMENT)
    if any(path.exists() for path in outputs):
        raise FileExistsError("Phase 4 group CV outputs already exist.")
    result = add_held_out_predictions(load_anchor_rows())
    EVENT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    write_sqlite(result)
    write_csv(EVENT_METRICS, result["event_metrics"] + [result["overall"]])
    write_csv(FOLD_METRICS, result["fold_metrics"])
    write_csv(HYPERPARAMS, result["parameters"])
    FOLD_ASSIGNMENT.write_text(json.dumps(result["assignments"], indent=2), encoding="utf-8")
    from phases.phase4.code.prep_phase4_trial4_groupcv_figures import main as draw_figures

    draw_figures()
    print("Saved Phase 4 20/5 group-CV GPR for 2,295 held-out anchors")


if __name__ == "__main__":
    main()
