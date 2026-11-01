"""Evaluate GPR correction with the three fixed Phase 5 V2 features."""

import math
import sqlite3

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF
from sklearn.preprocessing import StandardScaler

from prep_storm_r_gpr import ROOT
from prep_storm_r_phase3_trials import quiet_group_folds
from prep_storm_r_quiet_window_trials import load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_selected_gpr_v18.sqlite"
FEATURES = ("r_phase3", "prequiet_sme_mean_nt", "quiet_f107a_last81_sfu")
AMPLITUDE_R = 0.10
NOISE_STD_R = 0.10


def predict_delta(features: np.ndarray, targets: np.ndarray,
                  split: tuple[np.ndarray, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Input: [event, feature], delta-R, 20/5 indices. Output: train/test delta-R."""
    train, test = split
    scaler = StandardScaler().fit(features[train])
    kernel = ConstantKernel(AMPLITUDE_R ** 2, constant_value_bounds="fixed") * RBF(
        1.0, length_scale_bounds="fixed")
    model = GaussianProcessRegressor(kernel=kernel, alpha=NOISE_STD_R ** 2,
                                     normalize_y=False, optimizer=None)
    model.fit(scaler.transform(features[train]), targets[train])
    return (model.predict(scaler.transform(features[train])),
            model.predict(scaler.transform(features[test])))


def evaluate(rows: list[dict]) -> tuple[list[tuple], list[tuple]]:
    """Input: 25 labeled events. Output: five fold scores and 25 held-out predictions."""
    if len(rows) != 25 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Expected 25 distinct storms.")
    features = np.array([[row[name] for name in FEATURES] for row in rows], dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("Feature matrix has missing or invalid values.")
    targets = np.array([row["r_fit"] - row["r_phase3"] for row in rows])
    folds = []
    predictions = []
    for fold_index, test in enumerate(quiet_group_folds(rows, np.arange(25), 5), 1):
        train = np.setdiff1d(np.arange(25), test)
        train_pred, test_pred = predict_delta(features, targets, (train, test))
        folds.append((fold_index,
                      math.sqrt(float(np.mean((targets[train] - train_pred) ** 2))),
                      math.sqrt(float(np.mean((targets[test] - test_pred) ** 2))),
                      math.sqrt(float(np.mean(targets[train] ** 2))),
                      math.sqrt(float(np.mean(targets[test] ** 2)))))
        for index, correction in zip(test, test_pred, strict=True):
            row = rows[int(index)]
            r_pred = row["r_phase3"] + float(correction)
            if not 0 < r_pred < 2:
                raise ValueError(f"Invalid predicted R: {row['storm_id']}")
            predictions.append((row["storm_id"], fold_index, row["r_phase3"],
                                row["r_fit"], r_pred, row["prequiet_sme_mean_nt"],
                                row["quiet_f107a_last81_sfu"]))
    return folds, predictions


def save_results(folds: list[tuple], predictions: list[tuple]) -> None:
    """Input: fold scores and held-out predictions. Output: new SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE fold_score (
                fold_index INTEGER PRIMARY KEY, train_rmse_r REAL NOT NULL,
                five_event_rmse_r REAL NOT NULL, baseline_train_rmse_r REAL NOT NULL,
                baseline_five_event_rmse_r REAL NOT NULL
            );
            CREATE TABLE heldout_prediction (
                storm_id TEXT PRIMARY KEY, fold_index INTEGER NOT NULL,
                r_phase3 REAL NOT NULL, r_fit REAL NOT NULL, r_pred REAL NOT NULL,
                prequiet_sme_mean_nt REAL NOT NULL,
                quiet_f107a_last81_sfu REAL NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO fold_score VALUES (?,?,?,?,?)", folds)
        database.executemany("INSERT INTO heldout_prediction VALUES (?,?,?,?,?,?,?)",
                             predictions)
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit-r_phase3"),
            ("features", ",".join(FEATURES)),
            ("model", "zero-mean GPR; train-only standardized RBF length scale=1"),
            ("amplitude_r", str(AMPLITUDE_R)),
            ("noise_std_r", str(NOISE_STD_R)),
            ("split", "five 20/5 folds; shared Phase 3 quiet windows intact"),
            ("score_limit", "features were selected using these same 25 events"),
        ])
        counts = database.execute("""
            SELECT count(*),min(n),max(n) FROM (
                SELECT fold_index,count(*) n FROM heldout_prediction GROUP BY fold_index)
        """).fetchone()
        if (counts != (5, 5, 5) or len(predictions) != 25
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
            raise ValueError("Selected GPR SQLite audit failed.")


def main() -> None:
    """Input: Phase 3/4 V2 events. Output: fixed-feature GPR SQLite."""
    folds, predictions = evaluate(load_quiet_features())
    save_results(folds, predictions)
    print(f"selected GPR: train RMSE mean={np.mean([row[1] for row in folds]):.6f}; "
          f"five-event RMSE mean={np.mean([row[2] for row in folds]):.6f}; "
          f"Phase 3 baseline={np.mean([row[4] for row in folds]):.6f}")


if __name__ == "__main__":
    main()
