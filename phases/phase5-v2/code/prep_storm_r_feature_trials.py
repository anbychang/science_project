"""Choose storm-level GPR features inside each 20-storm training fold."""

import math
import sqlite3
import warnings
from contextlib import closing
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler

from prep_storm_r_gpr import RANDOM_SEED, ROOT, WEATHER, load_storm_rows


OUTPUT = ROOT / "data/sqlite/storm_r_feature_trials_v2.sqlite"
ALGORITHM_VERSION = "storm_r_feature_trials_v2"
WINDOW_US = 24 * 60 * 60 * 1_000_000
FEATURE_SETS = {
    "sme_peak": ("peak_sme_nt",),
    "sme_integral": ("sme_excess_nt_h",),
    "symh_min": ("min_symh_nt",),
    "sme_peak_integral": ("peak_sme_nt", "sme_excess_nt_h"),
    "sme_symh": ("peak_sme_nt", "min_symh_nt"),
    "sme_f107a": ("sme_excess_nt_h", "f107a_sfu"),
}


def load_event_features() -> list[dict]:
    """Input: Phase 4 V2 labels and Phase 2 minutes. Output: 25 event feature records."""
    labels, _, _ = load_storm_rows()
    uri = f"file:{WEATHER.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = []
        for label in labels:
            storm_id = label["storm_id"]
            values = database.execute("""
                SELECT max(f.sme_nt),min(f.symh_nt),
                       sum(max(f.sme_nt - 65.0,0.0))/60.0,
                       avg(f.f107a_sfu),count(*)
                FROM storm_minute_feature_v5 AS f
                JOIN storm_event_t0_phase_v5 AS e ON e.storm_id=f.storm_id
                WHERE f.storm_id=? AND f.source_time_us>=e.t0_time_us-?
                  AND f.source_time_us<e.t0_time_us+?
            """, (storm_id, WINDOW_US, WINDOW_US)).fetchone()
            peak, minimum, integral, f107a, count = values
            if count != 2880 or any(value is None for value in values[:4]):
                raise ValueError(f"Incomplete 48-hour feature window: {storm_id}")
            rows.append({**label, "peak_sme_nt": peak, "min_symh_nt": minimum,
                         "sme_excess_nt_h": integral, "f107a_sfu": f107a})
    return rows


def fit_predict(train: np.ndarray, test: np.ndarray,
                model_data: dict) -> tuple[np.ndarray, np.ndarray]:
    """Input: train/test indices and {features, targets}. Output: mean/std log-R."""
    values = model_data["features"]
    targets = model_data["targets"]
    scaler = StandardScaler().fit(values[train])
    kernel = ConstantKernel(1.0, (1e-3, 1e3)) * RBF(1.0, (1e-2, 1e2)) + WhiteKernel(0.1, (1e-5, 1e1))
    model = GaussianProcessRegressor(kernel=kernel, normalize_y=True, random_state=RANDOM_SEED)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(scaler.transform(values[train]), targets[train])
    return model.predict(scaler.transform(values[test]), return_std=True)


def select_features(train: np.ndarray, model_data: dict) -> tuple[str, list[tuple[str, float]]]:
    """Input: 20 outer-train indices and {feature set: arrays}. Output: choice and scores."""
    inner_folds = np.array_split(train, 4)
    scores = []
    for name in model_data:
        targets = model_data[name]["targets"]
        squared_errors = []
        for test in inner_folds:
            fit = np.setdiff1d(train, test)
            mean, _ = fit_predict(fit, test, model_data[name])
            squared_errors.extend((targets[test] - mean) ** 2)
        scores.append((name, math.sqrt(float(np.mean(squared_errors)))))
    return min(scores, key=lambda item: item[1])[0], scores


def evaluate(rows: list[dict], feature_sets: dict = FEATURE_SETS) -> tuple[list[dict], list[dict]]:
    """Input: 25 labeled events and candidate sets. Output: predictions and inner scores."""
    if len(rows) != 25 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Expected 25 distinct storms.")
    targets = np.array([row["log_r_fit"] for row in rows])
    model_data = {
        name: {"features": np.array([[row[field] for field in fields] for row in rows]),
               "targets": targets}
        for name, fields in feature_sets.items()
    }
    folds = np.random.default_rng(RANDOM_SEED).permutation(25).reshape(5, 5)
    predictions = []
    selection_scores = []
    for fold_index, test in enumerate(folds, 1):
        train = np.setdiff1d(np.arange(25), test)
        selected, scores = select_features(train, model_data)
        mean, std = fit_predict(train, test, model_data[selected])
        baseline = float(np.mean(targets[train]))
        selection_scores.extend({"fold_index": fold_index, "feature_set": name,
                                 "inner_rmse_log_r": score, "selected": int(name == selected)}
                                for name, score in scores)
        predictions.extend({"storm_id": rows[int(index)]["storm_id"],
                            "fold_index": fold_index, "feature_set": selected,
                            "r_fit": rows[int(index)]["r_fit"], "r_pred": math.exp(float(value)),
                            "r_pred_std_log": float(uncertainty),
                            "r_train_mean": math.exp(baseline)}
                           for index, value, uncertainty in zip(test, mean, std, strict=True))
    return sorted(predictions, key=lambda row: row["storm_id"]), selection_scores


def save_results(predictions: list[dict], scores: list[dict], settings: dict) -> None:
    """Input: predictions, inner scores, output settings. Output: new SQLite tables."""
    output = settings["output"]
    version = settings["version"]
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output) as database:
        database.executescript("""
            CREATE TABLE storm_r_prediction (
                storm_id TEXT PRIMARY KEY, fold_index INTEGER NOT NULL,
                feature_set TEXT NOT NULL, r_fit REAL NOT NULL, r_pred REAL NOT NULL,
                r_pred_std_log REAL NOT NULL, r_train_mean REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE feature_selection (
                fold_index INTEGER NOT NULL, feature_set TEXT NOT NULL,
                inner_rmse_log_r REAL NOT NULL, selected INTEGER NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(fold_index,feature_set)
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO storm_r_prediction VALUES (?,?,?,?,?,?,?,?)", (
            (row["storm_id"], row["fold_index"], row["feature_set"], row["r_fit"],
             row["r_pred"], row["r_pred_std_log"], row["r_train_mean"], version)
            for row in predictions
        ))
        database.executemany("INSERT INTO feature_selection VALUES (?,?,?,?,?)", (
            (row["fold_index"], row["feature_set"], row["inner_rmse_log_r"],
             row["selected"], version) for row in scores
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("source", "Phase 4 V2 phase4_v2_events.r_fit"),
            ("feature_window", settings["window"]),
            ("selection", "4 inner folds of 5 train storms; 5 outer folds of 5 test storms"),
            ("random_seed", str(RANDOM_SEED)),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Phase 5 V2 feature-trial SQLite integrity check failed.")


def main() -> None:
    """Input: Phase 4 V2 and Phase 2 read-only SQLite. Output: feature-trial SQLite."""
    predictions, scores = evaluate(load_event_features())
    save_results(predictions, scores, {"output": OUTPUT, "version": ALGORITHM_VERSION,
                                       "window": "t0 +/- 24 h; 2880 one-minute rows"})
    actual = np.log([row["r_fit"] for row in predictions])
    predicted = np.log([row["r_pred"] for row in predictions])
    baseline = np.log([row["r_train_mean"] for row in predictions])
    print(f"nested GPR RMSE={np.sqrt(np.mean((actual-predicted)**2)):.6f}; "
          f"train mean={np.sqrt(np.mean((actual-baseline)**2)):.6f}")


if __name__ == "__main__":
    main()
