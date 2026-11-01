from phases.phase6.code.calc_phase6_quiet_background_excess_decay import (
    DAY_US,
    OrbitMean,
    longest_consecutive_days,
    select_quiet_rows,
)


def test_quiet_rows_end_before_event_window():
    """Input: rows on two quiet days and an event starting midday on day two.
    Output: only the complete quiet UTC day before the event window."""
    rows = [
        OrbitMean(DAY_US // 2, 0, 1.0, 3),
        OrbitMean(DAY_US + DAY_US // 4, DAY_US, 2.0, 3),
    ]

    selected = select_quiet_rows(rows, {0, DAY_US}, DAY_US + DAY_US // 2)

    assert selected == [rows[0]]


def test_longest_consecutive_quiet_run_uses_utc_days():
    """Input: two adjacent quiet days and one isolated quiet day.
    Output: longest run of two days."""
    assert longest_consecutive_days({0, DAY_US, 3 * DAY_US}) == 2
