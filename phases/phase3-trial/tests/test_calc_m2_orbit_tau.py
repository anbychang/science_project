"""Check that changing tau by orbit preserves the filter state."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from calc_m2_orbit_tau import event_orbit_response, tau_from_previous_sme


def test_previous_orbit_rule_uses_only_known_sme() -> None:
    """Input: previous-orbit SME levels. Output: quiet/interpolated/active tau."""
    tau = tau_from_previous_sme(np.array([40.0, 500.0, 935.0]), 1.0, 5.0)
    assert np.allclose(tau, [1.0, 3.0, 1.0 + 4.0 * 870.0 / 1305.0])


def test_event_response_uses_prior_state_at_window_start() -> None:
    """Input: prior response and two orbit segments. Output: carried memory."""
    response = event_orbit_response(np.array([0.0, 0.0]),
                                    np.array([0, 1, 2]),
                                    np.array([1.0, 2.0]), 10.0)
    assert np.isclose(response[0], 10 * np.exp(-1 / 60))
    assert np.isclose(response[1], response[0] * np.exp(-1 / 120))
