"""Check the stored four-curve Phase 3 to Phase 4 comparison input."""

import sys
from pathlib import Path


CODE_DIRECTORY = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIRECTORY))

from prep_phase4_model_comparison import (
    EXPECTED_MINUTE_COUNT,
    EXPECTED_STORM_COUNT,
    build_comparison_series,
)


def test_comparison_aligns_all_saved_phase3_and_phase4_minutes() -> None:
    """Input: saved Phase 3 and Phase 4 SQLite. Output: aligned four-curve rows."""
    series = build_comparison_series()

    assert len(series) == EXPECTED_STORM_COUNT
    assert sum(len(storm.time_us) for storm in series) == EXPECTED_MINUTE_COUNT
    assert all(len(storm.time_us) == len(storm.rho_phase4_d_kg_m3) for storm in series)
