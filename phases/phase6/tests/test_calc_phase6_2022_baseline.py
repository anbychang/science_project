from phases.phase6.code.calc_phase6_2022_baseline import (
    DAY_US,
    OrbitMean,
    calculate_chunk_baseline,
)


def orbit_rows(day_count: int, rate_m_day: float) -> list[OrbitMean]:
    """Input: daily sample count and linear rate in m/day.
    Output: one synthetic same-chunk orbit series."""
    return [
        OrbitMean(
            time_us=day * DAY_US,
            orbit_start_time_us=day * DAY_US,
            semi_major_axis_m=7_000_000.0 + rate_m_day * day,
            chunk_id=3,
        )
        for day in range(day_count)
    ]


def test_90day_baseline_recovers_linear_rate():
    """Input: 91 days declining 25 m/day.
    Output: evaluated trailing fit with exact -25 m/day slope."""
    baseline = calculate_chunk_baseline(orbit_rows(91, -25.0))

    assert baseline.status == "evaluated"
    assert baseline.rate_m_day == -25.0


def test_short_chunk_is_not_fit_as_90_days():
    """Input: 30 days from one source chunk.
    Output: explicit insufficient-coverage result without a slope."""
    baseline = calculate_chunk_baseline(orbit_rows(30, -25.0))

    assert baseline.status == "insufficient_90day_coverage"
    assert baseline.rate_m_day is None
