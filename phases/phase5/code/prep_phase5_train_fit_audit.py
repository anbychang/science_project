"""Recompute in-sample scores for the saved Trial 10-12 storm folds."""

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path("phases/phase5-trial10/code").resolve()))
sys.path.insert(0, str(Path("phases/phase5-trial11/code").resolve()))
sys.path.insert(0, str(Path("phases/phase5-trial12/code").resolve()))

from phases.phase5.code.calc_phase5_trial4_groupcv import split_storm_folds
from calc_m1_shape_features import build_triplets
from calc_peak_context_features import build_feature_rows as build_peak_rows
from calc_temporal_shape_features import build_feature_rows as build_temporal_rows
from prep_phase5_m1_shape_gpr import fit_fold, load_anchors
from prep_temporal_shape_gpr import center_events, fit_gpr, load_event_times, score


OUTPUT = Path("phases/phase5/data/sqlite/swarm_a_phase5_train_fit_audit_v1.sqlite")
VERSION = "phase5_train_fit_audit_v1"
SOURCES = {
    "Trial10": Path("phases/phase5-trial10/data/sqlite/swarm_a_phase5_m1_shape_gpr_v1.sqlite"),
    "Trial11": Path("phases/phase5-trial11/data/sqlite/swarm_a_phase5_temporal_shape_gpr_v1.sqlite"),
    "Trial12": Path("phases/phase5-trial12/data/sqlite/swarm_a_phase5_peak_context_gpr_v1.sqlite"),
}


def read_saved_test_scores(trial: str) -> dict:
    """Input: Trial name. Output: {fold_index: (M1 test RMSE, GPR test RMSE)}."""
    uri = f"file:{SOURCES[trial].resolve().as_posix()}?mode=ro"
    m1_column = "m1_log_rmse" if trial == "Trial10" else "m1_total_rmse"
    gp_column = "gpr_log_rmse" if trial == "Trial10" else "gp_total_rmse"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute(
            f"SELECT fold_index,{m1_column},{gp_column} FROM fold_metric"
        ).fetchall()
    return {fold: (m1_rmse, gp_rmse) for fold, m1_rmse, gp_rmse in rows}


def audit_trial(trial: str, rows: list[dict]) -> list[tuple]:
    """Input: Trial name, [orbit feature row]. Output: [train/test fold metric row]."""
    features = np.array([row["features"] for row in rows])
    targets = np.array([row["target_log_residual"] for row in rows])
    storms = np.array([row["storm_id"] for row in rows])
    saved_scores = read_saved_test_scores(trial)
    metrics = []
    for fold, (train, test) in enumerate(split_storm_folds(storms), 1):
        train_targets = targets[train]
        if trial == "Trial10":
            scaler, target_scale, model, _ = fit_fold(features[train], train_targets)
        else:
            centered = center_events(train_targets, storms[train])
            scaler, target_scale, model, _ = fit_gpr(features[train], centered)
        train_prediction = target_scale * model.predict(scaler.transform(features[train]))
        test_prediction = target_scale * model.predict(scaler.transform(features[test]))
        if trial != "Trial10":
            train_prediction = center_events(train_prediction, storms[train])
            test_prediction = center_events(test_prediction, storms[test])
        train_rows = [rows[int(index)] for index in train]
        test_rows = [rows[int(index)] for index in test]
        train_m1 = score(train_rows, np.zeros(len(train)))
        train_gp = score(train_rows, train_prediction)
        test_m1 = score(test_rows, np.zeros(len(test)))
        test_gp = score(test_rows, test_prediction)
        expected_m1, expected_gp = saved_scores[fold]
        if abs(test_m1[0] - expected_m1) > 1e-8 or abs(test_gp[0] - expected_gp) > 1e-8:
            raise ValueError(f"{trial} fold {fold}: retrained test score differs from saved score")
        metrics.append((trial, fold, len(set(storms[train])), len(train),
                        len(set(storms[test])), len(test), ",".join(sorted(set(storms[test]))),
                        train_m1[0], train_gp[0], test_m1[0], test_gp[0],
                        train_m1[1], train_gp[1], test_m1[1], test_gp[1], VERSION))
        print(f"{trial} fold {fold}: train {train_gp[0]:.5f}, test {test_gp[0]:.5f}",
              flush=True)
    return metrics


def write_sqlite(metrics: list[tuple]) -> None:
    """Input: [15 fold metric rows]. Output: new derived SQLite file, atomically."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE fold_metric (
                    trial TEXT NOT NULL,fold_index INTEGER NOT NULL,
                    train_storm_count INTEGER NOT NULL,train_orbit_count INTEGER NOT NULL,
                    test_storm_count INTEGER NOT NULL,test_orbit_count INTEGER NOT NULL,
                    test_storm_ids TEXT NOT NULL,
                    train_m1_total_rmse REAL NOT NULL,train_gp_total_rmse REAL NOT NULL,
                    test_m1_total_rmse REAL NOT NULL,test_gp_total_rmse REAL NOT NULL,
                    train_m1_shape_rmse REAL NOT NULL,train_gp_shape_rmse REAL NOT NULL,
                    test_m1_shape_rmse REAL NOT NULL,test_gp_shape_rmse REAL NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY(trial,fold_index)
                );
            """)
            database.executemany("INSERT INTO fold_metric VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 metrics)
            if (database.execute("SELECT count(*) FROM fold_metric").fetchone()[0] != 15
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Training-fit audit SQLite failed validation")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: historical M1/L2 and saved fold scores. Output: in-sample score audit."""
    triplets = build_triplets(load_anchors())
    trial_rows = {
        "Trial10": triplets,
        "Trial11": build_temporal_rows(triplets, load_event_times()),
        "Trial12": build_peak_rows(triplets),
    }
    metrics = []
    for trial, rows in trial_rows.items():
        metrics.extend(audit_trial(trial, rows))
    write_sqlite(metrics)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
