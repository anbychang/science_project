"""Search one Ridge feature set and fit the Phase 4 V2 R correction."""

import math

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from prep_storm_r_phase3_trials import quiet_group_folds


FEATURES = (
    "r_phase3", "distance_days", "quiet_day", "quiet_duration_h",
    "quiet_mean_sme_nt", "quiet_mean_ap", "quiet_mean_symh_nt",
    "quiet_mean_h_nt", "quiet_max_abs_h_nt", "event_day",
    "quiet_season_cos", "quiet_max_sme_nt", "quiet_std_sme_nt",
    "quiet_sme_trend_nt_h", "quiet_std_h_nt",
    "quiet_positive_h_fraction", "quiet_mean_ae_nt", "quiet_max_ae_nt",
    "quiet_symh_range_nt", "prequiet_sme_mean_nt", "prequiet_ap_mean",
    "quiet_f107a_last81_sfu", "quiet_abs_h_p90_nt",
)
RIDGE_ALPHA = 1.0
RANDOM_SEED = 42
GENERATIONS = 7
ELITE_COUNT = 8
CHILD_ATTEMPTS = 24


def fit_model(data: dict, train: np.ndarray,
              candidate: tuple[int, ...]) -> tuple[StandardScaler, Ridge]:
    """Input: {features, targets}, training indices, factor indices. Output: scaler and Ridge."""
    values = data["features"][train][:, candidate]
    scaler = StandardScaler().fit(values)
    model = Ridge(alpha=RIDGE_ALPHA).fit(scaler.transform(values), data["targets"][train])
    return scaler, model


def predict_delta(data: dict, split: tuple[np.ndarray, np.ndarray],
                  candidate: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Input: {features, targets}, 20/5 indices, factor indices. Output: train/test delta-R."""
    train, test = split
    scaler, model = fit_model(data, train, candidate)
    values = data["features"][:, candidate]
    return (model.predict(scaler.transform(values[train])),
            model.predict(scaler.transform(values[test])))


def score_candidate(data: dict, folds: list[tuple],
                    candidate: tuple[int, ...]) -> float:
    """Input: event data, five 20/5 folds, factor indices. Output: mean five-event RMSE."""
    scores = []
    for split in folds:
        _, predicted = predict_delta(data, split, candidate)
        test = split[1]
        scores.append(math.sqrt(float(np.mean((data["targets"][test] - predicted) ** 2))))
    return float(np.mean(scores))


def offspring(elite: list[tuple[int, ...]], rng: np.random.Generator) -> tuple[int, ...]:
    """Input: eight leading subsets and RNG. Output: merged/mutated 1-3 factor subset."""
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


def search_features(data: dict, folds: list[tuple]) -> tuple[tuple[int, ...], dict]:
    """Input: event data and five 20/5 folds. Output: one subset and candidate scores."""
    rng = np.random.default_rng(RANDOM_SEED)
    scores = {}
    population = {(index,) for index in range(len(FEATURES))}
    for _ in range(GENERATIONS):
        for candidate in population:
            if candidate not in scores:
                scores[candidate] = score_candidate(data, folds, candidate)
        elite = sorted(scores, key=lambda item: (scores[item], item))[:ELITE_COUNT]
        population = set(elite)
        for _ in range(CHILD_ATTEMPTS):
            population.add(offspring(elite, rng))
    for candidate in population:
        if candidate not in scores:
            scores[candidate] = score_candidate(data, folds, candidate)
    selected = min(scores, key=lambda item: (scores[item], item))
    return selected, scores


def evaluate(rows: list[dict]) -> dict:
    """Input: 25 event rows with 23 factors and R labels. Output: Ridge search results."""
    if len(rows) != 25 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Expected 25 distinct event rows.")
    features = np.array([[row[name] for name in FEATURES] for row in rows], dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("Feature matrix has missing or invalid values.")
    targets = np.array([row["r_fit"] - row["r_phase3"] for row in rows])
    data = {"features": features, "targets": targets}
    folds = [(np.setdiff1d(np.arange(25), test), test)
             for test in quiet_group_folds(rows, np.arange(25), 5)]
    selected, candidates = search_features(data, folds)
    fold_scores = []
    predictions = []
    for fold_index, (train, test) in enumerate(folds, 1):
        train_pred, test_pred = predict_delta(data, (train, test), selected)
        fold_scores.append((fold_index,
                            math.sqrt(float(np.mean((targets[train] - train_pred) ** 2))),
                            math.sqrt(float(np.mean((targets[test] - test_pred) ** 2))),
                            math.sqrt(float(np.mean(targets[train] ** 2))),
                            math.sqrt(float(np.mean(targets[test] ** 2)))))
        for index, correction in zip(test, test_pred, strict=True):
            row = rows[int(index)]
            r_pred = row["r_phase3"] + float(correction)
            if not 0 < r_pred < 2:
                raise ValueError(f"Invalid predicted R: {row['storm_id']}")
            predictions.append((row["storm_id"], fold_index, row["r_phase3"],
                                row["r_fit"], r_pred))
    scaler, model = fit_model(data, np.arange(25), selected)
    parameters = [(FEATURES[index], float(mean), float(scale), float(weight))
                  for index, mean, scale, weight in zip(
                      selected, scaler.mean_, scaler.scale_, model.coef_, strict=True)]
    return {"selected": selected, "candidate_scores": candidates,
            "fold_scores": fold_scores, "predictions": predictions,
            "parameters": parameters, "intercept": float(model.intercept_),
            "full_train_rmse": math.sqrt(float(np.mean(
                (targets - model.predict(scaler.transform(features[:, selected]))) ** 2)))}
