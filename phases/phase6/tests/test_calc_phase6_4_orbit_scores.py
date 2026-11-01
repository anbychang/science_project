import pytest

from phases.phase6.code.calc_phase6_4_orbit_scores import (
    EventWindow,
    MinutePrediction,
    OrbitMean,
    error_metrics,
    score_event,
    storm_metrics,
)


def test_scores_local_change_between_adjacent_complete_orbits() -> None:
    """Input: two complete POD orbits and model endpoints. Output: one local score."""
    window = EventWindow("S1", 60_000_000, 120_000_000)
    orbits = [
        OrbitMean(60_000_000, 0, 1, 100.0),
        OrbitMean(120_000_000, 70_000_000, 1, 97.0),
    ]
    predictions = {
        60_000_000: MinutePrediction(2, 1, -1.0, -2.0, 0.01),
        120_000_000: MinutePrediction(2, 1, -4.0, -4.0, 0.01),
    }

    scores = score_event(window, orbits, predictions)

    assert len(scores) == 1
    assert scores[0].observed_orbit_delta_a_m == -3.0
    assert scores[0].predicted_m0_orbit_delta_a_m == -3.0
    assert scores[0].m0_error_m == 0.0
    assert scores[0].predicted_ridge_orbit_delta_a_m == -2.0
    assert scores[0].ridge_error_m == 1.0
    assert scores[0].closer_model == "M0"


def test_skips_orbit_when_density_interval_crosses_a_block_gap() -> None:
    """Input: model endpoints in different blocks. Output: no invented orbit score."""
    window = EventWindow("S1", 60_000_000, 120_000_000)
    orbits = [
        OrbitMean(60_000_000, 0, 1, 100.0),
        OrbitMean(120_000_000, 70_000_000, 1, 97.0),
    ]
    predictions = {
        60_000_000: MinutePrediction(2, 1, -1.0, -2.0, 0.01),
        120_000_000: MinutePrediction(3, 1, -4.0, -4.0, 0.01),
    }

    assert score_event(window, orbits, predictions) == []


def test_does_not_score_across_pod_chunk_boundary() -> None:
    """Input: adjacent orbit means from different chunks. Output: no cross-chunk score."""
    window = EventWindow("S1", 60_000_000, 120_000_000)
    orbits = [
        OrbitMean(60_000_000, 0, 1, 100.0),
        OrbitMean(120_000_000, 70_000_000, 2, 97.0),
    ]
    predictions = {
        60_000_000: MinutePrediction(2, 1, -1.0, -2.0, 0.01),
        120_000_000: MinutePrediction(2, 2, -4.0, -4.0, 0.01),
    }

    assert score_event(window, orbits, predictions) == []


def test_error_metrics_score_every_orbit_error() -> None:
    """Input: three local errors. Output: direct orbit-level aggregate metrics."""
    metrics = error_metrics([-2.0, 1.0, 4.0])

    assert metrics.count == 3
    assert metrics.mean_error_m == pytest.approx(1.0)
    assert metrics.mean_absolute_error_m == pytest.approx(7.0 / 3.0)
    assert metrics.median_absolute_error_m == 2.0
    assert metrics.root_mean_square_error_m == pytest.approx((21.0 / 3.0) ** 0.5)


def test_storm_metrics_give_every_event_equal_weight() -> None:
    """Input: three event MAE pairs. Output: equal-weight wins and macro means."""
    metrics = storm_metrics([(1.0, 2.0), (10.0, 3.0), (4.0, 4.0)])

    assert metrics.storm_count == 3
    assert metrics.m0_win_count == 1
    assert metrics.ridge_win_count == 1
    assert metrics.tied_storm_count == 1
    assert metrics.m0_macro_mean_orbit_mae_m == 5.0
    assert metrics.ridge_macro_mean_orbit_mae_m == 3.0
