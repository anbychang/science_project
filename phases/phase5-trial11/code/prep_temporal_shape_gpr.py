"""Test a temporal, trend-focused GPR on whole-storm held-out M1 curves."""

import math
import os
import sqlite3
import sys
import tempfile
import warnings
from contextlib import closing
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path("phases/phase5-trial10/code").resolve()))

from phases.phase5.code.calc_phase5_trial4_groupcv import split_storm_folds
from calc_m1_shape_features import build_triplets
from prep_phase5_m1_shape_gpr import M1, load_anchors
from calc_temporal_shape_features import build_feature_rows


OUTPUT = Path("phases/phase5-trial11/data/sqlite/swarm_a_phase5_temporal_shape_gpr_v1.sqlite")
VERSION = "phase5_trial11_temporal_shape_gpr_v1"
FEATURE_NAMES = ("days_from_t0", "log_m1", "relative_log_m1", "centered_log_slope")


def load_event_times() -> dict:
    """Input: read-only Phase 3 overview. Output: {storm_id: t0_time_us}."""
    uri = f"file:{M1.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        return dict(database.execute(
            "SELECT storm_id,t0_time_us FROM phase3_25storm_overview"))


def center_events(values: np.ndarray, storms: np.ndarray) -> np.ndarray:
    """Input: [orbit value], [storm_id]. Output: values minus each storm's mean."""
    centered = values.copy()
    for storm in np.unique(storms):
        mask = storms == storm
        centered[mask] -= np.mean(values[mask])
    return centered


def score(rows: list[dict], predicted: np.ndarray) -> tuple[float, float, float]:
    """Input: [orbit row], [predicted log correction]. Output: total, shape, change RMSE."""
    actual = np.array([row["target_log_residual"] for row in rows])
    storms = np.array([row["storm_id"] for row in rows])
    errors = actual - predicted
    total = float(np.sqrt(np.mean(errors ** 2)))
    shape = float(np.sqrt(np.mean(center_events(errors, storms) ** 2)))
    indexed = sorted(zip(rows, errors, strict=True),
                     key=lambda pair: (pair[0]["storm_id"], pair[0]["grid_index"]))
    changes = [current_error - previous_error
               for (previous, previous_error), (current, current_error)
               in zip(indexed, indexed[1:])
               if current["storm_id"] == previous["storm_id"]
               and current["grid_index"] == previous["grid_index"] + 1]
    change = float(np.sqrt(np.mean(np.square(changes))))
    return total, shape, change


def fit_gpr(features: np.ndarray, targets: np.ndarray) -> tuple:
    """Input: train [four features], centered log residual. Output: X scaler, y scale, GP, warning count."""
    scaler = StandardScaler().fit(features)
    target_scale = float(np.std(targets))
    if target_scale <= 0 or not math.isfinite(target_scale):
        raise ValueError("Training shape targets must have positive finite scale.")
    kernel = (ConstantKernel(1.0, (1e-2, 1e2))
              * Matern(np.ones(4), (1e-2, 1e2), nu=1.5)
              + WhiteKernel(0.1, (1e-3, 1.0)))
    model = GaussianProcessRegressor(
        kernel=kernel, alpha=1e-8, normalize_y=False,
        n_restarts_optimizer=0, random_state=20261030,
    )
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        model.fit(scaler.transform(features), targets / target_scale)
    warning_count = sum(isinstance(item.message, ConvergenceWarning) for item in emitted)
    return scaler, target_scale, model, warning_count


def evaluate(rows: list[dict], version: str) -> dict:
    """Input: [M1-only features with historical L2 label], version. Output: held-out result."""
    features = np.array([row["features"] for row in rows])
    targets = np.array([row["target_log_residual"] for row in rows])
    storms = np.array([row["storm_id"] for row in rows])
    held_out = np.full(len(rows), np.nan)
    fold_rows = []
    prediction_rows = []
    for fold, (train, test) in enumerate(split_storm_folds(storms), 1):
        if (len(set(storms[train])) != 20 or len(set(storms[test])) != 5
                or set(storms[train]) & set(storms[test])):
            raise ValueError("Each fold must hold out five complete storms.")
        centered_targets = center_events(targets[train], storms[train])
        scaler, target_scale, model, warning_count = fit_gpr(
            features[train], centered_targets)
        predicted = target_scale * model.predict(scaler.transform(features[test]))
        predicted = center_events(predicted, storms[test])
        held_out[test] = predicted
        test_rows = [rows[int(index)] for index in test]
        baseline = score(test_rows, np.zeros(len(test)))
        corrected = score(test_rows, predicted)
        scales = model.kernel_.k1.k2.length_scale
        fold_rows.append((fold, len(train), len(test), *baseline, *corrected,
                          *map(float, scales), warning_count, version))
        prediction_rows.extend((row["storm_id"], row["time_us"], row["grid_index"],
                                fold, *row["features"], row["rho_m1_kg_m3"],
                                row["rho_l2_kg_m3"], row["target_log_residual"],
                                float(value), row["rho_m1_kg_m3"] * math.exp(value), version)
                               for row, value in zip(test_rows, predicted, strict=True))
        print(f"Fold {fold}: M1 shape {baseline[1]:.6f}, GP shape {corrected[1]:.6f}; "
              f"M1 total {baseline[0]:.6f}, GP total {corrected[0]:.6f}", flush=True)
    if not np.isfinite(held_out).all():
        raise ValueError("Every test orbit must have a prediction.")
    event_rows = []
    for storm in sorted(set(storms)):
        indices = np.flatnonzero(storms == storm)
        event = [rows[int(index)] for index in indices]
        baseline = score(event, np.zeros(len(event)))
        corrected = score(event, held_out[indices])
        event_rows.append((storm, len(event), *baseline, *corrected, version))
    baseline = score(rows, np.zeros(len(rows)))
    corrected = score(rows, held_out)
    summary = (len(rows), *baseline, *corrected,
               sum(item[6] < item[3] for item in event_rows), version)
    return {"predictions": prediction_rows, "folds": fold_rows,
            "events": event_rows, "summary": summary}


def write_sqlite(result: dict) -> None:
    """Input: held-out GP result. Output: atomic, non-overwriting Trial 11 SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE prediction (
                    storm_id TEXT NOT NULL,time_us INTEGER NOT NULL,grid_index INTEGER NOT NULL,
                    fold_index INTEGER NOT NULL,days_from_t0 REAL NOT NULL,
                    log_m1 REAL NOT NULL,relative_log_m1 REAL NOT NULL,
                    centered_log_slope REAL NOT NULL,rho_m1_kg_m3 REAL NOT NULL,
                    rho_l2_kg_m3 REAL NOT NULL,actual_log_residual REAL NOT NULL,
                    predicted_shape_residual REAL NOT NULL,rho_gp_kg_m3 REAL NOT NULL,
                    algorithm_version TEXT NOT NULL,PRIMARY KEY(storm_id,time_us)
                );
                CREATE TABLE fold_metric (
                    fold_index INTEGER PRIMARY KEY,train_count INTEGER NOT NULL,
                    test_count INTEGER NOT NULL,m1_total_rmse REAL NOT NULL,
                    m1_shape_rmse REAL NOT NULL,m1_change_rmse REAL NOT NULL,
                    gp_total_rmse REAL NOT NULL,gp_shape_rmse REAL NOT NULL,
                    gp_change_rmse REAL NOT NULL,length_scale_time REAL NOT NULL,
                    length_scale_log_m1 REAL NOT NULL,length_scale_relative_m1 REAL NOT NULL,
                    length_scale_slope REAL NOT NULL,warning_count INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE event_metric (
                    storm_id TEXT PRIMARY KEY,test_count INTEGER NOT NULL,
                    m1_total_rmse REAL NOT NULL,m1_shape_rmse REAL NOT NULL,
                    m1_change_rmse REAL NOT NULL,gp_total_rmse REAL NOT NULL,
                    gp_shape_rmse REAL NOT NULL,gp_change_rmse REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE summary (
                    test_count INTEGER NOT NULL,m1_total_rmse REAL NOT NULL,
                    m1_shape_rmse REAL NOT NULL,m1_change_rmse REAL NOT NULL,
                    gp_total_rmse REAL NOT NULL,gp_shape_rmse REAL NOT NULL,
                    gp_change_rmse REAL NOT NULL,improved_shape_storms INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE metadata (name TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            database.executemany("INSERT INTO prediction VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 result["predictions"])
            database.executemany("INSERT INTO fold_metric VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 result["folds"])
            database.executemany("INSERT INTO event_metric VALUES (?,?,?,?,?,?,?,?,?)",
                                 result["events"])
            database.execute("INSERT INTO summary VALUES (?,?,?,?,?,?,?,?,?)", result["summary"])
            database.executemany("INSERT INTO metadata VALUES (?,?)", {
                "feature_names": ",".join(FEATURE_NAMES),
                "training_target": "log(L2/M1) minus each training storm's mean",
                "test_correction": "predicted shape minus its test storm mean; no test L2",
                "split": "five whole-storm 20/5 folds, seed 20261030",
                "source": str(M1),
            }.items())
            if (database.execute("SELECT count(*) FROM prediction").fetchone()[0]
                    != result["summary"][0]
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Trial 11 SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: Phase 3 M1 and historical L2. Output: Trial 11 held-out SQLite."""
    rows = build_feature_rows(build_triplets(load_anchors()), load_event_times())
    if len(rows) != 2235 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Expected 2,235 valid centers across 25 storms.")
    result = evaluate(rows, VERSION)
    write_sqlite(result)
    print(f"Overall M1 shape {result['summary'][2]:.6f}, "
          f"GP shape {result['summary'][5]:.6f}, "
          f"improved storms {result['summary'][7]}/25")


if __name__ == "__main__":
    main()
