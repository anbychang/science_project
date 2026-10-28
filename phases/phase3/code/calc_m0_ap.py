"""Build the retrospective seven-value Ap history specified by MSIS."""

from datetime import datetime, time, timedelta, timezone


THREE_HOURS = timedelta(hours=3)


def msis_ap_history(sample_time: datetime, ap_slots: dict) -> list[float] | None:
    """Input: UTC epoch and {3-hour slot start: ap}. Output: MSIS Ap[7] or None."""
    if sample_time.tzinfo is None or sample_time.utcoffset() != timedelta(0):
        raise ValueError("MSIS Ap history needs a UTC epoch.")
    slot_start = sample_time.replace(
        hour=sample_time.hour - sample_time.hour % 3,
        minute=0, second=0, microsecond=0,
    )
    day_start = datetime.combine(sample_time.date(), time.min, timezone.utc)
    daily = [ap_slots.get(day_start + offset * THREE_HOURS)
             for offset in range(8)]
    recent = [ap_slots.get(slot_start - offset * THREE_HOURS)
              for offset in range(4)]
    older_12_33 = [ap_slots.get(slot_start - offset * THREE_HOURS)
                   for offset in range(4, 12)]
    older_36_57 = [ap_slots.get(slot_start - offset * THREE_HOURS)
                   for offset in range(12, 20)]
    if any(value is None for value in daily + recent + older_12_33 + older_36_57):
        return None
    return [sum(daily) / 8, *recent, sum(older_12_33) / 8,
            sum(older_36_57) / 8]
