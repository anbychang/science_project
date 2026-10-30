"""Check balanced holdouts and the delayed first-order response algebra."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from calc_trial2_delay import (
    balanced_splits, fit_gain, fixed_gain_error, response_statistics,
)
from phases.phase3.code.calc_h_tau import filtered_sme, phase_support, phase_weighted_mean


def test_balanced_splits_cover_each_event_twenty_times() -> None:
    """Input: 25 synthetic event IDs. Output: 100 balanced 20/5 splits."""
    splits = balanced_splits(25)
    appearances = np.zeros(25, dtype=int)
    for _, train, test in splits:
        assert len(train) == 20
        assert len(test) == 5
        assert not np.intersect1d(train, test).size
        appearances[test] += 1
    assert len(splits) == 100
    assert np.array_equal(appearances, np.full(25, 20))


def test_delay_grid_recovers_known_shift() -> None:
    """Input: synthetic shifted SME response. Output: minimum at true delay."""
    sme_nt = np.full(1000, 65.0)
    sme_nt[460:480] = 465.0
    sme_nt[620:650] = 365.0
    indexes = np.arange(400, 800)
    pairs = np.full(len(indexes), 2, dtype=int)
    support = phase_support(np.linspace(0, 20 * np.pi, len(indexes)), pairs)
    filtered = filtered_sme(sme_nt - 65.0, 1.0)
    phase = phase_weighted_mean(filtered[indexes - 30], pairs, support)
    anomaly = 0.001 * phase[support["valid"]]
    event = {"minute_index": indexes, "pairs": pairs, "support": support,
             "anomaly": anomaly}
    cross, response_squared = response_statistics(
        sme_nt, [event], [(1.0, 0), (1.0, 30), (1.0, 60)]
    )
    error = fixed_gain_error((cross[:, 0], response_squared[:, 0]),
                             float(anomaly @ anomaly), 0.001)
    assert int(np.argmin(error)) == 1
    assert float(error[1]) < 1e-9


def test_fit_gain_uses_training_cross_products() -> None:
    """Input: known response and anomaly. Output: analytic gain and zero SSE."""
    response = np.array([1.0, 2.0, 3.0])
    anomaly = 0.002 * response
    gain, error = fit_gain(
        np.array([response @ anomaly]),
        np.array([response @ response]),
        float(anomaly @ anomaly),
    )
    assert np.isclose(gain[0], 0.002)
    assert np.isclose(error[0], 0.0)
