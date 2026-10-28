"""Check the SME response state before each Phase 3 event window."""

import csv
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from phases.phase3.code.prep_phase3_sme_check import (
    MINUTES_PER_DAY, MINUTE_US, SOURCE, event_center, read_source,
)


REPORT = Path("phases/phase3/data/analysis/phase3_h_at_window_start.csv")
SME_REFERENCE_NT = 65.0
WARMUP_DAYS = 3
TAU_HOURS = (1, 2, 4, 10)


def initial_state(history: np.ndarray, tau_hours: float) -> float:
    """Input: consecutive SME minutes, tau [h]. Output: filtered anomaly before next minute [nT]."""
    if len(history) != WARMUP_DAYS * MINUTES_PER_DAY or not np.isfinite(history).all():
        raise ValueError("An event has incomplete three-day SME history.")
    alpha = math.exp(-1 / (60 * tau_hours))
    state = float(history[0] - SME_REFERENCE_NT)
    for value in history[1:]:
        state = alpha * state + (1 - alpha) * (float(value) - SME_REFERENCE_NT)
    return state


def event_rows(sme: np.ndarray, events: list[tuple[str, int]]) -> list[dict]:
    """Input: [minute SME], [(storm_id, t0_us)]. Output: [window-start H rows]."""
    rows = []
    for storm_id, t0_us in events:
        start_index = event_center(t0_us) - 2 * MINUTES_PER_DAY
        history = sme[start_index - WARMUP_DAYS * MINUTES_PER_DAY:start_index]
        start_us = t0_us // MINUTE_US * MINUTE_US - 2 * MINUTES_PER_DAY * MINUTE_US
        for tau_hours in TAU_HOURS:
            rows.append({
                "storm_id": storm_id,
                "window_start_utc": datetime.fromtimestamp(
                    start_us / 1_000_000, timezone.utc).isoformat(),
                "tau_hours": tau_hours,
                "sme_reference_nt": SME_REFERENCE_NT,
                "warmup_days": WARMUP_DAYS,
                "h_before_window_nt": initial_state(history, tau_hours),
            })
    return rows


def main() -> None:
    """Input: frozen 1-minute SME and events. Output: pre-window H CSV."""
    sme, events = read_source(SOURCE)
    rows = event_rows(sme, events)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {REPORT}: {len(rows)} event-tau states")


if __name__ == "__main__":
    main()
