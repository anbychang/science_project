"""Find near-zero SME-response windows and estimate pre-event density ratios."""

import math
from pathlib import Path

import numpy as np

from phases.phase3.code.prep_phase3_anytime_quiet_pairs import (
    FIRST_MINUTE_US, MINUTE_US, save_rows, source_symh_and_extrema,
    utc_minute,
)
from phases.phase3.code.prep_phase3_ap_check import AP_SOURCE, read_ap_minutes
from phases.phase3.code.prep_phase3_h_zero_frequency import (
    NEAR_ZERO_NT, WARMUP_MINUTES,
)
from phases.phase3.code.prep_phase3_rquiet_candidates import pair_candidates
from phases.phase3.code.prep_phase3_sme_check import SOURCE, read_source
from phases.phase3.code.calc_h_tau import filtered_sme


SME_REFERENCE_NT = 65.0
MIN_RUN_MINUTES = 90
REPORT = Path("phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv")


def near_zero_runs(sme: np.ndarray, ap: np.ndarray) -> list[tuple[int, int]]:
    """Input: [valid 1-minute SME], [ap]. Output: [(start, end) quiet runs]."""
    eligible = (ap <= 4) & (sme <= 100)
    eligible[:WARMUP_MINUTES] = False
    for tau_hours in np.arange(0, 10.00001, 0.25):
        response = filtered_sme(sme, float(tau_hours)) - SME_REFERENCE_NT
        eligible &= abs(response) <= NEAR_ZERO_NT
    edges = np.diff(np.r_[False, eligible, False].astype(int))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    return [(int(start), int(end)) for start, end in zip(starts, ends)
            if end - start >= MIN_RUN_MINUTES]


def nearest_pre_runs(events: list[tuple[str, int]], runs: list[tuple[int, int]],
                     first_minima: dict) -> dict[str, tuple[int, int]]:
    """Input: [events], [runs], {storm: minimum bounds}. Output: {storm: run}."""
    return {
        storm_id: max((run for run in runs if run[1] <= first_minima[storm_id][0]),
                      key=lambda run: run[1])
        for storm_id, _ in events
    }


def nearest_post_runs(events: list[tuple[str, int]], runs: list[tuple[int, int]],
                      extrema: dict) -> dict[str, tuple[int, int]]:
    """Input: [events], [runs], {storm: minimum bounds}. Output: {storm: run}."""
    return {
        storm_id: min((run for run in runs if run[0] >= extrema[storm_id][1]),
                      key=lambda run: run[0])
        for storm_id, _ in events
    }


def paired_ratios(run: tuple[int, int], ratios: dict[int, float]) -> list[float]:
    """Input: minute-index run, {minute_us: log ratio}. Output: paired ratios."""
    values = []
    for index in range(run[0], run[1]):
        minute_us = FIRST_MINUTE_US + index * MINUTE_US
        if minute_us in ratios:
            values.append(math.exp(ratios[minute_us]))
    return values


def report_rows(selected: dict, ratios: dict[int, float],
                series: dict) -> list[dict]:
    """Input: {pre, post} runs, minute ratios, {ap, sme, extrema}. Output: rows."""
    rows = []
    for storm_id, (start, end) in selected["pre"].items():
        post_start, post_end = selected["post"][storm_id]
        pre_values = paired_ratios((start, end), ratios)
        post_values = paired_ratios((post_start, post_end), ratios)
        coverage = len(pre_values) / (end - start)
        distance_days = (series["extrema"][storm_id][0] - end) / 1440
        pre_median = float(np.median(pre_values)) if coverage >= 0.8 else None
        post_median = float(np.median(post_values)) if len(post_values) >= 0.8 * (
            post_end - post_start) else None
        rows.append({
            "storm_id": storm_id,
            "first_strong_minimum_utc": utc_minute(series["extrema"][storm_id][0]),
            "near_zero_start_utc": utc_minute(start),
            "near_zero_end_exclusive_utc": utc_minute(end),
            "distance_before_first_minimum_days": distance_days,
            "run_minutes": end - start,
            "max_observed_ap": float(np.max(series["ap"][start:end])),
            "mean_sme_nt": float(np.mean(series["sme"][start:end])),
            "paired_l2_minutes": len(pre_values),
            "paired_coverage": coverage,
            "r_near_zero_median_candidate": (
                pre_median if pre_median is not None else ""),
            "post_near_zero_start_utc": utc_minute(post_start),
            "post_distance_after_last_minimum_days": (
                post_start - series["extrema"][storm_id][1]) / 1440,
            "post_mean_sme_nt": float(np.mean(series["sme"][post_start:post_end])),
            "post_max_observed_ap": float(np.max(series["ap"][post_start:post_end])),
            "post_paired_l2_minutes": len(post_values),
            "r_post_near_zero_median_diagnostic": (
                post_median if post_median is not None else ""),
            "post_pre_r_relative_gap": (
                post_median / pre_median - 1
                if pre_median is not None and post_median is not None else ""),
            "status": ("candidate_distance_gt_14d" if distance_days > 14
                       else "candidate_within_14d") if coverage >= 0.8
            else "insufficient_l2_coverage",
        })
    return rows


def main() -> None:
    """Input: frozen 3-year SME, ap and L2. Output: 25 near-zero candidates."""
    source_sme, events = read_source(SOURCE)
    source_ap, _ = read_ap_minutes(AP_SOURCE)
    last_valid = int(np.flatnonzero(np.isfinite(source_sme))[-1]) + 1
    sme = source_sme[:last_valid]
    ap = source_ap[:last_valid]
    if not np.isfinite(sme).all():
        raise ValueError("SME has an internal gap; continuous response needs review.")
    runs = near_zero_runs(sme, ap)
    _, extrema = source_symh_and_extrema(events, len(sme))
    selected = {
        "pre": nearest_pre_runs(events, runs, extrema),
        "post": nearest_post_runs(events, runs, extrema),
    }
    targets = {FIRST_MINUTE_US + index * MINUTE_US: ["candidate"]
               for start, end in set(selected["pre"].values())
               | set(selected["post"].values())
               for index in range(start, end)}
    ratios = pair_candidates(targets)
    rows = report_rows(selected, ratios, {"ap": ap, "sme": sme,
                                         "extrema": extrema})
    save_rows(rows, REPORT)
    print(f"Saved {len(rows)} candidates with independent post-run checks")


if __name__ == "__main__":
    main()
