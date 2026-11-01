"""Use signed residual SME response to predict the Phase 3 to Phase 4 R difference."""

import math
import sqlite3
from contextlib import closing

import numpy as np

from prep_storm_r_gpr import ROOT, SOURCE
from prep_storm_r_quiet_window_trials import evaluate, load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_quiet_response_trials_v8.sqlite"
ALGORITHM_VERSION = "storm_r_quiet_response_trials_v8"
FEATURE_SETS = {
    "quiet_mean_h": ("quiet_mean_h_nt",),
    "phase3_r_h": ("r_phase3", "quiet_mean_h_nt"),
    "distance_h": ("distance_log_days", "quiet_mean_h_nt"),
    "quiet_date_h": ("quiet_day", "quiet_mean_h_nt"),
    "h_variability": ("quiet_mean_h_nt", "quiet_std_h_nt"),
    "phase3_r_distance_h": ("r_phase3", "distance_log_days", "quiet_mean_h_nt"),
    "phase3_r_date_h": ("r_phase3", "quiet_day", "quiet_mean_h_nt"),
}


def load_gain() -> float:
    """Input: Phase 4 V2 event SQLite. Output: common positive G in 1/nT."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        values = [row[0] for row in database.execute(
            "SELECT DISTINCT gain_per_nt FROM phase4_v2_events")]
    if len(values) != 1 or values[0] <= 0:
        raise ValueError("Expected one Phase 4 V2 gain.")
    return values[0]


def save_results(predictions: list[dict], scores: list[dict], gain: float) -> None:
    """Input: held-out predictions, inner scores and G. Output: new response-trial SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE storm_r_prediction (
                storm_id TEXT PRIMARY KEY, quiet_end_exclusive_time_us INTEGER NOT NULL,
                distance_days REAL NOT NULL, quiet_mean_h_nt REAL NOT NULL,
                quiet_std_h_nt REAL NOT NULL, r_phase3 REAL NOT NULL,
                r_fit REAL NOT NULL, r_h_adjusted REAL NOT NULL,
                delta_r_pred REAL NOT NULL, r_pred REAL NOT NULL,
                fold_index INTEGER NOT NULL, feature_set TEXT NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE feature_selection (
                fold_index INTEGER NOT NULL, feature_set TEXT NOT NULL,
                inner_rmse_delta_r REAL NOT NULL, selected INTEGER NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(fold_index,feature_set)
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO storm_r_prediction VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            (row["storm_id"], row["quiet_end_exclusive_time_us"],
             row["distance_days"], row["quiet_mean_h_nt"], row["quiet_std_h_nt"],
             row["r_phase3"], row["r_fit"],
             row["r_phase3"] * math.exp(-gain * row["quiet_mean_h_nt"]),
             row["delta_r_pred"], row["r_pred"], row["fold_index"],
             row["feature_set"], ALGORITHM_VERSION) for row in predictions
        ))
        database.executemany("INSERT INTO feature_selection VALUES (?,?,?,?,?)", (
            (row["fold_index"], row["feature_set"], row["inner_rmse_delta_r"],
             row["selected"], ALGORITHM_VERSION) for row in scores
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit - r_phase3"),
            ("h_adjustment", "r_phase3 * exp(-gain_per_nt * quiet_mean_h_nt)"),
            ("gain_per_nt", str(gain)),
            ("split", "5 outer 20/5, 4 inner 15/5; repeated quiet runs intact"),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Quiet-response trial SQLite integrity check failed.")


def main() -> None:
    """Input: frozen Phase 2/3 and Phase 4 V2 data. Output: response-trial SQLite."""
    predictions, scores = evaluate(load_quiet_features(), FEATURE_SETS)
    gain = load_gain()
    save_results(predictions, scores, gain)
    actual = np.array([row["r_fit"] for row in predictions])
    original = np.array([row["r_phase3"] for row in predictions])
    adjusted = np.array([row["r_phase3"] * math.exp(-gain * row["quiet_mean_h_nt"])
                         for row in predictions])
    predicted = np.array([row["r_pred"] for row in predictions])
    print(f"MAE original={np.mean(abs(actual-original)):.6f}, "
          f"H-adjusted={np.mean(abs(actual-adjusted)):.6f}, "
          f"GPR={np.mean(abs(actual-predicted)):.6f}")


if __name__ == "__main__":
    main()
