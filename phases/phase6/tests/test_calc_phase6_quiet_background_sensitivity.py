from phases.phase6.code.calc_phase6_quiet_background_excess_decay import (
    DAY_US,
    OrbitMean,
)
from phases.phase6.code.calc_phase6_quiet_background_sensitivity import (
    EventContext,
    leave_one_day_out,
    summarize_sensitivity,
)


def test_leave_one_day_out_refits_each_quiet_day():
    """Input: two quiet days with linear -10 m/day orbit means.
    Output: two omission fits that preserve the exact background rate."""
    context = EventContext("S1", 3 * DAY_US, 0, 4, 2, 6.0, -120.0, -10.0, 60.0)
    rows = [
        OrbitMean(day * DAY_US + offset, day * DAY_US, 1000.0 - 10.0 * (day + offset / DAY_US), 4)
        for day in range(2)
        for offset in (0, DAY_US // 3, 2 * DAY_US // 3)
    ]

    results = leave_one_day_out(context, rows)

    assert len(results) == 2
    assert all(abs(item.rate_m_day + 10.0) < 1e-9 for item in results)


def test_single_quiet_day_has_no_leave_one_day_out_result():
    """Input: one quiet day and a positive reference result.
    Output: explicit insufficient sensitivity status."""
    context = EventContext("S1", DAY_US, 0, 4, 1, 6.0, -120.0, -10.0, 60.0)
    rows = [
        OrbitMean(offset, 0, 1000.0, 4)
        for offset in (0, DAY_US // 3, 2 * DAY_US // 3)
    ]

    summary = summarize_sensitivity(context, leave_one_day_out(context, rows))

    assert summary.status == "insufficient_quiet_days"
    assert summary.sign_stable is None
