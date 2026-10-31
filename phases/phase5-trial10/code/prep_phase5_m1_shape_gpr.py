"""Test an M1-only three-feature GPR with whole-storm held-out folds."""

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
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from phases.phase5.code.calc_phase5_trial4_groupcv import split_storm_folds
from calc_m1_shape_features import build_triplets


ROOT = Path("phases/phase5-trial10")
PHASE = Path("phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite")
M1 = Path("phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
OUTPUT = ROOT / "data/sqlite/swarm_a_phase5_m1_shape_gpr_v1.sqlite"
VERSION = "phase5_trial10_m1_shape_gpr_v1"
FEATURE_NAMES = ("log_m1", "past_log_change", "centered_log_curvature")
GRID_TOLERANCE_RAD = 0.02 * math.pi


def load_anchors() -> list[dict]:
    """Input: read-only Phase 3 phase and M1 SQLite. Output: one valid M1/L2 anchor per orbit."""
    phase_uri = f"file:{PHASE.resolve().as_posix()}?mode=ro"
    m1_uri = f"file:{M1.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(phase_uri, uri=True)) as database:
        database.execute("ATTACH DATABASE ? AS m1", (m1_uri,))
        rows = database.execute("""
            SELECT phase.storm_id,phase.time_us,phase.u_rel_rad,
                   m1.rho_m1_pooled_phase_kg_m3,m1.rho_l2_phase_kg_m3
            FROM phase3_h_tau_minute AS phase
            JOIN m1.phase3_prediction_minute AS m1
              ON m1.storm_id=phase.storm_id AND m1.time_us=phase.time_us
            WHERE phase.phase_is_valid_80pct=1
            ORDER BY phase.storm_id,phase.time_us
        """).fetchall()
    selected = {}
    for storm_id, time_us, phase_rad, m1_density, l2_density in rows:
        grid_index = round(phase_rad / (2 * math.pi))
        distance = abs(phase_rad - 2 * math.pi * grid_index)
        if distance > GRID_TOLERANCE_RAD:
            continue
        key = (storm_id, grid_index)
        previous = selected.get(key)
        if previous is None or distance < previous[0]:
            selected[key] = (distance, {
                "storm_id": storm_id,
                "time_us": time_us,
                "grid_index": grid_index,
                "rho_m1_kg_m3": m1_density,
                "rho_l2_kg_m3": l2_density,
            })
    anchors = [selected[key][1] for key in sorted(selected)]
    if len(anchors) != 2295 or len({row["storm_id"] for row in anchors}) != 25:
        raise ValueError("Expected 2,295 M1 anchors across 25 storms.")
    return anchors


def log_rmse(actual: np.ndarray, estimate: np.ndarray) -> float:
    """Input: [actual log residual], [estimated log residual]. Output: log-density RMSE."""
    return float(np.sqrt(np.mean((actual - estimate) ** 2)))


def fit_fold(features: np.ndarray, targets: np.ndarray) -> tuple:
    """Input: [train x three M1 features], [train log residual]. Output: X scaler, y scale, GPR, warnings."""
    x_scaler = StandardScaler().fit(features)
    y_scale = float(np.std(targets))
    if y_scale <= 0 or not np.isfinite(y_scale):
        raise ValueError("Training residual scale must be positive and finite.")
    kernel = (ConstantKernel(1.0, (1e-2, 1e2))
              * RBF(np.ones(3), (1e-2, 1e2))
              + WhiteKernel(0.1, (1e-3, 1.0)))
    model = GaussianProcessRegressor(
        kernel=kernel, alpha=1e-8, normalize_y=False,
        n_restarts_optimizer=0, random_state=20261030,
    )
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        model.fit(x_scaler.transform(features), targets / y_scale)
    warning_count = sum(isinstance(item.message, ConvergenceWarning) for item in emitted)
    return x_scaler, y_scale, model, warning_count


def evaluate(triplets: list[dict]) -> dict:
    """Input: [{three M1 features, historical L2 label}]. Output: held-out predictions and RMSE."""
    features = np.array([row["features"] for row in triplets])
    targets = np.array([row["target_log_residual"] for row in triplets])
    storm_ids = np.array([row["storm_id"] for row in triplets])
    held_out = np.full(len(triplets), np.nan)
    predictions = []
    fold_metrics = []
    for fold_index, (train, test) in enumerate(split_storm_folds(storm_ids), 1):
        train_storms = set(storm_ids[train])
        test_storms = set(storm_ids[test])
        if len(train_storms) != 20 or len(test_storms) != 5 or train_storms & test_storms:
            raise ValueError("A GPR fold must hold out five complete storms.")
        x_scaler, y_scale, model, warning_count = fit_fold(features[train], targets[train])
        means = y_scale * model.predict(x_scaler.transform(features[test]))
        held_out[test] = means
        for index, mean in zip(test, means, strict=True):
            row = triplets[int(index)]
            predictions.append((row["storm_id"], row["time_us"], row["grid_index"],
                                fold_index, *row["features"], row["rho_m1_kg_m3"],
                                row["rho_l2_kg_m3"], row["target_log_residual"],
                                float(mean), row["rho_m1_kg_m3"] * math.exp(mean), VERSION))
        scales = model.kernel_.k1.k2.length_scale
        fold_metrics.append((fold_index, len(train), len(test),
                             log_rmse(targets[test], np.zeros(len(test))),
                             log_rmse(targets[test], means), y_scale,
                             *map(float, scales), warning_count, VERSION))
        print(f"Fold {fold_index}: {len(train)} train, {len(test)} test, "
              f"M1 {fold_metrics[-1][3]:.6f}, GPR {fold_metrics[-1][4]:.6f}", flush=True)
    if not np.isfinite(held_out).all() or len(predictions) != len(triplets):
        raise ValueError("Every triplet must receive one held-out prediction.")
    event_metrics = []
    for storm_id in sorted(set(storm_ids)):
        mask = storm_ids == storm_id
        event_metrics.append((storm_id, int(mask.sum()),
                              log_rmse(targets[mask], np.zeros(mask.sum())),
                              log_rmse(targets[mask], held_out[mask]), VERSION))
    summary = (len(triplets), log_rmse(targets, np.zeros(len(targets))),
               log_rmse(targets, held_out),
               sum(row[3] < row[2] for row in event_metrics), VERSION)
    return {"predictions": predictions, "fold_metrics": fold_metrics,
            "event_metrics": event_metrics, "summary": summary}


def write_sqlite(result: dict) -> None:
    """Input: held-out M1 GPR result. Output: atomic, non-overwriting Trial 10 SQLite."""
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
                    fold_index INTEGER NOT NULL,log_m1 REAL NOT NULL,
                    past_log_change REAL NOT NULL,centered_log_curvature REAL NOT NULL,
                    rho_m1_kg_m3 REAL NOT NULL,rho_l2_kg_m3 REAL NOT NULL,
                    actual_log_residual REAL NOT NULL,gpr_log_residual REAL NOT NULL,
                    rho_gpr_kg_m3 REAL NOT NULL,algorithm_version TEXT NOT NULL,
                    PRIMARY KEY(storm_id,time_us)
                );
                CREATE TABLE fold_metric (
                    fold_index INTEGER PRIMARY KEY,train_count INTEGER NOT NULL,
                    test_count INTEGER NOT NULL,m1_log_rmse REAL NOT NULL,
                    gpr_log_rmse REAL NOT NULL,train_target_scale REAL NOT NULL,
                    length_scale_log_m1 REAL NOT NULL,length_scale_past_change REAL NOT NULL,
                    length_scale_curvature REAL NOT NULL,warning_count INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE event_metric (
                    storm_id TEXT PRIMARY KEY,test_count INTEGER NOT NULL,
                    m1_log_rmse REAL NOT NULL,gpr_log_rmse REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE summary (
                    test_count INTEGER NOT NULL,m1_log_rmse REAL NOT NULL,
                    gpr_log_rmse REAL NOT NULL,improved_storm_count INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE metadata (name TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            database.executemany("INSERT INTO prediction VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 result["predictions"])
            database.executemany("INSERT INTO fold_metric VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 result["fold_metrics"])
            database.executemany("INSERT INTO event_metric VALUES (?,?,?,?,?)",
                                 result["event_metrics"])
            database.execute("INSERT INTO summary VALUES (?,?,?,?,?)", result["summary"])
            metadata = {
                "phase_source": str(PHASE),
                "m1_source": str(M1),
                "m1_column": "rho_m1_pooled_phase_kg_m3",
                "feature_names": ",".join(FEATURE_NAMES),
                "evaluation": "five whole-storm 20/5 folds; historical L2 used only as labels and scores",
                "input_scaling": "train-fold StandardScaler for X; train-fold target std for y; no y centering",
            }
            database.executemany("INSERT INTO metadata VALUES (?,?)", metadata.items())
            if (database.execute("SELECT count(*) FROM prediction").fetchone()[0]
                    != result["summary"][0]
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Trial 10 SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: Phase 3 M1 and historical L2. Output: held-out Trial 10 SQLite."""
    triplets = build_triplets(load_anchors())
    if len({row["storm_id"] for row in triplets}) != 25:
        raise ValueError("Triplets must cover all 25 storms.")
    print(f"Training on {len(triplets)} valid three-orbit centers", flush=True)
    result = evaluate(triplets)
    write_sqlite(result)
    print(f"Combined M1 {result['summary'][1]:.6f}, "
          f"GPR {result['summary'][2]:.6f}, "
          f"improved storms {result['summary'][3]}/25", flush=True)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
