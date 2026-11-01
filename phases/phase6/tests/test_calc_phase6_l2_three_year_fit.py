import math

import pytest

from phases.phase6.code.calc_phase6_l2_density_decay import (
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
)
from phases.phase6.code.calc_phase6_l2_three_year_fit import (
    PairedOrbit,
    apply_global_beta,
    build_integral_points,
    fit_global_beta,
)


def exact_drag_pairs(beta_eff: float) -> list[PairedOrbit]:
    """Input: positive beta_eff. Output: five exact L2/POD drag-consistent orbit rows."""
    pairs = []
    semi_major_axis_m = 6_800_000.0
    density_kg_m3 = 2.0e-12
    interval_s = 5_600.0
    for index in range(5):
        time_us = int(index * interval_s * 1_000_000)
        pairs.append(PairedOrbit(
            time_us=time_us,
            semi_major_axis_m=semi_major_axis_m,
            chunk_id=1,
            density_time_us=time_us,
            density_kg_m3=density_kg_m3,
        ))
        semi_major_axis_m -= (
            beta_eff
            * density_kg_m3
            * math.sqrt(EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * semi_major_axis_m)
            * interval_s
        )
    return pairs


def test_global_cumulative_fit_recovers_one_beta_eff():
    """Input: exact three-year-style cumulative line. Output: original global beta_eff."""
    expected_beta = 0.01
    points = build_integral_points(exact_drag_pairs(expected_beta))

    actual_beta = fit_global_beta(points)

    assert actual_beta == pytest.approx(expected_beta)


def test_global_fit_curve_starts_from_each_chunk():
    """Input: two chunks separated without a valid interval. Output: two zero-based blocks."""
    pairs = exact_drag_pairs(0.01)
    second_chunk = [
        PairedOrbit(
            time_us=pair.time_us + 100_000_000_000,
            semi_major_axis_m=pair.semi_major_axis_m,
            chunk_id=2,
            density_time_us=pair.density_time_us + 100_000_000_000,
            density_kg_m3=pair.density_kg_m3,
        )
        for pair in pairs
    ]

    points = build_integral_points([*pairs, *second_chunk])

    assert {point.block_index for point in points} == {1, 2}
    assert sum(point.block_index == 1 for point in points) == 4
    assert sum(point.block_index == 2 for point in points) == 4


def test_applied_beta_produces_pod_scale_curve():
    """Input: exact cumulative points and fitted beta. Output: zero prediction residual."""
    points = build_integral_points(exact_drag_pairs(0.01))

    fitted = apply_global_beta(points, fit_global_beta(points))

    assert max(abs(point.residual_m) for point in fitted) < 1.0e-8
