from phases.phase6.code.calc_phase6_quiet_closure import (
    OrbitDensityPair,
    WindowMeasure,
    density_integration_kernel,
    leave_one_window_out,
    measure_window,
)


def test_measure_window_recovers_a_descending_linear_series():
    """Input: twelve linearly declining orbit samples with fixed density.
    Output: a negative fitted change and positive empirical scale."""
    samples = [
        OrbitDensityPair(index * 5_000_000_000, 6_800_000.0 - index, 2.0e-12)
        for index in range(12)
    ]

    measure = measure_window("Q1", samples)

    assert measure.observed_delta_a_m == -11.0
    assert measure.density_kernel_kg_m == density_integration_kernel(samples)
    assert measure.empirical_scale_m2_kg is not None


def test_leave_one_window_out_excludes_held_out_scale():
    """Input: three descending windows with different empirical scales.
    Output: held-out prediction uses only the other two scales."""
    measures = [
        WindowMeasure("Q1", 1, 2, -2.0, 1.0, 2.0),
        WindowMeasure("Q2", 3, 4, -4.0, 1.0, 4.0),
        WindowMeasure("Q3", 5, 6, -8.0, 2.0, 4.0),
    ]

    result = leave_one_window_out(measures)

    assert result[0].calibration_window_count == 2
    assert result[0].predicted_delta_a_m == -4.0
    assert result[0].prediction_error_m == -2.0


def test_leave_one_window_out_excludes_overlapping_calibration_window():
    """Input: one target and one calibration window sharing orbit times.
    Output: overlap cannot contribute an empirical scale."""
    measures = [
        WindowMeasure("Q1", 1, 5, -2.0, 1.0, 2.0),
        WindowMeasure("Q2", 4, 8, -4.0, 1.0, 4.0),
        WindowMeasure("Q3", 9, 10, -8.0, 2.0, 4.0),
    ]

    result = leave_one_window_out(measures)

    assert result[0].calibration_window_count == 1
    assert result[0].predicted_delta_a_m == -4.0
