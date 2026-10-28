"""Calculate per-event pre-window density ratios before fitting G or tau."""

import csv
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from phases.phase3.code.prep_phase3_rquiet_candidates import pair_candidates
from phases.phase3.code.prep_phase3_sme_check import (
    FIRST_TIME, MINUTES_PER_DAY, SOURCE, event_center, read_source,
)


MINUTE_US = 60_000_000
FIRST_MINUTE_US = int(FIRST_TIME.timestamp() * 1_000_000)
REPORT = Path("phases/phase3/data/analysis/phase3_rpre_direct_25.csv")


def target_minutes(events: list[tuple[str, int]]) -> dict:
    """Input: [(storm_id, t0_us)]. Output: {pre-window minute_us: [candidate]}."""
    targets = {}
    for _, t0_us in events:
        end = event_center(t0_us) - 2 * MINUTES_PER_DAY
        for index in range(end - 3600, end):
            targets[FIRST_MINUTE_US + index * MINUTE_US] = ["candidate"]
    return targets


def event_window_mask(events: list[tuple[str, int]], size: int) -> np.ndarray:
    """Input: events, source minute count. Output: known event-window mask."""
    mask = np.zeros(size, dtype=bool)
    for _, t0_us in events:
        center = event_center(t0_us)
        mask[center - 2 * MINUTES_PER_DAY:center + 4 * MINUTES_PER_DAY] = True
    return mask


def summarize(events: list[tuple[str, int]], ratios: dict,
              event_mask: np.ndarray) -> list[dict]:
    """Input: events, minute log ratios, event mask. Output: direct pre-window rows."""
    rows = []
    for storm_id, t0_us in events:
        end = event_center(t0_us) - 2 * MINUTES_PER_DAY
        for width_minutes in (MINUTES_PER_DAY, 3600):
            start = end - width_minutes
            values = np.array([
                ratios[FIRST_MINUTE_US + index * MINUTE_US]
                for index in range(start, end)
                if FIRST_MINUTE_US + index * MINUTE_US in ratios
            ])
            rows.append({
                "storm_id": storm_id,
                "baseline_start_utc": datetime.fromtimestamp(
                    (FIRST_MINUTE_US + start * MINUTE_US) / 1_000_000,
                    timezone.utc).isoformat(),
                "baseline_end_exclusive_utc": datetime.fromtimestamp(
                    (FIRST_MINUTE_US + end * MINUTE_US) / 1_000_000,
                    timezone.utc).isoformat(),
                "baseline_width_minutes": width_minutes,
                "paired_minutes": len(values),
                "known_other_event_minutes": int(event_mask[start:end].sum()),
                "r_pre_log_mean": math.exp(float(np.mean(values))) if len(values) else "",
                "r_pre_log_median": math.exp(float(np.median(values))) if len(values) else "",
                "ratio_q1": math.exp(float(np.quantile(values, 0.25))) if len(values) else "",
                "ratio_q3": math.exp(float(np.quantile(values, 0.75))) if len(values) else "",
            })
    return rows


def main() -> None:
    """Input: frozen event times and native density. Output: direct R_pre CSV."""
    sme, events = read_source(SOURCE)
    targets = target_minutes(events)
    print(f"Selected {len(targets)} unique pre-window minutes", flush=True)
    ratios = pair_candidates(targets)
    rows = summarize(events, ratios, event_window_mask(events, len(sme)))
    with REPORT.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {REPORT}; paired {len(ratios)} minute labels", flush=True)


if __name__ == "__main__":
    main()
