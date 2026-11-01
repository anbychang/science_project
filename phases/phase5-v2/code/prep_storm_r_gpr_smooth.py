"""Tune GPR smoothness using only the 20 training events in each fold."""

import math
import sqlite3
from contextlib import closing

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF
from sklearn.preprocessing import StandardScaler

from prep_storm_r_gpr import ROOT
from prep_storm_r_phase3_trials import quiet_group_folds
from prep_storm_r_quiet_window_trials import load_quiet_features
from prep_storm_r_selected_gpr import FEATURES


SOURCE = ROOT / "data/sqlite/phase4_v2_r_targets_v1.sqlite"
OUTPUT = ROOT / "data/sqlite/storm_r_gpr_smooth_v19.sqlite"
AMPLITUDE_R = 0.10
SETTINGS = ((1.0, 0.10), (1.0, 0.20), (2.0, 0.10),
            (2.0, 0.20), (4.0, 0.10), (4.0, 0.20))


def load_rows() -> list[dict]:
    """Input: event features and saved Phase 4 V2 labels. Output: 25 joined rows."""
    rows = load_quiet_features()
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as database:
        targets = dict(database.execute(
            "SELECT storm_id,r_fit FROM phase4_v2_r_target"))
    if len(targets) != 25 or {row["storm_id"] for row in rows} != targets.keys():
        raise ValueError("Phase 4 V2 target snapshot does not match feature events.")
    for row in rows:
        row["r_fit"] = targets[row["storm_id"]]
    return rows


def fit_predict(data: dict, split: tuple[np.ndarray, np.ndarray],
                setting: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """Input: {features, targets}, train/test indices, length/noise. Output: delta-R arrays."""
    train, test = split
    features = data["features"]
    targets = data["targets"]
    length_scale, noise_std_r = setting
    scaler = StandardScaler().fit(features[train])
    kernel = ConstantKernel(AMPLITUDE_R ** 2, constant_value_bounds="fixed") * RBF(
        length_scale, length_scale_bounds="fixed")
    model = GaussianProcessRegressor(kernel=kernel, alpha=noise_std_r ** 2,
                                     normalize_y=False, optimizer=None)
    model.fit(scaler.transform(features[train]), targets[train])
    return (model.predict(scaler.transform(features[train])),
            model.predict(scaler.transform(features[test])))


def choose_setting(data: dict, rows: list[dict], outer_train: np.ndarray) -> tuple:
    """Input: event data, rows, 20 indices. Output: best setting and inner scores."""
    inner_folds = quiet_group_folds(rows, outer_train, 4)
    scores = []
    for setting in SETTINGS:
        fold_rmse = []
        for test in inner_folds:
            train = np.setdiff1d(outer_train, test)
            _, predicted = fit_predict(data, (train, test), setting)
            fold_rmse.append(math.sqrt(float(np.mean(
                (data["targets"][test] - predicted) ** 2))))
        scores.append((setting[0], setting[1], float(np.mean(fold_rmse))))
    selected = min(scores, key=lambda row: (row[2], row[0], row[1]))
    return selected, scores


def evaluate(rows: list[dict]) -> dict:
    """Input: 25 labeled events. Output: nested 20/5 GPR scores and predictions."""
    if len(rows) != 25 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Expected 25 distinct storms.")
    features = np.array([[row[name] for name in FEATURES] for row in rows], dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("Feature matrix has missing or invalid values.")
    targets = np.array([row["r_fit"] - row["r_phase3"] for row in rows])
    data = {"features": features, "targets": targets}
    folds = []
    candidates = []
    predictions = []
    for fold_index, test in enumerate(quiet_group_folds(rows, np.arange(25), 5), 1):
        train = np.setdiff1d(np.arange(25), test)
        selected, scores = choose_setting(data, rows, train)
        candidates.extend((fold_index, length, noise, score,
                           int((length, noise) == selected[:2]))
                          for length, noise, score in scores)
        train_pred, test_pred = fit_predict(data, (train, test), selected[:2])
        folds.append((fold_index, selected[0], selected[1], selected[2],
                      math.sqrt(float(np.mean((targets[train] - train_pred) ** 2))),
                      math.sqrt(float(np.mean((targets[test] - test_pred) ** 2))),
                      math.sqrt(float(np.mean(targets[test] ** 2)))))
        for index, correction in zip(test, test_pred, strict=True):
            row = rows[int(index)]
            r_pred = row["r_phase3"] + float(correction)
            if not 0 < r_pred < 2:
                raise ValueError(f"Invalid predicted R: {row['storm_id']}")
            predictions.append((row["storm_id"], fold_index, row["r_phase3"],
                                row["r_fit"], r_pred))
    return {"folds": folds, "candidates": candidates,
            "predictions": predictions}


def save_results(result: dict) -> None:
    """Input: nested GPR results. Output: new SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE fold_score (
                fold_index INTEGER PRIMARY KEY, length_scale REAL NOT NULL,
                noise_std_r REAL NOT NULL, inner_rmse_r REAL NOT NULL,
                train_rmse_r REAL NOT NULL, five_event_rmse_r REAL NOT NULL,
                baseline_five_event_rmse_r REAL NOT NULL
            );
            CREATE TABLE candidate_score (
                fold_index INTEGER NOT NULL, length_scale REAL NOT NULL,
                noise_std_r REAL NOT NULL, inner_rmse_r REAL NOT NULL,
                selected INTEGER NOT NULL,
                PRIMARY KEY(fold_index,length_scale,noise_std_r)
            );
            CREATE TABLE heldout_prediction (
                storm_id TEXT PRIMARY KEY, fold_index INTEGER NOT NULL,
                r_phase3 REAL NOT NULL, r_fit REAL NOT NULL, r_pred REAL NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO fold_score VALUES (?,?,?,?,?,?,?)",
                             result["folds"])
        database.executemany("INSERT INTO candidate_score VALUES (?,?,?,?,?)",
                             result["candidates"])
        database.executemany("INSERT INTO heldout_prediction VALUES (?,?,?,?,?)",
                             result["predictions"])
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target_source", str(SOURCE)),
            ("features", ",".join(FEATURES)),
            ("target", "r_fit-r_phase3"),
            ("model", "zero-mean RBF GPR; fixed amplitude 0.10"),
            ("selection", "six settings scored by four inner 15/5 folds of outer 20"),
            ("score_limit", "three features were previously chosen using these 25 events"),
        ])
        if (len(result["folds"]) != 5 or len(result["candidates"]) != 30
                or len(result["predictions"]) != 25
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
            raise ValueError("GPR smoothing SQLite audit failed.")


def main() -> None:
    """Input: fixed features and saved Phase 4 V2 labels. Output: GPR SQLite."""
    result = evaluate(load_rows())
    save_results(result)
    folds = result["folds"]
    print("selected settings", [(row[1], row[2]) for row in folds])
    print(f"smoothed GPR: train RMSE mean={np.mean([row[4] for row in folds]):.6f}; "
          f"five-event RMSE mean={np.mean([row[5] for row in folds]):.6f}; "
          f"Phase 3 baseline={np.mean([row[6] for row in folds]):.6f}")


if __name__ == "__main__":
    main()
