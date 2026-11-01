from datetime import date

from phases.phase6.code.prep_phase6_quiet_audit import (
    DensitySample,
    QuietDay,
    nearest_density_sample,
    quiet_windows,
)


def test_quiet_windows_returns_only_consecutive_days():
    """Input: three candidate days with one one-day gap.
    Output: only the consecutive two-day window."""
    days = [
        QuietDay(date(2024, 1, 1), 3.0, 100.0, 10),
        QuietDay(date(2024, 1, 2), 4.0, 120.0, 10),
        QuietDay(date(2024, 1, 4), 2.0, 110.0, 10),
    ]

    assert quiet_windows(days) == [(days[0], days[1])]


def test_nearest_density_sample_respects_matching_limit():
    """Input: one nearby and one distant density sample.
    Output: only the nearby sample may match an orbit."""
    samples = [
        DensitySample(1_020_000_000, 1.0e-12, "near.ZIP"),
        DensitySample(1_100_000_000, 2.0e-12, "far.ZIP"),
    ]

    assert nearest_density_sample(samples, 1_000_000_000) == samples[0]
    assert nearest_density_sample(samples, 1_180_000_000) is None
