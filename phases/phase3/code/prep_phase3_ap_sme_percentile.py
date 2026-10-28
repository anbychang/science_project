"""Compare low-tail median definitions for observed ap and SME."""

import csv
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from phases.phase3.code.prep_phase3_ap_check import AP_SOURCE, read_ap_minutes
from phases.phase3.code.prep_phase3_sme_check import (
    FIRST_TIME, MINUTES_PER_DAY, SOURCE, event_center, read_source,
)


REPORT = Path("phases/phase3/data/analysis/phase3_ap_sme_low_tail_percentiles.csv")


def lower_tail_median(values: np.ndarray, fraction: float) -> float:
    """Input: [finite values], fraction in (0, 1]. Output: lower-tail median."""
    count = max(1, round(len(values) * fraction))
    return float(np.median(np.partition(values, count - 1)[:count]))


def summarize(ap: np.ndarray, sme: np.ndarray, label: str) -> dict:
    """Input: paired ap/SME minutes and subset label. Output: percentile row."""
    below_ap4 = float(np.mean(ap < 4))
    at_most_ap4 = float(np.mean(ap <= 4))
    ap4_midrank = (below_ap4 + at_most_ap4) / 2
    matched_low_tail = min(1.0, 2 * ap4_midrank)
    tail_min = 2 * below_ap4
    tail_max = min(1.0, 2 * at_most_ap4)
    sme65_fraction = float(np.mean(sme <= 65))
    return {
        "subset": label,
        "paired_minutes": len(ap),
        "ap_below4_fraction": below_ap4,
        "ap_equal4_fraction": float(np.mean(ap == 4)),
        "ap_at_most4_fraction": at_most_ap4,
        "lower_tail_fraction_min_for_ap_median4": tail_min,
        "lower_tail_fraction_max_for_ap_median4": tail_max,
        "sme_median_near_lower_tail_min_nt": lower_tail_median(sme, tail_min),
        "sme_median_near_lower_tail_max_nt": lower_tail_median(sme, tail_max),
        "chosen_midpoint_lower_tail_fraction": matched_low_tail,
        "sme_median_of_chosen_lower_tail_nt": lower_tail_median(sme, matched_low_tail),
        "sme_q25_cutoff_nt": float(np.quantile(sme, 0.25)),
        "sme_median_of_bottom25_nt": lower_tail_median(sme, 0.25),
        "sme_median_of_bottom_ap_le4_fraction_nt": lower_tail_median(sme, at_most_ap4),
        "ap_median_of_bottom_ap_le4_fraction": lower_tail_median(ap, at_most_ap4),
        "sme_at_most65_fraction": sme65_fraction,
        "ap_median_of_tail_matched_to_sme65": lower_tail_median(ap, 2 * sme65_fraction),
    }


def main() -> None:
    """Input: frozen three-year ap/SME and events. Output: percentile CSV."""
    ap, _ = read_ap_minutes(AP_SOURCE)
    sme, events = read_source(SOURCE)
    valid_sme = np.isfinite(sme)
    event_window = np.zeros(len(sme), dtype=bool)
    for _, t0_us in events:
        center = event_center(t0_us)
        event_window[center - 2 * MINUTES_PER_DAY:
                     center + 4 * MINUTES_PER_DAY] = True
    masks = [("all_common_minutes", valid_sme),
             ("outside_25_event_windows", valid_sme & ~event_window)]
    for year in range(2023, 2026):
        start = int((datetime(year, 7, 1, tzinfo=timezone.utc) - FIRST_TIME)
                    .total_seconds() // 60)
        end = int((datetime(year + 1, 7, 1, tzinfo=timezone.utc) - FIRST_TIME)
                  .total_seconds() // 60)
        yearly = np.zeros(len(sme), dtype=bool)
        yearly[start:end] = True
        masks.append((f"{year}-07_to_{year + 1}-06", yearly & valid_sme))
    rows = [summarize(ap[mask], sme[mask], label) for label, mask in masks]
    with REPORT.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {REPORT}")


if __name__ == "__main__":
    main()
