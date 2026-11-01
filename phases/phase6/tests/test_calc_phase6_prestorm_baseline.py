from phases.phase6.code.calc_phase6_prestorm_baseline import (
    DAY_US,
    OrbitMean,
    fit_summary,
    quiet_rows,
)


def test_fit_summary_recovers_linear_daily_slope():
    """Input: five orbit means declining 10 m per day.
    Output: exact -10 m/day slope with zero OLS uncertainty."""
    rows = [
        OrbitMean(index * DAY_US, 7_000_000.0 - 10.0 * index, index * DAY_US, 1)
        for index in range(5)
    ]

    fit = fit_summary(rows)

    assert fit.rate_m_day == -10.0
    assert fit.rate_1sigma_m_day == 0.0


def test_quiet_rows_uses_orbit_end_utc_day():
    """Input: orbit means on two UTC days and one accepted day key.
    Output: only rows ending on the accepted UTC day."""
    rows = [
        OrbitMean(DAY_US + 1, 1.0, DAY_US, 1),
        OrbitMean(2 * DAY_US + 1, 2.0, 2 * DAY_US, 1),
    ]

    assert quiet_rows(rows, {DAY_US}) == [rows[0]]
