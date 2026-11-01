"""Save the Phase 4 V2 R target, Ridge feature search, and model in SQLite."""

import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from calc_storm_r_ridge import FEATURES, RIDGE_ALPHA, evaluate
from prep_storm_r_quiet_window_trials import load_quiet_features


ROOT = Path("phases/phase5-v2")
SOURCE = Path("phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite")
TARGET_SNAPSHOT = ROOT / "data/sqlite/phase4_v2_r_targets_v2.sqlite"
OUTPUT = ROOT / "data/sqlite/storm_r_ridge_v21.sqlite"
ALGORITHM_VERSION = "storm_r_ridge_v21"


def load_rows() -> list[dict]:
    """Input: quiet features, Phase 4 V2 R, saved target. Output: 25 checked event rows."""
    rows = load_quiet_features()
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    snapshot_uri = f"file:{TARGET_SNAPSHOT.resolve().as_posix()}?mode=ro"
    with (closing(sqlite3.connect(source_uri, uri=True)) as source,
          closing(sqlite3.connect(snapshot_uri, uri=True)) as snapshot):
        labels = dict(source.execute("SELECT storm_id,r_fit FROM phase4_v2_events"))
        saved = dict(snapshot.execute("SELECT storm_id,r_fit FROM phase4_v2_r_target"))
    if labels != saved or len(labels) != 25:
        raise ValueError("Phase 4 V2 R target snapshot differs from source.")
    if {row["storm_id"] for row in rows} != labels.keys():
        raise ValueError("Quiet features and Phase 4 V2 R events differ.")
    for row in rows:
        if row["r_fit"] != labels[row["storm_id"]]:
            raise ValueError(f"R label differs from Phase 4 V2: {row['storm_id']}")
    return rows


def save_results(rows: list[dict], result: dict) -> None:
    """Input: 25 events and Ridge results. Output: new versioned SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE event_input (
                storm_id TEXT PRIMARY KEY, t0_time_us INTEGER NOT NULL,
                quiet_start_time_us INTEGER NOT NULL,
                quiet_end_exclusive_time_us INTEGER NOT NULL,
                r_phase3 REAL NOT NULL, r_fit REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE event_feature (
                storm_id TEXT NOT NULL, feature TEXT NOT NULL, value REAL NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(storm_id,feature)
            );
            CREATE TABLE candidate_score (
                features TEXT PRIMARY KEY, five_fold_mean_rmse_r REAL NOT NULL,
                selected INTEGER NOT NULL, algorithm_version TEXT NOT NULL
            );
            CREATE TABLE fold_score (
                fold_index INTEGER PRIMARY KEY, selected_features TEXT NOT NULL,
                train_count INTEGER NOT NULL, score_count INTEGER NOT NULL,
                train_rmse_r REAL NOT NULL, five_event_rmse_r REAL NOT NULL,
                baseline_train_rmse_r REAL NOT NULL,
                baseline_five_event_rmse_r REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE heldout_prediction (
                storm_id TEXT PRIMARY KEY, fold_index INTEGER NOT NULL,
                r_phase3 REAL NOT NULL, r_fit REAL NOT NULL, r_pred REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE final_parameter (
                feature TEXT PRIMARY KEY, train_mean REAL NOT NULL,
                train_scale REAL NOT NULL, coefficient REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO event_input VALUES (?,?,?,?,?,?,?)", (
            (row["storm_id"], row["t0_time_us"], row["quiet_start_time_us"],
             row["quiet_end_exclusive_time_us"], row["r_phase3"], row["r_fit"],
             ALGORITHM_VERSION) for row in rows
        ))
        database.executemany("INSERT INTO event_feature VALUES (?,?,?,?)", (
            (row["storm_id"], name, row[name], ALGORITHM_VERSION)
            for row in rows for name in FEATURES
        ))
        database.executemany("INSERT INTO candidate_score VALUES (?,?,?,?)", (
            (",".join(FEATURES[index] for index in candidate), score,
             int(candidate == result["selected"]), ALGORITHM_VERSION)
            for candidate, score in result["candidate_scores"].items()
        ))
        selected_features = ",".join(FEATURES[index] for index in result["selected"])
        database.executemany("INSERT INTO fold_score VALUES (?,?,?,?,?,?,?,?,?)", (
            (fold, selected_features, 20, 5, train_rmse, score_rmse,
             baseline_train, baseline_score, ALGORITHM_VERSION)
            for fold, train_rmse, score_rmse, baseline_train, baseline_score
            in result["fold_scores"]
        ))
        database.executemany("INSERT INTO heldout_prediction VALUES (?,?,?,?,?,?)", (
            (*prediction, ALGORITHM_VERSION) for prediction in result["predictions"]
        ))
        database.executemany("INSERT INTO final_parameter VALUES (?,?,?,?,?)", (
            (*parameter, ALGORITHM_VERSION) for parameter in result["parameters"]
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("r_target_source", f"{SOURCE}:phase4_v2_events.r_fit"),
            ("r_target_snapshot", f"{TARGET_SNAPSHOT}:phase4_v2_r_target.r_fit"),
            ("phase3_source", "phases/phase4/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite:phase3_25storm_overview.r_candidate"),
            ("target", "r_fit-r_phase3"),
            ("selection", "A*-style top-8 merge/mutate; 23 singletons; 7 generations; seed 42"),
            ("score", "arithmetic mean of five grouped 20-train/5-score RMSE values"),
            ("model", f"train-standardized Ridge alpha={RIDGE_ALPHA}; up to 3 factors"),
            ("selected_features", selected_features),
            ("final_fit", "selected features refit on all 25 events; no independent test"),
            ("final_intercept_delta_r", repr(result["intercept"])),
            ("final_train_rmse_r", repr(result["full_train_rmse"])),
            ("algorithm_version", ALGORITHM_VERSION),
        ])
        counts = (
            database.execute("SELECT count(*) FROM event_input").fetchone()[0],
            database.execute("SELECT count(*) FROM event_feature").fetchone()[0],
            database.execute("SELECT count(*) FROM fold_score").fetchone()[0],
            database.execute("SELECT count(*) FROM heldout_prediction").fetchone()[0],
            database.execute("SELECT sum(selected) FROM candidate_score").fetchone()[0],
            database.execute("SELECT count(*) FROM final_parameter").fetchone()[0],
        )
        fold_sizes = database.execute("""
            SELECT count(*),min(n),max(n) FROM (
                SELECT fold_index,count(*) n FROM heldout_prediction GROUP BY fold_index)
        """).fetchone()
        split_quiet_groups = database.execute("""
            SELECT count(*) FROM (
                SELECT e.quiet_end_exclusive_time_us
                FROM event_input e JOIN heldout_prediction p USING(storm_id)
                GROUP BY e.quiet_end_exclusive_time_us
                HAVING count(DISTINCT p.fold_index)>1)
        """).fetchone()[0]
        if (counts != (25, 575, 5, 25, 1, len(result["selected"]))
                or fold_sizes != (5, 5, 5) or split_quiet_groups != 0
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
            raise ValueError(f"Ridge SQLite audit failed: {counts}")


def main() -> None:
    """Input: Phase 3/4 V2 SQLite sources. Output: Ridge research SQLite."""
    rows = load_rows()
    result = evaluate(rows)
    save_results(rows, result)
    scores = np.array(result["fold_scores"], dtype=float)
    print("selected", [FEATURES[index] for index in result["selected"]])
    print(f"candidates={len(result['candidate_scores'])}; "
          f"train RMSE mean={np.mean(scores[:, 1]):.6f}; "
          f"five-event selection RMSE mean={np.mean(scores[:, 2]):.6f}; "
          f"Phase 3 baseline={np.mean(scores[:, 4]):.6f}")


if __name__ == "__main__":
    main()
