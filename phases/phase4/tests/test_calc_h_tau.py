"""Check continuous SME filtering and paired phase-window support."""

import math
import sys
from pathlib import Path

import numpy as np

CODE_DIRECTORY = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIRECTORY))

from calc_h_tau import (
    filtered_sme, phase_support, phase_weighted_mean,
)


def test_filter_keeps_previous_response_without_reset() -> None:
    """Input: one-minute pulse. Output: exact first-order decay into later minutes."""
    sme = np.array([65.0, 165.0, 65.0])
    alpha = math.exp(-1 / 60)
    response = filtered_sme(sme, 1) - 65
    assert np.allclose(response, [0.0, 100 * (1 - alpha),
                                  100 * alpha * (1 - alpha)])
    assert np.array_equal(filtered_sme(sme, 0) - 65, [0, 100, 0])


def test_phase_mean_uses_only_paired_samples_and_rejects_edges() -> None:
    """Input: centered phase samples with one L2 gap. Output: paired mean at center."""
    phase = np.arange(9) * math.pi / 2
    pairs = np.full(9, 2)
    pairs[3] = 0
    support = phase_support(phase, pairs)
    values = np.arange(9, dtype=float)
    values[3] = np.nan
    means = phase_weighted_mean(values, pairs, support)
    assert support["expected"][4] == 10
    assert support["paired"][4] == 8
    assert support["coverage"][4] == 0.8
    assert means[4] == 4.25
    assert math.isnan(means[0])
