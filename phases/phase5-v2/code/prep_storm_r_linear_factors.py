"""Check one-factor linear relationships with the Phase 3 to Phase 4 R difference."""

import math
import sqlite3

import numpy as np

from prep_storm_r_gpr import ROOT
from prep_storm_r_phase3_trials import quiet_group_folds
from prep_storm_r_quiet_window_trials import load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_linear_factors_v10.sqlite"
ALGORITHM_VERSION = "storm_r_linear_factors_v10"
FACTORS = (
    "r_phase3",
    "distance_days",
    "quiet_day",
    "quiet_duration_h",
    "quiet_mean_sme_nt",
    "quiet_mean_ap",
    "quiet_mean_symh_nt",
    "quiet_mean_h_nt",
    "quiet_max_abs_h_nt",
)


def fit_line(values: np.ndarray, targets: np.ndarray) -> tuple[float, float]:
    """Input: [one factor], [delta-R]. Output: intercept and slope per factor unit."""
    design = np.column_stack((np.ones(len(values)), values))
    intercept, slope = np.linalg.lstsq(design, targets, rcond=None)[0]
    return float(intercept), float(slope)


def quiet_group_correlation(rows: list[dict], factor: str) -> float:
    """Input: 25 event rows and one factor. Output: Pearson r over 20 quiet groups."""
    groups = {}
    for row in rows:
        groups.setdefault(row["quiet_end_exclusive_time_us"], []).append(row)
    values = [np.mean([row[factor] for row in group]) for group in groups.values()]
    targets = [np.mean([row["r_fit"] - row["r_phase3"] for row in group])
               for group in groups.values()]
    return float(np.corrcoef(values, targets)[0, 1])


def evaluate(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Input: 25 Phase 3 quiet-window rows. Output: predictions, factor and fold scores."""
    if len(rows) != 25 or len({row["quiet_end_exclusive_time_us"] for row in rows}) != 20:
        raise ValueError("Expected 25 storms and 20 distinct quiet windows.")
    targets = np.array([row["r_fit"] - row["r_phase3"] for row in rows])
    folds = quiet_group_folds(rows, np.arange(25), 5)
    predictions = []
    summaries = []
    fold_slopes = []
    for factor in FACTORS:
        values = np.array([row[factor] for row in rows], dtype=float)
        _, all_slope = fit_line(values, targets)
        errors = []
        for fold_index, test in enumerate(folds, 1):
            train = np.setdiff1d(np.arange(25), test)
            intercept, slope = fit_line(values[train], targets[train])
            fold_slopes.append({"factor": factor, "fold_index": fold_index,
                                "intercept": intercept, "slope": slope})
            for index in test:
                row = rows[int(index)]
                delta_pred = intercept + slope * values[index]
                r_pred = row["r_phase3"] + delta_pred
                if not 0 < r_pred < 2:
                    raise ValueError(f"Invalid linear R: {factor}, {row['storm_id']}")
                error = row["r_fit"] - r_pred
                errors.append(error)
                predictions.append({"storm_id": row["storm_id"], "factor": factor,
                                    "factor_value": float(values[index]),
                                    "fold_index": fold_index, "r_phase3": row["r_phase3"],
                                    "r_fit": row["r_fit"], "delta_r_pred": float(delta_pred),
                                    "r_pred": float(r_pred)})
        summaries.append({"factor": factor, "slope_all": all_slope,
                          "group_pearson_r": quiet_group_correlation(rows, factor),
                          "positive_fold_slopes": sum(row["slope"] > 0 for row in fold_slopes
                                                      if row["factor"] == factor),
                          "mae_r": float(np.mean(abs(np.array(errors)))),
                          "rmse_r": math.sqrt(float(np.mean(np.square(errors))))})
    return predictions, summaries, fold_slopes


def save_results(predictions: list[dict], summaries: list[dict],
                 fold_slopes: list[dict]) -> None:
    """Input: line predictions and diagnostics. Output: new Phase 5 V2 SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE linear_prediction (
                storm_id TEXT NOT NULL, factor TEXT NOT NULL, factor_value REAL NOT NULL,
                fold_index INTEGER NOT NULL, r_phase3 REAL NOT NULL, r_fit REAL NOT NULL,
                delta_r_pred REAL NOT NULL, r_pred REAL NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(storm_id,factor)
            );
            CREATE TABLE factor_summary (
                factor TEXT PRIMARY KEY, slope_all REAL NOT NULL,
                group_pearson_r REAL NOT NULL, positive_fold_slopes INTEGER NOT NULL,
                mae_r REAL NOT NULL, rmse_r REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE fold_slope (
                factor TEXT NOT NULL, fold_index INTEGER NOT NULL,
                intercept REAL NOT NULL, slope REAL NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(factor,fold_index)
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO linear_prediction VALUES (?,?,?,?,?,?,?,?,?)", (
            (row["storm_id"], row["factor"], row["factor_value"], row["fold_index"],
             row["r_phase3"], row["r_fit"], row["delta_r_pred"], row["r_pred"],
             ALGORITHM_VERSION) for row in predictions
        ))
        database.executemany("INSERT INTO factor_summary VALUES (?,?,?,?,?,?,?)", (
            (row["factor"], row["slope_all"], row["group_pearson_r"],
             row["positive_fold_slopes"], row["mae_r"], row["rmse_r"],
             ALGORITHM_VERSION) for row in summaries
        ))
        database.executemany("INSERT INTO fold_slope VALUES (?,?,?,?,?)", (
            (row["factor"], row["fold_index"], row["intercept"], row["slope"],
             ALGORITHM_VERSION) for row in fold_slopes
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit - r_phase3"),
            ("model", "one factor plus intercept; ordinary least squares"),
            ("association", "Pearson correlation over 20 distinct quiet-window groups"),
            ("split", "5 outer 20/5 folds; repeated quiet windows intact"),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Linear factor SQLite integrity check failed.")


def main() -> None:
    """Input: Phase 2/3 and Phase 4 V2 data. Output: one-factor linear trial SQLite."""
    predictions, summaries, fold_slopes = evaluate(load_quiet_features())
    save_results(predictions, summaries, fold_slopes)
    for row in sorted(summaries, key=lambda item: item["mae_r"]):
        print(f"{row['factor']}: group r={row['group_pearson_r']:.3f}, "
              f"fold slope +={row['positive_fold_slopes']}/5, MAE={row['mae_r']:.6f}")


if __name__ == "__main__":
    main()
