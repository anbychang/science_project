"""Search small linear feature groups using only each outer training fold."""

import math
import sqlite3

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from prep_storm_r_gpr import ROOT
from prep_storm_r_phase3_trials import quiet_group_folds
from prep_storm_r_quiet_window_trials import load_quiet_features


OUTPUT = ROOT / "data/sqlite/storm_r_feature_search_v15.sqlite"
ALGORITHM_VERSION = "storm_r_feature_search_v15"
RANDOM_SEED = 42
RIDGE_ALPHA = 1.0
GENERATIONS = 7
FEATURES = (
    "r_phase3", "distance_days", "quiet_day", "quiet_duration_h",
    "quiet_mean_sme_nt", "quiet_mean_ap", "quiet_mean_symh_nt",
    "quiet_mean_h_nt", "quiet_max_abs_h_nt",
    "event_day", "quiet_season_cos", "quiet_max_sme_nt",
    "quiet_std_sme_nt", "quiet_sme_trend_nt_h", "quiet_std_h_nt",
    "quiet_positive_h_fraction", "quiet_mean_ae_nt", "quiet_max_ae_nt",
    "quiet_symh_range_nt", "prequiet_sme_mean_nt", "prequiet_ap_mean",
    "quiet_f107a_last81_sfu", "quiet_abs_h_p90_nt",
)


def fit_predict(values: np.ndarray, targets: np.ndarray,
                split: tuple[np.ndarray, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Input: feature columns, delta-R targets, train/test indices. Output: train/test delta-R."""
    train, test = split
    scaler = StandardScaler().fit(values[train])
    model = Ridge(alpha=RIDGE_ALPHA).fit(scaler.transform(values[train]), targets[train])
    return model.predict(scaler.transform(values[train])), model.predict(scaler.transform(values[test]))


def inner_score(candidate: tuple[int, ...], context: dict) -> float:
    """Input: feature indices and one outer-train context. Output: mean five-event RMSE."""
    features = context["features"][:, candidate]
    targets = context["targets"]
    fold_rmse = []
    for test in context["inner_folds"]:
        train = np.setdiff1d(context["outer_train"], test)
        _, predicted = fit_predict(features, targets, (train, test))
        fold_rmse.append(math.sqrt(float(np.mean((targets[test] - predicted) ** 2))))
    return float(np.mean(fold_rmse))


def offspring(elite: list[tuple[int, ...]], rng: np.random.Generator) -> tuple[int, ...]:
    """Input: top feature subsets and RNG. Output: merged/mutated subset of at most three."""
    left = elite[int(rng.integers(len(elite)))]
    right = elite[int(rng.integers(len(elite)))]
    chosen = set(left) | set(right)
    if len(chosen) > 3:
        chosen = set(rng.choice(sorted(chosen), size=3, replace=False).tolist())
    if rng.random() < 0.7:
        replacement = int(rng.integers(len(FEATURES)))
        if len(chosen) == 3:
            chosen.remove(sorted(chosen)[int(rng.integers(3))])
        chosen.add(replacement)
    return tuple(sorted(chosen))


def search_features(context: dict, seed: int) -> tuple[tuple[int, ...], dict]:
    """Input: one outer-training context and seed. Output: best subset and inner scores."""
    rng = np.random.default_rng(seed)
    scores = {}
    population = {(index,) for index in range(len(FEATURES))}
    for _ in range(GENERATIONS):
        for candidate in population:
            if candidate not in scores:
                scores[candidate] = inner_score(candidate, context)
        elite = sorted(scores, key=lambda candidate: (scores[candidate], candidate))[:8]
        population = set(elite)
        for _ in range(24):
            population.add(offspring(elite, rng))
    for candidate in population:
        if candidate not in scores:
            scores[candidate] = inner_score(candidate, context)
    selected = min(scores, key=lambda candidate: (scores[candidate], candidate))
    return selected, scores


def evaluate(rows: list[dict]) -> dict:
    """Input: 25 labeled events with 23 factors. Output: nested 20/5 search results."""
    if len(rows) != 25 or len(FEATURES) != 23:
        raise ValueError("Expected 25 events and 23 feature names.")
    features = np.array([[row[name] for name in FEATURES] for row in rows], dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("Feature matrix has missing or invalid values.")
    targets = np.array([row["r_fit"] - row["r_phase3"] for row in rows])
    predictions = []
    fold_scores = []
    candidates = []
    for fold_index, test in enumerate(quiet_group_folds(rows, np.arange(25), 5), 1):
        train = np.setdiff1d(np.arange(25), test)
        context = {"features": features, "targets": targets,
                   "outer_train": train, "inner_folds": quiet_group_folds(rows, train, 4)}
        selected, scores = search_features(context, RANDOM_SEED + fold_index)
        train_pred, test_pred = fit_predict(features[:, selected], targets, (train, test))
        fold_scores.append({
            "fold_index": fold_index,
            "selected_features": ",".join(FEATURES[index] for index in selected),
            "inner_rmse_delta_r": scores[selected],
            "train_rmse_r": math.sqrt(float(np.mean((targets[train] - train_pred) ** 2))),
            "test_rmse_r": math.sqrt(float(np.mean((targets[test] - test_pred) ** 2))),
            "baseline_train_rmse_r": math.sqrt(float(np.mean(targets[train] ** 2))),
            "baseline_test_rmse_r": math.sqrt(float(np.mean(targets[test] ** 2))),
        })
        candidates.extend({"fold_index": fold_index,
                           "features": ",".join(FEATURES[index] for index in candidate),
                           "inner_rmse_delta_r": score,
                           "selected": int(candidate == selected)}
                          for candidate, score in scores.items())
        for index, correction in zip(test, test_pred, strict=True):
            row = rows[int(index)]
            predicted_r = row["r_phase3"] + float(correction)
            if not 0 < predicted_r < 2:
                raise ValueError(f"Invalid selected R: {row['storm_id']}")
            predictions.append({"storm_id": row["storm_id"], "fold_index": fold_index,
                                "r_phase3": row["r_phase3"], "r_fit": row["r_fit"],
                                "r_pred": predicted_r})
    return {"rows": rows, "predictions": predictions,
            "fold_scores": fold_scores, "candidates": candidates}


def save_results(result: dict) -> None:
    """Input: event features and nested-search results. Output: new SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE event_feature (
                storm_id TEXT NOT NULL, feature TEXT NOT NULL, value REAL NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(storm_id,feature)
            );
            CREATE TABLE heldout_prediction (
                storm_id TEXT PRIMARY KEY, fold_index INTEGER NOT NULL,
                r_phase3 REAL NOT NULL, r_fit REAL NOT NULL, r_pred REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE fold_score (
                fold_index INTEGER PRIMARY KEY, selected_features TEXT NOT NULL,
                inner_rmse_delta_r REAL NOT NULL, train_rmse_r REAL NOT NULL,
                test_rmse_r REAL NOT NULL, baseline_train_rmse_r REAL NOT NULL,
                baseline_test_rmse_r REAL NOT NULL, algorithm_version TEXT NOT NULL
            );
            CREATE TABLE candidate_score (
                fold_index INTEGER NOT NULL, features TEXT NOT NULL,
                inner_rmse_delta_r REAL NOT NULL, selected INTEGER NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(fold_index,features)
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO event_feature VALUES (?,?,?,?)", (
            (row["storm_id"], name, row[name], ALGORITHM_VERSION)
            for row in result["rows"] for name in FEATURES
        ))
        database.executemany("INSERT INTO heldout_prediction VALUES (?,?,?,?,?,?)", (
            (row["storm_id"], row["fold_index"], row["r_phase3"],
             row["r_fit"], row["r_pred"], ALGORITHM_VERSION)
            for row in result["predictions"]
        ))
        database.executemany("INSERT INTO fold_score VALUES (?,?,?,?,?,?,?,?)", (
            (row["fold_index"], row["selected_features"], row["inner_rmse_delta_r"],
             row["train_rmse_r"], row["test_rmse_r"],
             row["baseline_train_rmse_r"], row["baseline_test_rmse_r"],
             ALGORITHM_VERSION) for row in result["fold_scores"]
        ))
        database.executemany("INSERT INTO candidate_score VALUES (?,?,?,?,?)", (
            (row["fold_index"], row["features"], row["inner_rmse_delta_r"],
             row["selected"], ALGORITHM_VERSION) for row in result["candidates"]
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit-r_phase3"),
            ("model", "train-standardized Ridge alpha=1; 1-3 features"),
            ("search", "rank all 23 single factors by mean five-event RMSE, then top-8 merge and random replacement; seed 42+outer fold"),
            ("split", "outer 20/5, inner 15/5; shared quiet windows stay together"),
            ("substitution", "quiet_abs_h_p90_nt replaces unprepared density-ratio IQR"),
        ])
        counts = database.execute("""
            SELECT count(*),min(n),max(n) FROM (
                SELECT fold_index,count(*) n FROM heldout_prediction GROUP BY fold_index)
        """).fetchone()
        if (counts != (5, 5, 5)
                or database.execute("SELECT count(*) FROM event_feature").fetchone()[0] != 575
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
            raise ValueError("Feature-search SQLite audit failed.")


def main() -> None:
    """Input: Phase 2/3 and Phase 4 V2 read-only data. Output: feature-search SQLite."""
    result = evaluate(load_quiet_features())
    save_results(result)
    scores = result["fold_scores"]
    print(f"23-single-factor-first search: train RMSE mean={np.mean([row['train_rmse_r'] for row in scores]):.6f}, "
          f"test RMSE mean={np.mean([row['test_rmse_r'] for row in scores]):.6f}; "
          f"baseline test={np.mean([row['baseline_test_rmse_r'] for row in scores]):.6f}")
    print("selected", [row["selected_features"] for row in scores])


if __name__ == "__main__":
    main()
