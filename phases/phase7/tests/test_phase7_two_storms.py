import math

from phases.phase7.code.calc_phase7_decay import (
    JoinedMinute,
    integrated_rows,
    kernel_increments,
)
from phases.phase7.code.load_phase7_two_storms import FixedModel, ridge_prediction


def test_ridge_prediction_uses_saved_standardization() -> None:
    """Input: one three-factor record. Output: manual standardized Ridge prediction."""
    model = FixedModel(
        tau_hours=4.75,
        gain_per_nt=0.001,
        ridge_intercept=0.1,
        ridge_parameters={
            "r_phase3": (1.0, 0.5, 0.2),
            "prequiet_sme_mean_nt": (50.0, 10.0, -0.1),
            "quiet_f107a_last81_sfu": (100.0, 20.0, 0.2),
        },
        beff_m2_kg=0.01,
    )
    features = {
        "r_phase3": 1.5,
        "prequiet_sme_mean_nt": 60.0,
        "quiet_f107a_last81_sfu": 120.0,
    }
    assert math.isclose(ridge_prediction(features, model), 1.9, rel_tol=1e-12)


def test_kernel_increments_keep_models_separate() -> None:
    """Input: two density endpoints. Output: Ridge/M0 kernel ratio follows density ratio."""
    previous = JoinedMinute("storm", 0, 1, 6_800_000.0, 1e-12, 2e-12)
    current = JoinedMinute("storm", 60_000_000, 1, 6_800_000.0, 1e-12, 2e-12)
    m0_increment, ridge_increment = kernel_increments(previous, current)
    assert math.isclose(ridge_increment / m0_increment, 2.0)


def test_decay_integration_does_not_cross_a_gap() -> None:
    """Input: one storm with a missing minute. Output: two blocks summed at event level."""
    rows = [
        JoinedMinute("storm", 0, 1, 100.0, 1e-12, 1e-12),
        JoinedMinute("storm", 60_000_000, 1, 99.0, 1e-12, 1e-12),
        JoinedMinute("storm", 180_000_000, 1, 90.0, 1e-12, 1e-12),
        JoinedMinute("storm", 240_000_000, 1, 89.0, 1e-12, 1e-12),
    ]
    _, events = integrated_rows(rows, 0.01)
    assert (events[0][4], events[0][5]) == (2, -2.0)
