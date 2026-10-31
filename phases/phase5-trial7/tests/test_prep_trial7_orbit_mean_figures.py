"""Check one-orbit averaging and scoring on the averaged densities."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("phases/phase5-trial7/code").resolve()))
from prep_trial7_orbit_mean_figures import score_event, trailing_orbit_mean  # noqa: E402


def test_orbit_mean_uses_previous_full_phase_turn() -> None:
    """Input: half-orbit phase steps and minute values. Output: trailing window means."""
    phase = np.arange(6) * np.pi / 2
    density = np.arange(1, 7, dtype=float)
    result = trailing_orbit_mean(density, phase, np.ones(6, dtype=int))
    assert np.allclose(result, [np.nan, np.nan, np.nan, np.nan, 3.0, 4.0],
                       equal_nan=True)


def test_orbit_mean_does_not_bridge_missing_minute() -> None:
    """Input: one missing minute inside orbit. Output: no average across gap."""
    phase = np.arange(6) * np.pi / 2
    density = np.array([1.0, 2.0, np.nan, 4.0, 5.0, 6.0])
    result = trailing_orbit_mean(density, phase, np.ones(6, dtype=int))
    assert np.isnan(result).all()


def test_orbit_mean_weights_native_pairs() -> None:
    """Input: unequal 30-second pair counts. Output: pair-weighted orbit mean."""
    phase = np.arange(5) * np.pi / 2
    density = np.arange(1, 6, dtype=float)
    result = trailing_orbit_mean(density, phase, np.array([1, 2, 1, 1, 1]))
    assert result[4] == 17 / 6


def test_score_uses_shared_orbit_mean_rows() -> None:
    """Input: averaged densities with one unavailable correction. Output: shared-row score."""
    event = {
        "storm_id": "example",
        "t0_us": 0,
        "time_us": np.array([0, 60_000_000, 120_000_000]),
        "orbit_l2": np.array([2.0, 2.0, 2.0]),
        "orbit_trial4": np.array([1.0, 2.0, 2.0]),
        "orbit_corrected": np.array([2.0, 2.0, np.nan]),
    }
    score = score_event(event)
    assert score["scored_count"] == 2
    assert np.isclose(score["trial4_log_rmse"], np.log(2) / np.sqrt(2))
    assert score["corrected_log_rmse"] == 0.0
