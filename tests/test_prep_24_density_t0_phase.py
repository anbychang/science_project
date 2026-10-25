"""Unit checks for P2.4 t0-phase density helpers."""

import pytest

from satellite_orbit.phase2.prep_24_density_t0_phase import (
    coverage_status,
    minute_label,
)


def test_minute_label_uses_assumed_centered_support() -> None:
    """Input: 30-second sample times. Output: their enclosing P2.3 minute labels."""
    assert minute_label(0) == 0
    assert minute_label(29_999_999) == 0
    assert minute_label(30_000_000) == 60_000_000
    assert minute_label(89_999_999) == 60_000_000


def test_coverage_requires_both_l2_and_pair_counts() -> None:
    """Input: expected native samples and counts. Output: 80-percent event status."""
    assert coverage_status(100, 80, 80) == (1, "used")
    assert coverage_status(100, 100, 79) == (0, "excluded_coverage")
    with pytest.raises(ValueError):
        coverage_status(100, 101, 80)
