"""Check the event-level split contract without loading research data."""

import runpy
from pathlib import Path

import numpy as np
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "code/prep_storm_r_gpr.py"
TRIAL_SCRIPT = SCRIPT.parent / "prep_storm_r_feature_trials.py"
PHASE3_SCRIPT = SCRIPT.parent / "prep_storm_r_phase3_trials.py"
PRIOR_SCRIPT = SCRIPT.parent / "prep_storm_r_prior_gpr.py"
LINEAR_SCRIPT = SCRIPT.parent / "prep_storm_r_linear_factors.py"
CONTROL_SCRIPT = SCRIPT.parent / "prep_storm_r_linear_controls.py"
SEARCH_SCRIPT = SCRIPT.parent / "prep_storm_r_feature_search.py"
SEARCH_V15_SCRIPT = SCRIPT.parent / "prep_storm_r_feature_search_v15.py"
SEARCH_V16_SCRIPT = SCRIPT.parent / "prep_storm_r_feature_search_v16.py"
SEARCH_V17_SCRIPT = SCRIPT.parent / "prep_storm_r_feature_search_v17.py"
SELECTED_GPR_SCRIPT = SCRIPT.parent / "prep_storm_r_selected_gpr.py"
SMOOTH_GPR_SCRIPT = SCRIPT.parent / "prep_storm_r_gpr_smooth.py"


def test_held_out_split_covers_every_storm_once():
    """Input: 25 synthetic event rows. Output: five disjoint 20/5 held-out folds."""
    predict = runpy.run_path(str(SCRIPT))["predict_held_out"]
    rows = [
        {"storm_id": f"S{index:02d}", "peak_sme_nt": 100.0 + index * 20,
         "min_symh_nt": -50.0 - index * 3, "log_r_fit": index / 100,
         "r_fit": 1.0}
        for index in range(25)
    ]
    result = predict(rows)
    assert {row["storm_id"] for row in result} == {row["storm_id"] for row in rows}
    assert [sum(row["fold_index"] == fold for row in result) for fold in range(1, 6)] == [5] * 5
    with pytest.raises(ValueError, match="distinct storms"):
        predict(rows[:-1] + rows[:1])


def test_feature_selection_uses_only_outer_training_storms(monkeypatch):
    """Input: 20 training indices. Output: inner fits never touch five held-out events."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    namespace = runpy.run_path(str(TRIAL_SCRIPT))
    seen = []

    def fake_fit_predict(train, test, model_data):
        """Input: inner split and unused data. Output: zeros with checked split shape."""
        seen.append((set(train), set(test)))
        return np.zeros(len(test)), np.ones(len(test))

    monkeypatch.setitem(namespace["select_features"].__globals__, "fit_predict", fake_fit_predict)
    model_data = {name: {"targets": np.arange(25, dtype=float)}
                  for name in namespace["FEATURE_SETS"]}
    namespace["select_features"](np.arange(20), model_data)
    assert len(seen) == 4 * len(namespace["FEATURE_SETS"])
    assert all(len(train) == 15 and len(test) == 5 and not train & test
               and train | test == set(range(20)) for train, test in seen)


def test_phase3_quiet_groups_stay_in_one_fold(monkeypatch):
    """Input: 25 events with repeated quiet R. Output: five folds of five intact groups."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    split = runpy.run_path(str(PHASE3_SCRIPT))["quiet_group_folds"]
    group_values = [1.0] * 3 + [2.0] * 3 + [3.0] * 2 + list(range(4, 21))
    rows = [{"r_phase3": value} for value in group_values]
    folds = split(rows, np.arange(25), 5)
    assert [len(fold) for fold in folds] == [5] * 5
    assert sorted(np.concatenate(folds)) == list(range(25))
    for group_value in set(group_values):
        assert sum(any(rows[int(index)]["r_phase3"] == group_value for index in fold)
                   for fold in folds) == 1


def test_zero_prior_keeps_phase3_r_without_correction_evidence(monkeypatch):
    """Input: zero observed delta-R and 20/5 split. Output: zero predicted correction."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    predict = runpy.run_path(str(PRIOR_SCRIPT))["predict_delta"]
    data = {"features": np.arange(25, dtype=float).reshape(-1, 1),
            "targets": np.zeros(25)}
    predicted = predict(data, (np.arange(20), np.arange(20, 25)), 0.1)
    assert np.allclose(predicted, 0)


def test_single_factor_line_recovers_known_slope(monkeypatch):
    """Input: exact one-factor delta-R relation. Output: matching intercept and slope."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    fit_line = runpy.run_path(str(LINEAR_SCRIPT))["fit_line"]
    values = np.array([0.0, 1.0, 2.0, 3.0])
    assert np.allclose(fit_line(values, 0.2 + 0.05 * values), (0.2, 0.05))


def test_two_factor_line_recovers_known_slopes(monkeypatch):
    """Input: exact two-factor delta-R relation. Output: matching coefficients."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    fit = runpy.run_path(str(CONTROL_SCRIPT))["fit_coefficients"]
    features = np.array([[0.0, 1.0], [1.0, 0.0], [2.0, 1.0], [3.0, 2.0]])
    targets = 0.1 + 0.04 * features[:, 0] - 0.02 * features[:, 1]
    assert np.allclose(fit(features, targets), (0.1, 0.04, -0.02))


def test_feature_search_offspring_keeps_small_unique_subsets(monkeypatch):
    """Input: three parent subsets and fixed RNG. Output: valid 1-3 factor children."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    namespace = runpy.run_path(str(SEARCH_SCRIPT))
    rng = np.random.default_rng(42)
    children = [namespace["offspring"]([(0,), (1, 2), (3,)], rng)
                for _ in range(50)]
    assert all(1 <= len(child) <= 3 and len(set(child)) == len(child)
               and all(0 <= index < len(namespace["FEATURES"]) for index in child)
               for child in children)


def test_search_scores_all_23_single_factors_before_merging(monkeypatch):
    """Input: mock five-event scores. Output: 23 singletons scored before first merge."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    namespace = runpy.run_path(str(SEARCH_V15_SCRIPT))
    scored = set()

    def fake_score(candidate, context):
        """Input: candidate and unused context. Output: mock score."""
        scored.add(candidate)
        return float(sum(candidate))

    def fake_offspring(elite, rng):
        """Input: elite and RNG. Output: fixed valid child after checking first pass."""
        assert {(index,) for index in range(23)} <= scored
        return (0, 1)

    monkeypatch.setitem(namespace["search_features"].__globals__, "inner_score", fake_score)
    monkeypatch.setitem(namespace["search_features"].__globals__, "offspring", fake_offspring)
    namespace["search_features"]({}, 42)


def test_five_event_score_uses_20_training_and_five_scoring_events(monkeypatch):
    """Input: 20/5 indices and mock fit. Output: RMSE from those five events."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    namespace = runpy.run_path(str(SEARCH_V16_SCRIPT))
    seen = []

    def fake_fit_predict(values, targets, split):
        """Input: values, targets, split. Output: zero predictions after split check."""
        seen.append(split)
        return np.zeros(20), np.zeros(5)

    monkeypatch.setitem(namespace["five_event_score"].__globals__,
                        "fit_predict", fake_fit_predict)
    context = {"features": np.ones((25, 23)), "targets": np.arange(25, dtype=float),
               "train": np.arange(20), "score_events": np.arange(20, 25)}
    score = namespace["five_event_score"]((0,), context)
    assert np.isclose(score, np.sqrt(np.mean(np.arange(20, 25, dtype=float) ** 2)))
    assert len(seen) == 1 and np.array_equal(seen[0][0], np.arange(20))
    assert np.array_equal(seen[0][1], np.arange(20, 25))


def test_one_set_search_scores_all_23_single_factors_before_merging(monkeypatch):
    """Input: five-fold context. Output: one set after all singleton scores."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    namespace = runpy.run_path(str(SEARCH_V17_SCRIPT))
    scored = set()

    def fake_score(candidate, context):
        """Input: candidate and unused context. Output: fixed ranking score."""
        scored.add(candidate)
        return float(sum(candidate))

    def fake_offspring(elite, rng):
        """Input: elite and RNG. Output: fixed child after singleton check."""
        assert {(index,) for index in range(23)} <= scored
        return (0, 1)

    monkeypatch.setitem(namespace["search_one_set"].__globals__,
                        "score_candidate", fake_score)
    monkeypatch.setitem(namespace["search_one_set"].__globals__,
                        "offspring", fake_offspring)
    selected, scores = namespace["search_one_set"]({})
    assert selected == (0,)
    assert len(scores) >= 23


def test_selected_gpr_keeps_zero_delta_and_grouped_20_5_splits(monkeypatch):
    """Input: 25 zero-correction events. Output: zero scores and grouped 20/5 folds."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    evaluate = runpy.run_path(str(SELECTED_GPR_SCRIPT))["evaluate"]
    group_values = [0.5] * 3 + [0.6] * 3 + [0.7] * 2 + [0.8 + index / 100
                                                       for index in range(17)]
    rows = [{"storm_id": f"S{index:02d}", "r_phase3": value, "r_fit": value,
             "prequiet_sme_mean_nt": 100.0 + index,
             "quiet_f107a_last81_sfu": 120.0 + index}
            for index, value in enumerate(group_values)]
    folds, predictions = evaluate(rows)
    assert len(folds) == 5 and len(predictions) == 25
    assert all(np.isclose(fold[1], 0) and np.isclose(fold[2], 0)
               for fold in folds)
    assert all(np.isclose(row[2], row[4]) for row in predictions)


def test_gpr_setting_choice_keeps_outer_five_out_of_inner_fits(monkeypatch):
    """Input: 20 outer-training events. Output: six settings use only inner 15/5."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    namespace = runpy.run_path(str(SMOOTH_GPR_SCRIPT))
    seen = []

    def fake_fit_predict(data, split, setting):
        """Input: model data, inner split, setting. Output: zero corrections."""
        seen.append(split)
        return np.zeros(len(split[0])), np.zeros(len(split[1]))

    monkeypatch.setitem(namespace["choose_setting"].__globals__,
                        "fit_predict", fake_fit_predict)
    rows = [{"r_phase3": float(index)} for index in range(25)]
    data = {"features": np.ones((25, 3)), "targets": np.zeros(25)}
    selected, scores = namespace["choose_setting"](data, rows, np.arange(20))
    assert len(scores) == 6 and len(seen) == 24
    assert all(len(train) == 15 and len(test) == 5
               and set(train) | set(test) == set(range(20))
               for train, test in seen)
