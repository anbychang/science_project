"""Compare pre-event ratios from the 20 lowest-SME minutes per event."""

import csv
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from output.report.prep_phase3_ap_check import AP_SOURCE, read_ap_minutes
from output.report.prep_phase3_rquiet_candidates import pair_candidates
from output.report.prep_phase3_sme_check import (
    FIRST_TIME, MINUTES_PER_DAY, SOURCE, event_center, read_source,
)


MINUTE_US = 60_000_000
FIRST_MINUTE_US = int(FIRST_TIME.timestamp() * 1_000_000)
SUMMARY = Path("output/report/phase3_rquiet_lowest20_summary.csv")
MINUTES = Path("output/report/phase3_rquiet_lowest20_minutes.csv")


def choose_lowest(sme: np.ndarray, ap: np.ndarray, events: list) -> list[dict]:
    """Input: aligned SME/ap minutes and events. Output: [20-minute selections]."""
    event_windows = np.zeros(len(sme), dtype=bool)
    for _, t0_us in events:
        center = event_center(t0_us)
        event_windows[center - 2 * MINUTES_PER_DAY:
                      center + 4 * MINUTES_PER_DAY] = True
    selections = []
    for storm_id, t0_us in events:
        end = event_center(t0_us) - 2 * MINUTES_PER_DAY
        for width_minutes in (MINUTES_PER_DAY, 3600):
            positions = np.arange(end - width_minutes, end)
            valid = np.isfinite(sme[positions]) & ~event_windows[positions]
            for ap_rule in ("ap_le4", "any_ap"):
                allowed = valid & (ap[positions] <= 4 if ap_rule == "ap_le4" else True)
                eligible = positions[allowed]
                ordered = eligible[np.argsort(sme[eligible], kind="stable")]
                selections.append({
                    "storm_id": storm_id,
                    "window_minutes": width_minutes,
                    "ap_rule": ap_rule,
                    "eligible_minutes": len(eligible),
                    "selected": sorted(ordered[:20].tolist()),
                })
    return selections


def minute_utc(index: int) -> str:
    """Input: study minute index. Output: UTC timestamp text."""
    minute_us = FIRST_MINUTE_US + index * MINUTE_US
    return datetime.fromtimestamp(minute_us / 1_000_000, timezone.utc).isoformat()


def summarize(selections: list[dict], series: dict,
              ratios: dict) -> tuple[list[dict], list[dict]]:
    """Input: selections, {sme, ap}, log ratios. Output: (summary rows, minute rows)."""
    sme = series["sme"]
    ap = series["ap"]
    summaries = []
    minute_rows = []
    for selection in selections:
        selected = selection["selected"]
        matched = []
        for index in selected:
            minute_us = FIRST_MINUTE_US + index * MINUTE_US
            log_ratio = ratios.get(minute_us)
            if log_ratio is not None:
                matched.append(log_ratio)
            minute_rows.append({
                "storm_id": selection["storm_id"],
                "window_minutes": selection["window_minutes"],
                "ap_rule": selection["ap_rule"],
                "time_utc": minute_utc(index),
                "sme_nt": float(sme[index]),
                "observed_ap": float(ap[index]),
                "l2_over_msis_quiet": math.exp(log_ratio) if log_ratio is not None else "",
            })
        values = np.array(matched)
        summaries.append({
            "storm_id": selection["storm_id"],
            "window_minutes": selection["window_minutes"],
            "ap_rule": selection["ap_rule"],
            "eligible_minutes": selection["eligible_minutes"],
            "selected_minutes": len(selected),
            "paired_minutes": len(matched),
            "median_selected_sme_nt": float(np.median(sme[selected])) if selected else "",
            "min_selected_sme_nt": float(np.min(sme[selected])) if selected else "",
            "max_selected_sme_nt": float(np.max(sme[selected])) if selected else "",
            "median_observed_ap": float(np.median(ap[selected])) if selected else "",
            "first_selected_utc": minute_utc(selected[0]) if selected else "",
            "last_selected_utc": minute_utc(selected[-1]) if selected else "",
            "median_l2_over_msis_quiet": float(np.exp(np.median(values))) if len(values) else "",
            "ratio_q1": float(np.exp(np.quantile(values, 0.25))) if len(values) else "",
            "ratio_q3": float(np.exp(np.quantile(values, 0.75))) if len(values) else "",
        })
    return summaries, minute_rows


def save_rows(rows: list[dict], path: Path) -> None:
    """Input: [{field: value}], CSV path. Output: saved CSV."""
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Input: frozen 3-year sources. Output: lowest-SME summary and minute CSVs."""
    ap, _ = read_ap_minutes(AP_SOURCE)
    sme, events = read_source(SOURCE)
    selections = choose_lowest(sme, ap, events)
    minute_targets = {FIRST_MINUTE_US + index * MINUTE_US: ["candidate"]
                      for row in selections for index in row["selected"]}
    print(f"Selected {len(minute_targets)} distinct minute labels", flush=True)
    ratios = pair_candidates(minute_targets)
    summaries, minute_rows = summarize(selections, {"sme": sme, "ap": ap}, ratios)
    save_rows(summaries, SUMMARY)
    save_rows(minute_rows, MINUTES)
    print(f"Saved {SUMMARY} and {MINUTES}; paired {len(ratios)} minutes", flush=True)


if __name__ == "__main__":
    main()
