"""Choose one fixed feature subset by five grouped 20/5 scoring rounds."""

import math
import sqlite3

import numpy as np

from prep_storm_r_feature_search_v16 import (
    FEATURES, GENERATIONS, fit_predict, offspring,
)
from prep_storm_r_gpr import ROOT
from prep_storm_r_phase3_trials import quiet_group_folds
from prep_storm_r_quiet_window_trials import load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_feature_search_v17.sqlite"
RANDOM_SEED = 42


def score_candidate(candidate: tuple[int, ...], context: dict) -> float:
    """Input: feature indices and five 20/5 splits. Output: mean five-event RMSE."""
    values = context["features"][:, candidate]
    targets = context["targets"]
    scores = []
    for train, test in context["folds"]:
        _, predicted = fit_predict(values, targets, (train, test))
        scores.append(math.sqrt(float(np.mean((targets[test] - predicted) ** 2))))
    return float(np.mean(scores))


def search_one_set(context: dict) -> tuple[tuple[int, ...], dict]:
    """Input: five 20/5 splits. Output: one best subset and all candidate scores."""
    rng = np.random.default_rng(RANDOM_SEED)
    scores = {}
    population = {(index,) for index in range(len(FEATURES))}
    for _ in range(GENERATIONS):
        for candidate in population:
            if candidate not in scores:
                scores[candidate] = score_candidate(candidate, context)
        elite = sorted(scores, key=lambda item: (scores[item], item))[:8]
        population = set(elite)
        for _ in range(24):
            population.add(offspring(elite, rng))
    for candidate in population:
        if candidate not in scores:
            scores[candidate] = score_candidate(candidate, context)
    selected = min(scores, key=lambda item: (scores[item], item))
    return selected, scores


def evaluate(rows: list[dict]) -> dict:
    """Input: 25 event rows. Output: one feature set and five 20/5 scores."""
    if len(rows) != 25:
        raise ValueError("Expected 25 event rows.")
    features = np.array([[row[name] for name in FEATURES] for row in rows], dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("Feature matrix has missing or invalid values.")
    targets = np.array([row["r_fit"] - row["r_phase3"] for row in rows])
    folds = [(np.setdiff1d(np.arange(25), test), test)
             for test in quiet_group_folds(rows, np.arange(25), 5)]
    context = {"features": features, "targets": targets, "folds": folds}
    selected, candidates = search_one_set(context)
    fold_scores = []
    for fold_index, (train, test) in enumerate(folds, 1):
        train_pred, test_pred = fit_predict(features[:, selected], targets, (train, test))
        fold_scores.append((fold_index,
                            math.sqrt(float(np.mean((targets[train] - train_pred) ** 2))),
                            math.sqrt(float(np.mean((targets[test] - test_pred) ** 2))),
                            math.sqrt(float(np.mean(targets[test] ** 2)))))
    return {"selected": selected, "candidates": candidates,
            "fold_scores": fold_scores}


def save_results(result: dict) -> None:
    """Input: one selected subset and scores. Output: new SQLite result tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE candidate_score (
                features TEXT PRIMARY KEY, five_fold_mean_rmse_r REAL NOT NULL,
                selected INTEGER NOT NULL
            );
            CREATE TABLE fold_score (
                fold_index INTEGER PRIMARY KEY, train_rmse_r REAL NOT NULL,
                five_event_rmse_r REAL NOT NULL, baseline_five_event_rmse_r REAL NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO candidate_score VALUES (?,?,?)", (
            (",".join(FEATURES[index] for index in candidate), score,
             int(candidate == result["selected"]))
            for candidate, score in result["candidates"].items()
        ))
        database.executemany("INSERT INTO fold_score VALUES (?,?,?,?)",
                             result["fold_scores"])
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit-r_phase3"),
            ("model", "Ridge alpha=1; one fixed subset of 1-3 features"),
            ("selection", "23 singletons first; top-8 merge and replace; five 20/5 scores averaged"),
            ("score_limit", "all 25 event labels participate in feature selection; no independent test"),
        ])
        if (database.execute("SELECT count(*) FROM fold_score").fetchone()[0] != 5
                or database.execute("SELECT sum(selected) FROM candidate_score").fetchone()[0] != 1
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
            raise ValueError("Feature-search SQLite audit failed.")


def main() -> None:
    """Input: Phase 2/3 and Phase 4 V2 data. Output: one feature set in SQLite."""
    result = evaluate(load_quiet_features())
    save_results(result)
    names = [FEATURES[index] for index in result["selected"]]
    folds = result["fold_scores"]
    print("selected", names)
    print(f"train RMSE mean={np.mean([row[1] for row in folds]):.6f}; "
          f"five-event selection RMSE mean={np.mean([row[2] for row in folds]):.6f}; "
          f"baseline={np.mean([row[3] for row in folds]):.6f}")


if __name__ == "__main__":
    main()
