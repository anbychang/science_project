import math

import pytest

from phases.phase6.code.calc_phase6_l2_density_decay import (
    BetaFit,
    CalibrationWindow,
    DensityAnchor,
    MeanSample,
    centered_orbit,
    fit_beta_eff,
    predict_decay,
)


def test_fit_beta_eff_recovers_zero_intercept_scale():
    """Input: three exact quiet-window loss/kernel pairs. Output: fitted beta and zero SE."""
    windows = [
        CalibrationWindow("Q1", 1_000.0, 10.0),
        CalibrationWindow("Q2", 2_000.0, 20.0),
        CalibrationWindow("Q3", 3_000.0, 30.0),
    ]

    fit = fit_beta_eff(windows)

    assert fit == BetaFit(0.01, 0.0, 3)


def test_centered_orbit_uses_same_two_pi_phase_window():
    """Input: linear semi-major axis over a continuous phase segment.
    Output: centered two-pi mean equals the value at the center phase."""
    phase_step = 0.01
    samples = [
        MeanSample(
            time_us=index * 10_000_000,
            chunk_id=4,
            semi_major_axis_m=6_800_000.0 - 2.0 * index * phase_step,
            phase_rad=index * phase_step,
        )
        for index in range(1_300)
    ]
    center_phase = 2.0 * math.pi
    center_time_us = round(center_phase / phase_step * 10_000_000)
    anchor = DensityAnchor("S1", center_time_us, 0.0, 2.0e-12)

    orbit = centered_orbit([samples], anchor)

    assert orbit.phase_coverage_rad == pytest.approx(2.0 * math.pi)
    assert orbit.mean_semi_major_axis_m == pytest.approx(6_800_000.0 - 2.0 * center_phase)
    assert orbit.source_sample_count >= 500
    assert orbit.maximum_pod_gap_s <= 10.0


def test_predict_decay_returns_negative_rate_and_orbit_change():
    """Input: positive beta, density, and same-window semi-major axis.
    Output: negative candidate decay rate and orbit change."""
    anchor = DensityAnchor("S1", 10, 0.0, 2.0e-12)
    samples = [
        MeanSample(
            time_us=index * 10_000_000,
            chunk_id=1,
            semi_major_axis_m=6_800_000.0,
            phase_rad=index * 0.01,
        )
        for index in range(1_300)
    ]
    center_anchor = DensityAnchor(
        "S1", round(2.0 * math.pi / 0.01 * 10_000_000), 0.0, 2.0e-12,
    )
    orbit = centered_orbit(
        [samples],
        center_anchor,
    )

    result = predict_decay(anchor, orbit, 0.01)

    assert result.predicted_decay_rate_m_s < 0.0
    assert result.predicted_orbit_delta_a_m == pytest.approx(
        result.predicted_decay_rate_m_s * orbit.orbit_period_s,
    )
