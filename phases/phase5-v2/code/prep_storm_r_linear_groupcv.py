"""Compare simple R corrections using five quiet-grouped 20/5 folds."""

import math
import sqlite3

import numpy as np

from prep_storm_r_gpr import ROOT
from prep_storm_r_linear_controls import MODELS, fit_coefficients
from prep_storm_r_phase3_trials import quiet_group_folds
from prep_storm_r_quiet_window_trials import load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_linear_groupcv_v13.sqlite"
ALGORITHM_VERSION = "storm_r_linear_groupcv_v13"


def evaluate(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Input: 25 event rows. Output: 20/5 predictions and model summary rows."""
    if len(rows) != 25 or len({row["quiet_end_exclusive_time_us"] for row in rows}) != 20:
        raise ValueError("Expected 25 storms and 20 distinct quiet windows.")
    folds = quiet_group_folds(rows, np.arange(25), 5)
    predictions = []
    summaries = []
    for model_name in ("phase3_r", "train_mean_delta", *MODELS):
        fields = MODELS.get(model_name, ())
        features = np.array([[row[field] for field in fields] for row in rows])
        log_target = model_name == "log_ratio_abs_h"
        targets = np.array([math.log(row["r_fit"] / row["r_phase3"])
                            if log_target else row["r_fit"] - row["r_phase3"]
                            for row in rows])
        errors = []
        for fold_index, test in enumerate(folds, 1):
            train = np.setdiff1d(np.arange(25), test)
            if model_name == "phase3_r":
                coefficients = np.array([0.0])
            else:
                coefficients = fit_coefficients(features[train], targets[train])
            for index in test:
                row = rows[int(index)]
                correction = float(coefficients[0] + features[index] @ coefficients[1:])
                r_pred = (row["r_phase3"] * math.exp(correction) if log_target
                          else row["r_phase3"] + correction)
                if not 0 < r_pred < 2:
                    raise ValueError(f"Invalid R prediction: {model_name}, {row['storm_id']}")
                errors.append(row["r_fit"] - r_pred)
                predictions.append({"storm_id": row["storm_id"], "model": model_name,
                                    "quiet_end_us": row["quiet_end_exclusive_time_us"],
                                    "fold_index": fold_index, "r_phase3": row["r_phase3"],
                                    "r_fit": row["r_fit"], "r_pred": r_pred})
        summaries.append({"model": model_name,
                          "mae_r": float(np.mean(abs(np.array(errors)))),
                          "rmse_r": math.sqrt(float(np.mean(np.square(errors))))})
    return predictions, summaries


def save_results(predictions: list[dict], summaries: list[dict]) -> None:
    """Input: 20/5 predictions and summaries. Output: new Phase 5 V2 SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE linear_prediction (
                storm_id TEXT NOT NULL, model TEXT NOT NULL,
                quiet_end_us INTEGER NOT NULL, fold_index INTEGER NOT NULL,
                r_phase3 REAL NOT NULL, r_fit REAL NOT NULL, r_pred REAL NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(storm_id,model)
            );
            CREATE TABLE model_summary (
                model TEXT PRIMARY KEY, mae_r REAL NOT NULL, rmse_r REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO linear_prediction VALUES (?,?,?,?,?,?,?,?)", (
            (row["storm_id"], row["model"], row["quiet_end_us"], row["fold_index"],
             row["r_phase3"], row["r_fit"], row["r_pred"], ALGORITHM_VERSION)
            for row in predictions
        ))
        database.executemany("INSERT INTO model_summary VALUES (?,?,?,?)", (
            (row["model"], row["mae_r"], row["rmse_r"], ALGORITHM_VERSION)
            for row in summaries
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit - r_phase3; log_ratio_abs_h uses log ratio"),
            ("split", "five 20-train/5-test folds, quiet calibration groups intact"),
            ("fold_seed", "42"),
        ])
        counts = database.execute("""
            SELECT count(*),min(n),max(n) FROM (
                SELECT fold_index,count(*) n FROM linear_prediction
                WHERE model='phase3_r' GROUP BY fold_index)
        """).fetchone()
        split_groups = database.execute("""
            SELECT count(*) FROM (
                SELECT quiet_end_us,count(DISTINCT fold_index) n FROM linear_prediction
                WHERE model='phase3_r' GROUP BY quiet_end_us HAVING n>1)
        """).fetchone()[0]
        if counts != (5, 5, 5) or split_groups or database.execute(
                "PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("20/5 grouped linear output audit failed.")


def main() -> None:
    """Input: Phase 2/3 and Phase 4 V2 read-only data. Output: grouped 20/5 SQLite."""
    predictions, summaries = evaluate(load_quiet_features())
    save_results(predictions, summaries)
    for row in sorted(summaries, key=lambda item: item["mae_r"]):
        print(f"{row['model']}: MAE={row['mae_r']:.6f}, RMSE={row['rmse_r']:.6f}")


if __name__ == "__main__":
    main()
