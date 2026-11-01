from phases.phase6.code.calc_phase6_quiet_closure import OrbitDensityPair
from phases.phase6.code.calc_phase6_quiet_endpoint_sensitivity import (
    endpoint_estimate,
    measure_window_sensitivity,
)


def test_endpoint_sensitivity_is_zero_for_a_linear_series():
    """Input: sixteen equally spaced samples on one declining line.
    Output: 4/6/8-orbit fits agree with zero OLS residual sigma."""
    samples = [
        OrbitDensityPair(index * 5_000_000_000, 6_800_000.0 - 2.0 * index, 1.0e-12)
        for index in range(16)
    ]

    measure = measure_window_sensitivity("Q1", samples)

    assert measure.delta_a_4_m == -30.0
    assert measure.delta_a_6_m == -30.0
    assert measure.delta_a_8_m == -30.0
    assert measure.delta_a_ols_sigma_6_m == 0.0
    assert measure.delta_a_endpoint_span_m == 0.0


def test_endpoint_estimate_requires_two_complete_endpoints():
    """Input: fewer samples than two four-orbit endpoint fits.
    Output: an explicit failure instead of overlapping endpoint fits."""
    samples = [OrbitDensityPair(index, 1.0, 1.0e-12) for index in range(7)]

    try:
        endpoint_estimate(samples, 4)
    except ValueError as error:
        assert "Need 8 samples" in str(error)
    else:
        raise AssertionError("Expected incomplete endpoint samples to fail.")
