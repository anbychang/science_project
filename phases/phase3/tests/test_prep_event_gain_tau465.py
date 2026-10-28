"""Check the fixed-tau event gain estimator without storm data files."""

import math

import numpy as np
import pytest

from phases.phase3.code.prep_event_gain_tau465 import fit_event_gain


def test_event_gain_recovers_amplitude_without_changing_tau():
    """Input: exact linear H-response data. Output: event gain of 2 per nT."""
    response_nt = np.array([0.0, 1.0, 2.0, 3.0])
    log_anomaly = 2.0 * response_nt
    fit = fit_event_gain(response_nt, log_anomaly, pooled_gain_per_nt=1.0)
    assert math.isclose(fit["gain_event_fit_per_nt"], 2.0)


def test_zero_response_cannot_identify_event_gain():
    """Input: zero H and finite anomaly. Output: explicit identification error."""
    with pytest.raises(ValueError, match="unidentified"):
        fit_event_gain(np.zeros(3), np.ones(3), pooled_gain_per_nt=1.0)
