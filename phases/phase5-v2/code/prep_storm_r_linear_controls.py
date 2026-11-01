"""Check whether quiet-window response survives simple linear controls."""

import math
import sqlite3

import numpy as np

from prep_storm_r_gpr import ROOT
from prep_storm_r_quiet_window_trials import load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_linear_controls_v12.sqlite"
ALGORITHM_VERSION = "storm_r_linear_controls_v12"
MODELS = {
    "abs_h": ("quiet_max_abs_h_nt",),
    "abs_h_date": ("quiet_max_abs_h_nt", "quiet_day"),
    "abs_h_phase3_r": ("quiet_max_abs_h_nt", "r_phase3"),
    "abs_h_distance": ("quiet_max_abs_h_nt", "distance_days"),
    "abs_h_sme": ("quiet_max_abs_h_nt", "quiet_mean_sme_nt"),
    "log_ratio_abs_h": ("quiet_max_abs_h_nt",),
}


def fit_coefficients(features: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Input: [events x one/two factors], [delta-R]. Output: [intercept, slopes]."""
    design = np.column_stack((np.ones(len(features)), features))
    return np.linalg.lstsq(design, targets, rcond=None)[0]


def evaluate(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Input: 25 quiet-window events. Output: held-out predictions and model scores."""
    groups = sorted({row["quiet_end_exclusive_time_us"] for row in rows})
    if len(rows) != 25 or len(groups) != 20:
        raise ValueError("Expected 25 storms and 20 quiet windows.")
    predictions = []
    summaries = []
    for model_name, fields in MODELS.items():
        features = np.array([[row[field] for field in fields] for row in rows])
        log_target = model_name == "log_ratio_abs_h"
        targets = np.array([math.log(row["r_fit"] / row["r_phase3"])
                            if log_target else row["r_fit"] - row["r_phase3"]
                            for row in rows])
        errors = []
        positive_h_slopes = 0
        for group_id in groups:
            train = np.array([i for i, row in enumerate(rows)
                              if row["quiet_end_exclusive_time_us"] != group_id])
            test = np.array([i for i, row in enumerate(rows)
                             if row["quiet_end_exclusive_time_us"] == group_id])
            coefficients = fit_coefficients(features[train], targets[train])
            positive_h_slopes += coefficients[1] > 0
            for index in test:
                row = rows[int(index)]
                correction = float(coefficients[0] + features[index] @ coefficients[1:])
                r_pred = (row["r_phase3"] * math.exp(correction) if log_target
                          else row["r_phase3"] + correction)
                if not 0 < r_pred < 2:
                    raise ValueError(f"Invalid linear R: {model_name}, {row['storm_id']}")
                errors.append(row["r_fit"] - r_pred)
                predictions.append({"storm_id": row["storm_id"], "model": model_name,
                                    "held_out_quiet_end_us": group_id,
                                    "r_phase3": row["r_phase3"], "r_fit": row["r_fit"],
                                    "r_pred": r_pred})
        summaries.append({"model": model_name, "positive_h_slopes": positive_h_slopes,
                          "mae_r": float(np.mean(abs(np.array(errors)))),
                          "rmse_r": math.sqrt(float(np.mean(np.square(errors))))})
    return predictions, summaries


def save_results(predictions: list[dict], summaries: list[dict]) -> None:
    """Input: held-out model predictions and scores. Output: new SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE linear_prediction (
                storm_id TEXT NOT NULL, model TEXT NOT NULL,
                held_out_quiet_end_us INTEGER NOT NULL, r_phase3 REAL NOT NULL,
                r_fit REAL NOT NULL, r_pred REAL NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(storm_id,model)
            );
            CREATE TABLE model_summary (
                model TEXT PRIMARY KEY, positive_h_slopes INTEGER NOT NULL,
                mae_r REAL NOT NULL, rmse_r REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO linear_prediction VALUES (?,?,?,?,?,?,?)", (
            (row["storm_id"], row["model"], row["held_out_quiet_end_us"],
             row["r_phase3"], row["r_fit"], row["r_pred"], ALGORITHM_VERSION)
            for row in predictions
        ))
        database.executemany("INSERT INTO model_summary VALUES (?,?,?,?,?)", (
            (row["model"], row["positive_h_slopes"], row["mae_r"],
             row["rmse_r"], ALGORITHM_VERSION) for row in summaries
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit - r_phase3; log_ratio_abs_h uses log(r_fit/r_phase3)"),
            ("validation", "leave one distinct quiet window out; 20 folds"),
            ("model", "ordinary least squares; abs_h plus at most one control"),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Linear control SQLite integrity check failed.")


def main() -> None:
    """Input: Phase 2/3 and Phase 4 V2 read-only data. Output: linear-control SQLite."""
    predictions, summaries = evaluate(load_quiet_features())
    save_results(predictions, summaries)
    for row in sorted(summaries, key=lambda item: item["mae_r"]):
        print(f"{row['model']}: MAE={row['mae_r']:.6f}, "
              f"H slope +={row['positive_h_slopes']}/20")


if __name__ == "__main__":
    main()
