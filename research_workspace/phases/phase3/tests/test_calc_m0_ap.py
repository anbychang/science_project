"""Check the retrospective Ap vector used by NRLMSIS 2.0."""

from datetime import datetime, timedelta, timezone

from research_workspace.phases.phase3.code.calc_m0_ap import msis_ap_history


def test_msis_ap_history_uses_current_three_hour_slot_and_day() -> None:
    """Input: known UTC Ap slots. Output: current-day Ap and current-first history."""
    slot_start = datetime(2024, 5, 11, tzinfo=timezone.utc)
    slots = {slot_start + timedelta(hours=3 * offset): 100.0 + offset
             for offset in range(-20, 8)}
    values = msis_ap_history(slot_start + timedelta(hours=2, minutes=14), slots)
    assert values == [103.5, 100.0, 99.0, 98.0, 97.0, 92.5, 84.5]
    assert msis_ap_history(slot_start + timedelta(hours=3), slots)[1] == 101.0


def test_msis_ap_history_rejects_missing_or_non_utc_slots() -> None:
    """Input: missing current Ap or naive epoch. Output: no vector or clear error."""
    slot_start = datetime(2024, 5, 11, tzinfo=timezone.utc)
    assert msis_ap_history(slot_start, {}) is None
    try:
        msis_ap_history(slot_start.replace(tzinfo=None), {})
    except ValueError as error:
        assert "UTC" in str(error)
    else:
        raise AssertionError("Naive epoch should fail.")
