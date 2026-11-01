"""Test whether date and quiet-segment age improve the Phase 3 R baseline."""

import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from prep_storm_r_feature_trials import fit_predict
from prep_storm_r_gpr import ROOT, SOURCE


PHASE3 = Path("phases/phase4/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
OUTPUT = ROOT / "data/sqlite/storm_r_phase3_trials_v6.sqlite"
ALGORITHM_VERSION = "storm_r_phase3_trials_v6"
RANDOM_SEED = 42
DAY_US = 86_400_000_000
FEATURE_SETS = {
    "distance": ("distance_log_days",),
    "date": ("event_day",),
    "phase3_r": ("log_r_phase3",),
    "phase3_r_distance": ("log_r_phase3", "distance_log_days"),
    "phase3_r_date": ("log_r_phase3", "event_day"),
    "phase3_r_distance_date": ("log_r_phase3", "distance_log_days", "event_day"),
    "distance_season": ("distance_log_days", "season_sin", "season_cos"),
}


def load_phase3_rows() -> list[dict]:
    """Input: Phase 3 quiet R and Phase 4 V2 event R. Output: 25 paired event records."""
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    phase3_uri = f"file:{PHASE3.resolve().as_posix()}?mode=ro"
    with (closing(sqlite3.connect(source_uri, uri=True)) as phase4,
          closing(sqlite3.connect(phase3_uri, uri=True)) as phase3):
        labels = dict(phase4.execute("SELECT storm_id,r_fit FROM phase4_v2_events"))
        source_rows = phase3.execute("""
            SELECT storm_id,t0_time_us,r_candidate,r_pre_distance_days
            FROM phase3_25storm_overview ORDER BY storm_id
        """).fetchall()
    if len(labels) != 25 or len(source_rows) != 25:
        raise ValueError("Expected 25 Phase 3 and Phase 4 V2 events.")
    first_time_us = min(row[1] for row in source_rows)
    rows = []
    for storm_id, time_us, r_phase3, distance_days in source_rows:
        if storm_id not in labels or r_phase3 <= 0 or distance_days < 0:
            raise ValueError(f"Invalid Phase 3 event: {storm_id}")
        event_date = datetime.fromtimestamp(time_us / 1_000_000, timezone.utc)
        season_angle = 2 * math.pi * (event_date.timetuple().tm_yday - 1) / 365.25
        rows.append({"storm_id": storm_id, "t0_time_us": time_us,
                     "r_phase3": r_phase3, "r_fit": labels[storm_id],
                     "distance_days": distance_days,
                     "distance_log_days": math.log1p(distance_days),
                     "log_r_phase3": math.log(r_phase3),
                     "event_day": (time_us - first_time_us) / DAY_US,
                     "season_sin": math.sin(season_angle),
                     "season_cos": math.cos(season_angle)})
    if len({row["r_phase3"] for row in rows}) != 20:
        raise ValueError("Phase 3 quiet-segment grouping changed.")
    return rows


def quiet_group_folds(rows: list[dict], indices: np.ndarray, fold_count: int) -> list[np.ndarray]:
    """Input: events, selected indices, fold count. Output: equal folds keeping quiet R together."""
    if len(indices) % fold_count:
        raise ValueError("Cannot form equal-size event folds.")
    groups = {}
    for index in indices:
        groups.setdefault(rows[int(index)]["r_phase3"], []).append(int(index))
    rng = np.random.default_rng(RANDOM_SEED)
    shuffled = list(groups.values())
    rng.shuffle(shuffled)
    shuffled.sort(key=len, reverse=True)
    folds = [[] for _ in range(fold_count)]
    capacity = len(indices) // fold_count
    for group in shuffled:
        available = [fold for fold in folds if len(fold) + len(group) <= capacity]
        if not available:
            raise ValueError("Quiet-segment groups cannot fit equal-size folds.")
        min(available, key=len).extend(group)
    if any(len(fold) != capacity for fold in folds):
        raise ValueError("Quiet-segment fold sizes differ.")
    return [np.array(fold, dtype=int) for fold in folds]


def evaluate(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Input: 25 Phase 3/4 paired rows. Output: grouped held-out R and inner scores."""
    targets = np.log([row["r_fit"] / row["r_phase3"] for row in rows])
    data = {name: {"features": np.array([[row[field] for field in fields]
                                         for row in rows]), "targets": targets}
            for name, fields in FEATURE_SETS.items()}
    outer_folds = quiet_group_folds(rows, np.arange(25), 5)
    predictions = []
    scores = []
    for fold_index, test in enumerate(outer_folds, 1):
        train = np.setdiff1d(np.arange(25), test)
        inner_folds = quiet_group_folds(rows, train, 4)
        candidate_scores = []
        for name in FEATURE_SETS:
            errors = []
            for inner_test in inner_folds:
                inner_train = np.setdiff1d(train, inner_test)
                means, _ = fit_predict(inner_train, inner_test, data[name])
                errors.extend((targets[inner_test] - means) ** 2)
            candidate_scores.append((name, math.sqrt(float(np.mean(errors)))))
        selected = min(candidate_scores, key=lambda item: item[1])[0]
        means, stds = fit_predict(train, test, data[selected])
        scores.extend({"fold_index": fold_index, "feature_set": name,
                       "inner_rmse_log_correction": score, "selected": int(name == selected)}
                      for name, score in candidate_scores)
        predictions.extend({"storm_id": rows[int(index)]["storm_id"],
                            "t0_time_us": rows[int(index)]["t0_time_us"],
                            "distance_days": rows[int(index)]["distance_days"],
                            "r_phase3": rows[int(index)]["r_phase3"],
                            "r_fit": rows[int(index)]["r_fit"],
                            "r_pred": rows[int(index)]["r_phase3"] * math.exp(float(mean)),
                            "r_pred_std_log": float(std), "fold_index": fold_index,
                            "feature_set": selected}
                           for index, mean, std in zip(test, means, stds, strict=True))
    return sorted(predictions, key=lambda row: row["storm_id"]), scores


def save_results(predictions: list[dict], scores: list[dict]) -> None:
    """Input: grouped predictions and inner scores. Output: new Phase 5 V2 SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE storm_r_prediction (
                storm_id TEXT PRIMARY KEY, t0_time_us INTEGER NOT NULL,
                distance_days REAL NOT NULL, r_phase3 REAL NOT NULL,
                r_fit REAL NOT NULL, r_pred REAL NOT NULL,
                r_pred_std_log REAL NOT NULL, fold_index INTEGER NOT NULL,
                feature_set TEXT NOT NULL, algorithm_version TEXT NOT NULL
            );
            CREATE TABLE feature_selection (
                fold_index INTEGER NOT NULL, feature_set TEXT NOT NULL,
                inner_rmse_log_correction REAL NOT NULL, selected INTEGER NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(fold_index,feature_set)
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO storm_r_prediction VALUES (?,?,?,?,?,?,?,?,?,?)", (
            (row["storm_id"], row["t0_time_us"], row["distance_days"],
             row["r_phase3"], row["r_fit"], row["r_pred"], row["r_pred_std_log"],
             row["fold_index"], row["feature_set"], ALGORITHM_VERSION)
            for row in predictions
        ))
        database.executemany("INSERT INTO feature_selection VALUES (?,?,?,?,?)", (
            (row["fold_index"], row["feature_set"], row["inner_rmse_log_correction"],
             row["selected"], ALGORITHM_VERSION) for row in scores
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("phase3_source", str(PHASE3)), ("phase4_source", str(SOURCE)),
            ("target", "log(r_fit/r_phase3)"),
            ("split", "5 outer 20/5, 4 inner 15/5; repeated quiet R groups intact"),
            ("random_seed", str(RANDOM_SEED)),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Phase 3 R trial SQLite integrity check failed.")


def main() -> None:
    """Input: read-only Phase 3 and Phase 4 V2 SQLite. Output: correction trial SQLite."""
    predictions, scores = evaluate(load_phase3_rows())
    save_results(predictions, scores)
    actual = np.array([row["r_fit"] for row in predictions])
    phase3 = np.array([row["r_phase3"] for row in predictions])
    predicted = np.array([row["r_pred"] for row in predictions])
    print(f"MAE Phase 3 R={np.mean(abs(actual-phase3)):.6f}, "
          f"GPR corrected={np.mean(abs(actual-predicted)):.6f}")


if __name__ == "__main__":
    main()
