"""Recalculate retrospective quiet-pair pre-slot density-ratio medians."""

import csv
from datetime import datetime
from pathlib import Path

import numpy as np

from output.report.prep_phase3_anytime_quiet_pairs import (
    MINUTE_US, SLOT_MINUTES, save_rows,
)
from output.report.prep_phase3_rquiet_candidates import pair_candidates


PAIR_SOURCE = Path("output/report/phase3_anytime_quiet_pairs_h10_le25.csv")
REPORT = Path("output/report/phase3_rquiet_pre_median_candidates_25.csv")


def slot_start_us(utc_text: str) -> int:
    """Input: UTC ISO timestamp. Output: epoch microseconds at slot start."""
    return int(datetime.fromisoformat(utc_text).timestamp() * 1_000_000)


def paired_slot_ratios(start_us: int, log_ratios: dict[int, float]) -> np.ndarray:
    """Input: slot start and {minute_us: log ratio}. Output: paired minute ratios."""
    return np.array([
        float(np.exp(log_ratios[minute_us]))
        for minute_us in range(start_us, start_us + SLOT_MINUTES * MINUTE_US, MINUTE_US)
        if minute_us in log_ratios
    ])


def candidate_rows(pairs: list[dict], log_ratios: dict[int, float]) -> list[dict]:
    """Input: [retrospective pair], minute log ratios. Output: [pre-median QC]."""
    rows = []
    for pair in pairs:
        before = paired_slot_ratios(slot_start_us(pair["pre_start_utc"]), log_ratios)
        after = paired_slot_ratios(slot_start_us(pair["post_start_utc"]), log_ratios)
        pre_median = float(np.median(before))
        post_median = float(np.median(after))
        rows.append({
            "storm_id": pair["storm_id"],
            "first_strong_minimum_utc": pair["first_strong_minimum_utc"],
            "pre_start_utc": pair["pre_start_utc"],
            "pre_distance_from_first_minimum_hours": pair[
                "pre_distance_from_first_minimum_hours"],
            "pre_ap": pair["pre_ap"],
            "pre_mean_sme_nt": pair["pre_mean_sme_nt"],
            "pre_mean_h10_nt": pair["pre_mean_h10_nt"],
            "pre_paired_minutes": len(before),
            "r_pre_median_candidate": pre_median,
            "post_start_utc": pair["post_start_utc"],
            "post_distance_from_last_minimum_hours": pair[
                "post_distance_from_last_minimum_hours"],
            "post_ap": pair["post_ap"],
            "post_mean_sme_nt": pair["post_mean_sme_nt"],
            "post_mean_h10_nt": pair["post_mean_h10_nt"],
            "post_paired_minutes": len(after),
            "r_post_median_diagnostic": post_median,
            "post_pre_median_relative_gap": post_median / pre_median - 1,
            "status": "retrospective_candidate_not_rquiet",
        })
    return rows


def main() -> None:
    """Input: frozen density source and selected pair CSV. Output: 25-row QC CSV."""
    with PAIR_SOURCE.open(encoding="utf-8-sig", newline="") as source:
        pairs = list(csv.DictReader(source))
    if len(pairs) != 25:
        raise ValueError(f"Expected 25 pairs, found {len(pairs)}.")
    targets = {
        minute_us: ["candidate"]
        for pair in pairs
        for field in ("pre_start_utc", "post_start_utc")
        for minute_us in range(
            slot_start_us(pair[field]),
            slot_start_us(pair[field]) + SLOT_MINUTES * MINUTE_US,
            MINUTE_US,
        )
    }
    log_ratios = pair_candidates(targets)
    rows = candidate_rows(pairs, log_ratios)
    save_rows(rows, REPORT)
    print(f"Saved {len(rows)} retrospective candidates to {REPORT}")


if __name__ == "__main__":
    main()
