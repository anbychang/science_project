"""Check one-factor R corrections by leaving out each quiet calibration window."""

import math
import sqlite3

import numpy as np

from prep_storm_r_gpr import ROOT
from prep_storm_r_linear_factors import FACTORS, fit_line
from prep_storm_r_quiet_window_trials import load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_linear_robustness_v11.sqlite"
ALGORITHM_VERSION = "storm_r_linear_robustness_v11"
PERMUTATIONS = 10_000
RANDOM_SEED = 42


def group_arrays(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Input: 25 events. Output: [20 groups x factors], [20 mean delta-R]."""
    groups = {}
    for row in rows:
        groups.setdefault(row["quiet_end_exclusive_time_us"], []).append(row)
    if len(groups) != 20:
        raise ValueError("Expected 20 distinct quiet windows.")
    features = np.array([[np.mean([row[field] for row in group]) for field in FACTORS]
                         for group in groups.values()])
    targets = np.array([np.mean([row["r_fit"] - row["r_phase3"] for row in group])
                        for group in groups.values()])
    return features, targets


def permutation_checks(rows: list[dict]) -> dict[str, tuple[float, float, float]]:
    """Input: 20 quiet groups. Output: {factor: (r, raw p, nine-factor adjusted p)}."""
    features, targets = group_arrays(rows)
    centered_x = features - np.mean(features, axis=0)
    centered_x /= np.sqrt(np.mean(centered_x ** 2, axis=0))
    centered_y = targets - np.mean(targets)
    centered_y /= np.sqrt(np.mean(centered_y ** 2))
    observed = centered_x.T @ centered_y / len(targets)
    raw_counts = np.zeros(len(FACTORS), dtype=int)
    adjusted_counts = np.zeros(len(FACTORS), dtype=int)
    rng = np.random.default_rng(RANDOM_SEED)
    for _ in range(PERMUTATIONS):
        correlations = abs(centered_x.T @ rng.permutation(centered_y) / len(targets))
        raw_counts += correlations >= abs(observed)
        adjusted_counts += max(correlations) >= abs(observed)
    return {factor: (float(observed[index]),
                     float((raw_counts[index] + 1) / (PERMUTATIONS + 1)),
                     float((adjusted_counts[index] + 1) / (PERMUTATIONS + 1)))
            for index, factor in enumerate(FACTORS)}


def evaluate(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Input: 25 events. Output: leave-one-window predictions and association checks."""
    associations = permutation_checks(rows)
    predictions = []
    summaries = []
    baselines = []
    group_ids = sorted({row["quiet_end_exclusive_time_us"] for row in rows})
    for factor in FACTORS:
        errors = []
        positive_slopes = 0
        for group_id in group_ids:
            train = [row for row in rows if row["quiet_end_exclusive_time_us"] != group_id]
            test = [row for row in rows if row["quiet_end_exclusive_time_us"] == group_id]
            intercept, slope = fit_line(
                np.array([row[factor] for row in train]),
                np.array([row["r_fit"] - row["r_phase3"] for row in train]))
            positive_slopes += slope > 0
            for row in test:
                delta_pred = intercept + slope * row[factor]
                predicted_r = row["r_phase3"] + delta_pred
                if not 0 < predicted_r < 2:
                    raise ValueError(f"Invalid linear R: {factor}, {row['storm_id']}")
                errors.append(row["r_fit"] - predicted_r)
                predictions.append({"storm_id": row["storm_id"], "factor": factor,
                                    "held_out_quiet_end_us": group_id,
                                    "r_fit": row["r_fit"], "r_phase3": row["r_phase3"],
                                    "r_pred": predicted_r})
        correlation, raw_p, adjusted_p = associations[factor]
        summaries.append({"factor": factor, "group_pearson_r": correlation,
                          "permutation_p": raw_p, "nine_factor_p": adjusted_p,
                          "positive_group_slopes": positive_slopes,
                          "mae_r": float(np.mean(abs(np.array(errors)))),
                          "rmse_r": math.sqrt(float(np.mean(np.square(errors))))})
    for name in ("phase3_r", "train_mean_delta"):
        errors = []
        for group_id in group_ids:
            train = [row for row in rows if row["quiet_end_exclusive_time_us"] != group_id]
            test = [row for row in rows if row["quiet_end_exclusive_time_us"] == group_id]
            correction = (float(np.mean([row["r_fit"] - row["r_phase3"] for row in train]))
                          if name == "train_mean_delta" else 0.0)
            errors.extend(row["r_fit"] - row["r_phase3"] - correction for row in test)
        baselines.append({"name": name, "mae_r": float(np.mean(abs(np.array(errors)))),
                          "rmse_r": math.sqrt(float(np.mean(np.square(errors))))})
    return predictions, summaries, baselines


def save_results(results: tuple[list[dict], list[dict], list[dict]]) -> None:
    """Input: predictions, factor summaries, baselines. Output: new SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    predictions, summaries, baselines = results
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE linear_prediction (
                storm_id TEXT NOT NULL, factor TEXT NOT NULL,
                held_out_quiet_end_us INTEGER NOT NULL, r_fit REAL NOT NULL,
                r_phase3 REAL NOT NULL, r_pred REAL NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(storm_id,factor)
            );
            CREATE TABLE factor_summary (
                factor TEXT PRIMARY KEY, group_pearson_r REAL NOT NULL,
                permutation_p REAL NOT NULL, nine_factor_p REAL NOT NULL,
                positive_group_slopes INTEGER NOT NULL, mae_r REAL NOT NULL,
                rmse_r REAL NOT NULL, algorithm_version TEXT NOT NULL
            );
            CREATE TABLE baseline_summary (
                name TEXT PRIMARY KEY, mae_r REAL NOT NULL, rmse_r REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO linear_prediction VALUES (?,?,?,?,?,?,?)", (
            (row["storm_id"], row["factor"], row["held_out_quiet_end_us"],
             row["r_fit"], row["r_phase3"], row["r_pred"], ALGORITHM_VERSION)
            for row in predictions
        ))
        database.executemany("INSERT INTO factor_summary VALUES (?,?,?,?,?,?,?,?)", (
            (row["factor"], row["group_pearson_r"], row["permutation_p"],
             row["nine_factor_p"], row["positive_group_slopes"],
             row["mae_r"], row["rmse_r"], ALGORITHM_VERSION) for row in summaries
        ))
        database.executemany("INSERT INTO baseline_summary VALUES (?,?,?,?)", (
            (row["name"], row["mae_r"], row["rmse_r"], ALGORITHM_VERSION)
            for row in baselines
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit - r_phase3"),
            ("validation", "leave one distinct quiet window out; 20 folds"),
            ("permutations", str(PERMUTATIONS)),
            ("multiple_comparison", "maximum absolute correlation across nine factors"),
            ("random_seed", str(RANDOM_SEED)),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Linear robustness SQLite integrity check failed.")


def main() -> None:
    """Input: read-only Phase 2/3 and Phase 4 V2 data. Output: robustness SQLite."""
    results = evaluate(load_quiet_features())
    save_results(results)
    for row in sorted(results[1], key=lambda item: item["mae_r"])[:3]:
        print(f"{row['factor']}: MAE={row['mae_r']:.6f}, "
              f"r={row['group_pearson_r']:.3f}, p9={row['nine_factor_p']:.3f}")
    print("baselines", [(row["name"], round(row["mae_r"], 6)) for row in results[2]])


if __name__ == "__main__":
    main()
