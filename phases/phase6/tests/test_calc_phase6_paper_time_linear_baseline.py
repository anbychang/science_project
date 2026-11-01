from phases.phase6.code.calc_phase6_paper_time_linear_baseline import (
    ANCHOR_2024_RATE_M_DAY,
    ANCHOR_2024_TIME_US,
    ANCHOR_2026_RATE_M_DAY,
    ANCHOR_2026_TIME_US,
    paper_time_baseline,
)


def test_time_baseline_matches_both_paper_dates():
    """Input: both paper anchor dates.
    Output: exact published quiet-time rates."""
    assert paper_time_baseline(ANCHOR_2024_TIME_US).rate_m_day == ANCHOR_2024_RATE_M_DAY
    assert paper_time_baseline(ANCHOR_2026_TIME_US).rate_m_day == ANCHOR_2026_RATE_M_DAY


def test_time_baseline_is_linear_at_midpoint():
    """Input: timestamp halfway between both anchors.
    Output: arithmetic midpoint of both rates."""
    midpoint_us = (ANCHOR_2024_TIME_US + ANCHOR_2026_TIME_US) // 2
    expected_rate = (ANCHOR_2024_RATE_M_DAY + ANCHOR_2026_RATE_M_DAY) / 2
    assert paper_time_baseline(midpoint_us).rate_m_day == expected_rate


def test_time_baseline_extrapolates_to_2023():
    """Input: one 2023 timestamp.
    Output: backward-extrapolated rate on the same straight line."""
    baseline = paper_time_baseline(ANCHOR_2024_TIME_US - 180 * 86_400_000_000)
    assert baseline is not None
    assert baseline.source_role == "backward_extrapolation"


def test_time_baseline_does_not_extrapolate_to_2022():
    """Input: year outside the selected scope.
    Output: no decay rate."""
    assert paper_time_baseline(ANCHOR_2024_TIME_US - 500 * 86_400_000_000) is None
