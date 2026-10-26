"""Explore pre-event ap thresholds and SME=55..75 nT calibration candidates."""

import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from output.report.prep_phase3_ap_check import AP_SOURCE, read_ap_minutes
from output.report.prep_phase3_sme_check import (
    FIRST_TIME, MINUTES_PER_DAY, SOURCE, event_center, read_source,
)
from satellite_orbit.calculation.density.calc_msis_p2_4 import (
    calculate_msis_density, load_msis_weather, sample_drivers,
)
from satellite_orbit.data.density.load_dnsapod import load_dnsapod
from satellite_orbit.phase2.prep_24_density_t0_phase import (
    DensityPaths, checked_manifest, minute_label,
)


REPORT_FOLDER = Path("output/report")
FIRST_MINUTE_US = int(FIRST_TIME.timestamp() * 1_000_000)
MINUTE_US = 60_000_000
DAY_US = MINUTES_PER_DAY * MINUTE_US


def candidate_targets(eligible: np.ndarray,
                      events: list[tuple[str, int]]) -> tuple[dict, dict]:
    """Input: eligible minute mask and events. Output: {minute_us: [storm]}, {storm: t0_index}."""
    eligible = eligible.copy()
    targets = defaultdict(list)
    centers = {}
    other_event_windows = np.zeros(len(eligible), dtype=bool)
    for _, t0_us in events:
        center = event_center(t0_us)
        other_event_windows[center - 2 * MINUTES_PER_DAY:
                            center + 4 * MINUTES_PER_DAY] = True
    eligible &= ~other_event_windows
    for storm_id, t0_us in events:
        center = event_center(t0_us)
        centers[storm_id] = center
        for index in np.flatnonzero(eligible[center - 14 * MINUTES_PER_DAY:
                                               center - 2 * MINUTES_PER_DAY]):
            minute_us = FIRST_MINUTE_US + (
                center - 14 * MINUTES_PER_DAY + int(index)
            ) * MINUTE_US
            targets[minute_us].append(storm_id)
    return targets, centers


def source_days(targets: dict) -> set[str]:
    """Input: selected minute labels. Output: UTC source days including midnight support."""
    days = set()
    for minute_us in targets:
        label = datetime.fromtimestamp(minute_us / 1_000_000, timezone.utc)
        days.add(label.strftime("%Y%m%d"))
        if minute_us % DAY_US == 0:
            days.add((label - timedelta(days=1)).strftime("%Y%m%d"))
    return days


def pair_candidates(targets: dict) -> dict:
    """Input: {minute_us: [storm]}. Output: {minute_us: log(L2/MSISq)}."""
    paths = DensityPaths()
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    paired_sums = defaultdict(lambda: [0.0, 0.0, 0])
    files = checked_manifest(paths, source_days(targets))
    for file_index, zip_path in enumerate(files, 1):
        samples = []
        drivers = []
        for sample in load_dnsapod(zip_path)["samples"]:
            minute_us = minute_label(sample["time_us"])
            if minute_us not in targets or sample["rho_l2_kg_m3"] is None:
                continue
            driver = sample_drivers(sample["time_us"], weather)
            if driver is None:
                continue
            driver["ap_values"] = [4.0] * 7
            samples.append((minute_us, sample))
            drivers.append(driver)
        densities = calculate_msis_density([sample for _, sample in samples], drivers)
        for (minute_us, sample), rho_msis in zip(samples, densities, strict=True):
            if rho_msis is None:
                continue
            totals = paired_sums[minute_us]
            totals[0] += sample["rho_l2_kg_m3"]
            totals[1] += rho_msis
            totals[2] += 1
        if file_index % 25 == 0 or file_index == len(files):
            print(f"Paired {file_index}/{len(files)} source days", flush=True)
    return {minute_us: math.log(l2 / model)
            for minute_us, (l2, model, _) in paired_sums.items()}


def summarize(targets: dict, centers: dict, ratios: dict) -> list[dict]:
    """Input: targets, t0 centers, minute log ratios. Output: 1/3/12-day event rows."""
    by_storm = defaultdict(list)
    for minute_us, storm_ids in targets.items():
        index = (minute_us - FIRST_MINUTE_US) // MINUTE_US
        for storm_id in storm_ids:
            by_storm[storm_id].append(index)
    rows = []
    for storm_id, center in centers.items():
        for lookback_days in (1, 3, 12):
            selected = sorted(index for index in by_storm[storm_id]
                              if index >= center - (lookback_days + 2) * MINUTES_PER_DAY)
            longest_run = 0
            current_run = 0
            previous = None
            for index in selected:
                current_run = current_run + 1 if previous == index - 1 else 1
                longest_run = max(longest_run, current_run)
                previous = index
            paired = [(index, ratios[FIRST_MINUTE_US + index * MINUTE_US])
                      for index in selected
                      if FIRST_MINUTE_US + index * MINUTE_US in ratios]
            values = np.array([value for _, value in paired])
            first = datetime.fromtimestamp((FIRST_MINUTE_US + selected[0] * MINUTE_US)
                                           / 1_000_000, timezone.utc) if selected else None
            last = datetime.fromtimestamp((FIRST_MINUTE_US + selected[-1] * MINUTE_US)
                                          / 1_000_000, timezone.utc) if selected else None
            rows.append({
                "storm_id": storm_id,
                "lookback_days_before_t0_minus_2d": lookback_days,
                "candidate_minutes": len(selected),
                "longest_contiguous_minutes": longest_run,
                "paired_minutes": len(paired),
                "first_candidate_utc": first.isoformat() if first else "",
                "last_candidate_utc": last.isoformat() if last else "",
                "median_log_ratio": float(np.median(values)) if len(values) else "",
                "rquiet_candidate": float(np.exp(np.median(values))) if len(values) else "",
                "rquiet_q1": float(np.exp(np.quantile(values, 0.25))) if len(values) else "",
                "rquiet_q3": float(np.exp(np.quantile(values, 0.75))) if len(values) else "",
            })
    return rows


def summarize_runs(targets: dict, centers: dict, ratios: dict) -> list[dict]:
    """Input: targets, t0 centers, log ratios. Output: [contiguous candidate intervals]."""
    by_storm = defaultdict(list)
    for minute_us, storm_ids in targets.items():
        for storm_id in storm_ids:
            by_storm[storm_id].append(minute_us)
    runs = []
    for storm_id, minutes in by_storm.items():
        minutes.sort()
        start = previous = minutes[0]
        for minute_us in minutes[1:] + [None]:
            if minute_us is not None and minute_us == previous + MINUTE_US:
                previous = minute_us
                continue
            values = [ratios[key] for key in range(start, previous + MINUTE_US, MINUTE_US)
                      if key in ratios]
            runs.append({
                "storm_id": storm_id,
                "start_utc": datetime.fromtimestamp(start / 1_000_000, timezone.utc).isoformat(),
                "end_exclusive_utc": datetime.fromtimestamp(
                    (previous + MINUTE_US) / 1_000_000, timezone.utc).isoformat(),
                "duration_minutes": (previous - start) // MINUTE_US + 1,
                "paired_minutes": len(values),
                "rquiet_run_candidate": float(np.exp(np.median(values))) if values else "",
                "days_before_t0": (FIRST_MINUTE_US + centers[storm_id] * MINUTE_US
                                   - start) / DAY_US,
            })
            start = previous = minute_us
    return runs


def main() -> None:
    """Input: frozen 3-year sources. Output: Phase 3 threshold comparison CSVs."""
    ap_minutes, _ = read_ap_minutes(AP_SOURCE)
    sme, events = read_source(SOURCE)
    quiet_sme = np.isfinite(sme) & (sme >= 55) & (sme <= 75)
    ap_rules = (("ap4", ap_minutes == 4),
                ("ap_le4", ap_minutes <= 4),
                ("ap_le7", ap_minutes <= 7))
    selected = {name: candidate_targets(quiet_sme & ap_mask, events)
                for name, ap_mask in ap_rules}
    broad_targets = selected["ap_le7"][0]
    print(f"Selected {len(broad_targets)} unique candidate minute labels", flush=True)
    ratios = pair_candidates(broad_targets)
    for name, (targets, centers) in selected.items():
        rows = summarize(targets, centers, ratios)
        report = REPORT_FOLDER / f"phase3_rquiet_{name}_sme55_75_candidates.csv"
        with report.open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        runs = summarize_runs(targets, centers, ratios)
        run_report = REPORT_FOLDER / f"phase3_rquiet_{name}_sme55_75_runs.csv"
        with run_report.open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.DictWriter(output, fieldnames=list(runs[0]))
            writer.writeheader()
            writer.writerows(runs)
        print(f"Saved {report} and {run_report}", flush=True)
    print(f"Paired {len(ratios)} broad-condition minute labels", flush=True)


if __name__ == "__main__":
    main()
