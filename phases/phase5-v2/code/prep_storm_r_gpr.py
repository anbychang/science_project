"""Predict Phase 4 V2 event R values from storm-level geomagnetic features."""

import math
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler


ROOT = Path("phases/phase5-v2")
SOURCE = Path("phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite")
WEATHER = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
OUTPUT = ROOT / "data/sqlite/storm_r_gpr_v1.sqlite"
ALGORITHM_VERSION = "storm_r_gpr_v1"
FOLD_COUNT = 5
RANDOM_SEED = 42


def load_storm_rows() -> tuple[list[dict], float, float]:
    """Input: Phase 4 V2 event R and Phase 2 storm minutes. Output: rows, tau h, G 1/nT."""
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    weather_uri = f"file:{WEATHER.resolve().as_posix()}?mode=ro"
    with (closing(sqlite3.connect(source_uri, uri=True)) as source,
          closing(sqlite3.connect(weather_uri, uri=True)) as weather):
        labels = source.execute("""
            SELECT storm_id,r_fit,tau_hours,gain_per_nt FROM phase4_v2_events
            ORDER BY storm_id
        """).fetchall()
        rows = []
        for storm_id, r_fit, tau_hours, gain_per_nt in labels:
            if tau_hours != 4.75 or gain_per_nt <= 0 or r_fit <= 0:
                raise ValueError(f"Invalid Phase 4 V2 label: {storm_id}")
            peak_sme, min_symh, minute_count = weather.execute("""
                SELECT max(sme_nt),min(symh_nt),count(*)
                FROM storm_minute_feature_v5 WHERE storm_id=?
            """, (storm_id,)).fetchone()
            if minute_count < 1 or peak_sme is None or min_symh is None:
                raise ValueError(f"Incomplete geomagnetic features: {storm_id}")
            rows.append({"storm_id": storm_id, "peak_sme_nt": float(peak_sme),
                         "min_symh_nt": float(min_symh), "r_fit": r_fit,
                         "log_r_fit": math.log(r_fit)})
    if len(rows) != 25 or len({(label[2], label[3]) for label in labels}) != 1:
        raise ValueError("Expected 25 Phase 4 V2 storms.")
    return rows, labels[0][2], labels[0][3]


def predict_held_out(rows: list[dict]) -> list[dict]:
    """Input: 25 event labels and geomagnetic features. Output: held-out predictions."""
    if len(rows) != 25 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Expected 25 distinct storms.")
    features = np.array([[row["peak_sme_nt"], row["min_symh_nt"]] for row in rows])
    targets = np.array([row["log_r_fit"] for row in rows])
    folds = np.random.default_rng(RANDOM_SEED).permutation(len(rows)).reshape(FOLD_COUNT, 5)
    results = []
    for fold_index, test_indices in enumerate(folds, 1):
        train_indices = np.setdiff1d(np.arange(len(rows)), test_indices)
        scaler = StandardScaler().fit(features[train_indices])
        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * RBF(1.0, (1e-2, 1e2)) + WhiteKernel(0.1, (1e-5, 1e1))
        model = GaussianProcessRegressor(kernel=kernel, normalize_y=True, random_state=RANDOM_SEED)
        model.fit(scaler.transform(features[train_indices]), targets[train_indices])
        means, stds = model.predict(scaler.transform(features[test_indices]), return_std=True)
        baseline = float(np.mean(targets[train_indices]))
        for index, mean, std in zip(test_indices, means, stds, strict=True):
            results.append({
                **rows[int(index)],
                "fold_index": fold_index,
                "r_pred": math.exp(float(mean)),
                "r_pred_std_log": float(std),
                "r_train_mean": math.exp(baseline),
            })
    return sorted(results, key=lambda row: row["storm_id"])


def save_results(rows: list[dict], tau_hours: float, gain_per_nt: float) -> None:
    """Input: 25 held-out rows and Phase 4 V2 parameters. Output: new SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE storm_r_prediction (
                storm_id TEXT PRIMARY KEY, fold_index INTEGER NOT NULL,
                peak_sme_nt REAL NOT NULL, min_symh_nt REAL NOT NULL,
                r_fit REAL NOT NULL, log_r_fit REAL NOT NULL,
                r_pred REAL NOT NULL, r_pred_std_log REAL NOT NULL,
                r_train_mean REAL NOT NULL, algorithm_version TEXT NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO storm_r_prediction VALUES (?,?,?,?,?,?,?,?,?,?)", (
            (row["storm_id"], row["fold_index"], row["peak_sme_nt"], row["min_symh_nt"],
             row["r_fit"], row["log_r_fit"], row["r_pred"], row["r_pred_std_log"],
             row["r_train_mean"], ALGORITHM_VERSION) for row in rows
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("source", str(SOURCE)), ("tau_hours", str(tau_hours)),
            ("gain_per_nt", str(gain_per_nt)), ("fold_count", str(FOLD_COUNT)),
            ("random_seed", str(RANDOM_SEED)),
            ("feature_window", "whole Phase 2 storm minute window; available after event"),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Phase 5 V2 SQLite integrity check failed.")


def main() -> None:
    """Input: read-only Phase 4 V2 and Phase 2/3 data. Output: Phase 5 V2 SQLite."""
    labels, tau_hours, gain_per_nt = load_storm_rows()
    rows = predict_held_out(labels)
    save_results(rows, tau_hours, gain_per_nt)
    actual = np.array([row["log_r_fit"] for row in rows])
    predicted = np.log([row["r_pred"] for row in rows])
    baseline = np.log([row["r_train_mean"] for row in rows])
    print(f"25 held-out storms; log-R RMSE GPR={np.sqrt(np.mean((actual-predicted)**2)):.6f}, "
          f"train-mean={np.sqrt(np.mean((actual-baseline)**2)):.6f}")


if __name__ == "__main__":
    main()
