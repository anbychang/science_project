"""Check that free orbit tau fitting recovers a known response schedule."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from calc_m2_free_orbit_tau import fit_event_orbit_tau
from calc_m2_orbit_tau import event_orbit_response


def test_free_orbit_tau_recovers_two_known_segments() -> None:
    """Input: two noiseless orbit segments. Output: their separate tau values."""
    first = np.r_[np.zeros(10), np.full(40, 100.0)]
    second = np.r_[np.full(10, 100.0), np.zeros(40)]
    sme_excess = np.r_[first, second]
    edges = np.array([0, 50, 100])
    target = event_orbit_response(sme_excess, edges,
                                  np.array([1.0, 5.0]), 0.0)
    event = {
        "sme_excess": sme_excess,
        "orbit_edges": edges,
        "initial_h": 0.0,
        "pairs": np.ones(100, dtype=int),
        "support": {"left": np.arange(100), "right": np.arange(1, 101),
                    "paired": np.ones(100, dtype=int),
                    "valid": np.ones(100, dtype=bool)},
        "anomaly": target,
    }
    fitted = fit_event_orbit_tau(event, 1.0)
    assert np.array_equal(fitted["tau_by_orbit"], [1.0, 5.0])
    assert fitted["final_sse"] < 1e-20
    assert all(type(changed) is int for _, changed, _ in fitted["sweeps"])
