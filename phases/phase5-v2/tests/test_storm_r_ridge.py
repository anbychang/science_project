import runpy
from pathlib import Path

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "code/calc_storm_r_ridge.py"


def test_candidate_uses_mean_of_five_group_rmse(monkeypatch):
    """Input: one bad five-event group. Output: mean group RMSE of 0.2."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    namespace = runpy.run_path(str(SCRIPT))

    def zero_predict(data, split, candidate):
        """Input: event data, 20/5 split, factors. Output: zero delta-R arrays."""
        return np.zeros(20), np.zeros(5)

    monkeypatch.setitem(namespace["score_candidate"].__globals__,
                        "predict_delta", zero_predict)
    targets = np.r_[np.ones(5), np.zeros(20)]
    folds = [(np.setdiff1d(np.arange(25), test), test)
             for test in np.arange(25).reshape(5, 5)]
    assert np.isclose(namespace["score_candidate"](
        {"targets": targets}, folds, (0,)), 0.2)


def test_training_scaler_does_not_use_five_scoring_events(monkeypatch):
    """Input: changed five-event features. Output: unchanged 20-event predictions."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    predict_delta = runpy.run_path(str(SCRIPT))["predict_delta"]
    features = np.arange(25, dtype=float).reshape(-1, 1)
    targets = 0.01 * features[:, 0]
    split = (np.arange(20), np.arange(20, 25))
    original_train, _ = predict_delta(
        {"features": features, "targets": targets}, split, (0,))
    changed = features.copy()
    changed[20:] = 10_000
    changed_train, _ = predict_delta(
        {"features": changed, "targets": targets}, split, (0,))
    assert np.allclose(original_train, changed_train)
