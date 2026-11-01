import pytest

from phases.phase6.code.calc_phase6_storm_excess_decay import (
    DAY_US,
    OrbitMean,
    StormBaseline,
    measure_storm,
)


def piecewise_orbits(chunk_id: int = 4) -> list[OrbitMean]:
    """Input: one source chunk ID.
    Output: [-2, +4] quarter-day samples with faster loss after t0."""
    rows = []
    semi_major_axis_m = 7_000_000.0
    for index in range(25):
        time_us = index * DAY_US // 4
        if index > 0:
            rate_m_day = -40.0 if index <= 8 else -100.0
            semi_major_axis_m += rate_m_day / 4.0
        rows.append(OrbitMean(time_us, time_us, semi_major_axis_m, chunk_id))
    return rows


def test_post_t0_excess_decay_uses_only_four_day_response():
    """Input: background-matching pre-period and -100 m/day post-period.
    Output: zero pre-control error and positive 240 m post-t0 excess loss."""
    baseline = StormBaseline("S1", 2 * DAY_US, 4, 90.0, -40.0, 0.5)

    result = measure_storm(baseline, piecewise_orbits())

    assert result.pre_excess_decay_6_m == pytest.approx(0.0)
    assert result.post_observed_delta_a_6_m == pytest.approx(-400.0)
    assert result.post_background_delta_a_m == pytest.approx(-160.0)
    assert result.post_excess_decay_6_m == pytest.approx(240.0)
    assert result.local_pre_rate_m_day == pytest.approx(-40.0)
    assert result.local_post_excess_decay_6_m == pytest.approx(240.0)


def test_excess_decay_rejects_cross_chunk_window():
    """Input: window rows that disagree with the baseline chunk.
    Output: explicit boundary error instead of a cross-maneuver result."""
    baseline = StormBaseline("S1", 2 * DAY_US, 4, 90.0, -40.0, 0.5)
    rows = piecewise_orbits()
    rows[-1] = OrbitMean(
        rows[-1].time_us, rows[-1].orbit_start_time_us,
        rows[-1].semi_major_axis_m, 5,
    )

    with pytest.raises(ValueError, match="window chunks"):
        measure_storm(baseline, rows)
