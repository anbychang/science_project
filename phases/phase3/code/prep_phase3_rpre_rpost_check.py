"""Compare direct pre/post L2-to-quiet-MSIS ratios for 25 events."""

import csv
import math
from pathlib import Path

import numpy as np

from phases.phase3.code.prep_phase3_rquiet_candidates import pair_candidates
from phases.phase3.code.prep_phase3_sme_check import (
    FIRST_TIME, MINUTES_PER_DAY, SOURCE, event_center, read_source,
)


MINUTE_US = 60_000_000
FIRST_MINUTE_US = int(FIRST_TIME.timestamp() * 1_000_000)
PRE = Path("phases/phase3/data/analysis/phase3_rpre_direct_25.csv")
REPORT = Path("phases/phase3/data/analysis/phase3_rpre_rpost_25.csv")


def read_pre() -> dict:
    """Input: direct pre-window CSV. Output: {storm_id: pre ratio row}."""
    with PRE.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    return {row["storm_id"]: row for row in rows
            if row["baseline_width_minutes"] == str(MINUTES_PER_DAY)}


def post_targets(events: list[tuple[str, int]]) -> dict:
    """Input: [(storm_id, t0_us)]. Output: {post minute_us: [candidate]}."""
    targets = {}
    for _, t0_us in events:
        start = event_center(t0_us) + 4 * MINUTES_PER_DAY
        for index in range(start, start + MINUTES_PER_DAY):
            targets[FIRST_MINUTE_US + index * MINUTE_US] = ["candidate"]
    return targets


def compare(events: list[tuple[str, int]], pre: dict, ratios: dict) -> list[dict]:
    """Input: events, pre rows, post log ratios. Output: [pre/post rows]."""
    rows = []
    for storm_id, t0_us in events:
        start = event_center(t0_us) + 4 * MINUTES_PER_DAY
        values = np.array([
            ratios[FIRST_MINUTE_US + index * MINUTE_US]
            for index in range(start, start + MINUTES_PER_DAY)
            if FIRST_MINUTE_US + index * MINUTE_US in ratios
        ])
        pre_ratio = float(pre[storm_id]["r_pre_log_mean"])
        post_ratio = math.exp(float(np.mean(values))) if len(values) else None
        rows.append({
            "storm_id": storm_id,
            "pre_r_log_mean": pre_ratio,
            "pre_paired_minutes": pre[storm_id]["paired_minutes"],
            "post_r_log_mean": post_ratio if post_ratio is not None else "",
            "post_paired_minutes": len(values),
            "post_over_pre_ratio": post_ratio / pre_ratio if post_ratio is not None else "",
            "post_minus_pre_percent": 100 * (post_ratio / pre_ratio - 1)
            if post_ratio is not None else "",
        })
    return rows


def main() -> None:
    """Input: frozen event times, density, direct pre ratios. Output: comparison CSV."""
    _, events = read_source(SOURCE)
    ratios = pair_candidates(post_targets(events))
    rows = compare(events, read_pre(), ratios)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {REPORT}; paired {len(ratios)} post minutes")


if __name__ == "__main__":
    main()
