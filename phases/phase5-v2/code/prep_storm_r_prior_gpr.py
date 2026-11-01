"""Test zero-mean GPR corrections around the Phase 3 R prior."""

import math
import sqlite3

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF
from sklearn.preprocessing import StandardScaler

from prep_storm_r_gpr import ROOT
from prep_storm_r_phase3_trials import quiet_group_folds
from prep_storm_r_quiet_window_trials import load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_prior_gpr_v9.sqlite"
ALGORITHM_VERSION = "storm_r_prior_gpr_v9"
NOISE_STD_R = 0.10
FEATURE_SETS = {
    "quiet_h": ("quiet_mean_h_nt",),
    "quiet_h_distance": ("quiet_mean_h_nt", "distance_log_days"),
    "quiet_h_date": ("quiet_mean_h_nt", "quiet_day"),
    "phase3_r_distance": ("r_phase3", "distance_log_days"),
}
AMPLITUDES_R = (0.05, 0.10)


def predict_delta(model_data: dict, split: tuple[np.ndarray, np.ndarray],
                  amplitude_r: float) -> np.ndarray:
    """Input: {features, targets}, train/test indices and amplitude. Output: test delta-R."""
    train, test = split
    features = model_data["features"]
    targets = model_data["targets"]
    scaler = StandardScaler().fit(features[train])
    kernel = ConstantKernel(amplitude_r ** 2, constant_value_bounds="fixed") * RBF(
        1.0, length_scale_bounds="fixed")
    model = GaussianProcessRegressor(kernel=kernel, alpha=NOISE_STD_R ** 2,
                                     normalize_y=False, optimizer=None)
    model.fit(scaler.transform(features[train]), targets[train])
    return model.predict(scaler.transform(features[test]))


def evaluate(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Input: 25 quiet-window events. Output: group-held-out corrections and inner scores."""
    targets = np.array([row["r_fit"] - row["r_phase3"] for row in rows])
    model_data = {name: {"features": np.array([[row[field] for field in fields]
                                              for row in rows]), "targets": targets}
                  for name, fields in FEATURE_SETS.items()}
    predictions = []
    scores = []
    for fold_index, test in enumerate(quiet_group_folds(rows, np.arange(25), 5), 1):
        train = np.setdiff1d(np.arange(25), test)
        inner_folds = quiet_group_folds(rows, train, 4)
        candidates = []
        for name, data in model_data.items():
            for amplitude in AMPLITUDES_R:
                errors = []
                for inner_test in inner_folds:
                    inner_train = np.setdiff1d(train, inner_test)
                    mean = predict_delta(data, (inner_train, inner_test), amplitude)
                    errors.extend((targets[inner_test] - mean) ** 2)
                candidates.append((name, amplitude, math.sqrt(float(np.mean(errors)))))
        selected = min(candidates, key=lambda candidate: candidate[2])
        means = predict_delta(model_data[selected[0]], (train, test), selected[1])
        scores.extend({"fold_index": fold_index, "feature_set": name,
                       "amplitude_r": amplitude, "inner_rmse_delta_r": score,
                       "selected": int((name, amplitude) == selected[:2])}
                      for name, amplitude, score in candidates)
        for index, delta_r in zip(test, means, strict=True):
            row = rows[int(index)]
            r_pred = row["r_phase3"] + float(delta_r)
            if not 0 < r_pred < 2:
                raise ValueError(f"Invalid R correction: {row['storm_id']}")
            predictions.append({"storm_id": row["storm_id"],
                                "r_phase3": row["r_phase3"], "r_fit": row["r_fit"],
                                "r_pred": r_pred, "delta_r_pred": float(delta_r),
                                "quiet_mean_h_nt": row["quiet_mean_h_nt"],
                                "distance_days": row["distance_days"],
                                "quiet_end_exclusive_time_us": row["quiet_end_exclusive_time_us"],
                                "fold_index": fold_index, "feature_set": selected[0],
                                "amplitude_r": selected[1]})
    return sorted(predictions, key=lambda row: row["storm_id"]), scores


def save_results(predictions: list[dict], scores: list[dict]) -> None:
    """Input: predictions and inner scores. Output: new zero-prior trial SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE storm_r_prediction (
                storm_id TEXT PRIMARY KEY, r_phase3 REAL NOT NULL, r_fit REAL NOT NULL,
                r_pred REAL NOT NULL, delta_r_pred REAL NOT NULL,
                quiet_mean_h_nt REAL NOT NULL, distance_days REAL NOT NULL,
                quiet_end_exclusive_time_us INTEGER NOT NULL,
                fold_index INTEGER NOT NULL, feature_set TEXT NOT NULL,
                amplitude_r REAL NOT NULL, algorithm_version TEXT NOT NULL
            );
            CREATE TABLE feature_selection (
                fold_index INTEGER NOT NULL, feature_set TEXT NOT NULL,
                amplitude_r REAL NOT NULL, inner_rmse_delta_r REAL NOT NULL,
                selected INTEGER NOT NULL, algorithm_version TEXT NOT NULL,
                PRIMARY KEY(fold_index,feature_set,amplitude_r)
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO storm_r_prediction VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            (row["storm_id"], row["r_phase3"], row["r_fit"], row["r_pred"],
             row["delta_r_pred"], row["quiet_mean_h_nt"], row["distance_days"],
             row["quiet_end_exclusive_time_us"], row["fold_index"],
             row["feature_set"], row["amplitude_r"], ALGORITHM_VERSION)
            for row in predictions
        ))
        database.executemany("INSERT INTO feature_selection VALUES (?,?,?,?,?,?)", (
            (row["fold_index"], row["feature_set"], row["amplitude_r"],
             row["inner_rmse_delta_r"], row["selected"], ALGORITHM_VERSION)
            for row in scores
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit - r_phase3"),
            ("gp_prior", "zero mean delta-R; fixed RBF scale=1 after train-only standardization"),
            ("noise_std_r", str(NOISE_STD_R)),
            ("split", "5 outer 20/5, 4 inner 15/5; repeated quiet runs intact"),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Zero-prior trial SQLite integrity check failed.")


def main() -> None:
    """Input: Phase 2/3 and Phase 4 V2 sources. Output: Phase 5 V2 prior-GPR SQLite."""
    predictions, scores = evaluate(load_quiet_features())
    save_results(predictions, scores)
    actual = np.array([row["r_fit"] for row in predictions])
    original = np.array([row["r_phase3"] for row in predictions])
    predicted = np.array([row["r_pred"] for row in predictions])
    print(f"MAE original={np.mean(abs(actual-original)):.6f}; "
          f"zero-prior GPR={np.mean(abs(actual-predicted)):.6f}")


if __name__ == "__main__":
    main()
