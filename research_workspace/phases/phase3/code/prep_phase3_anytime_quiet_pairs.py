"""Explore quiet pre/post matches without fixed offsets from storm minimum."""

import csv
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from research_workspace.phases.phase3.code.prep_phase3_ap_check import AP_SOURCE, read_ap_minutes
from research_workspace.phases.phase3.code.prep_phase3_rquiet_candidates import pair_candidates
from research_workspace.phases.phase3.code.prep_phase3_sme_check import (
    FIRST_TIME, MINUTES_PER_DAY, SOURCE, event_center, read_source,
)


MINUTE_US = 60_000_000
FIRST_MINUTE_US = int(FIRST_TIME.timestamp() * 1_000_000)
SLOT_MINUTES = 180
SME_QUIET_LIMIT_NT = 89.3248675
SYMH_QUIET_MEAN_MIN_NT = -30
SLOT_REPORT = Path("research_workspace/phases/phase3/data/analysis/phase3_anytime_quiet_slots.csv")
PAIR_REPORT = Path("research_workspace/phases/phase3/data/analysis/phase3_anytime_quiet_pairs.csv")


def source_symh_and_extrema(events: list[tuple[str, int]], size: int) -> tuple:
    """Input: events, minute count. Output: [SYM-H], {storm_id: (first, last) indices}."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        symh = np.fromiter(
            (float(value) if value is not None else np.nan
             for (value,) in database.execute(
                 "SELECT symh_nt FROM geomag_1min_v2 ORDER BY time_us")),
            dtype=float, count=size,
        )
        extrema = {}
        for storm_id, _ in events:
            first_us, last_us = database.execute(
                "SELECT MIN(minimum_time_us), MAX(minimum_time_us) "
                "FROM storm_minimum_v2 WHERE storm_id=?", (storm_id,),
            ).fetchone()
            extrema[storm_id] = ((first_us - FIRST_MINUTE_US) // MINUTE_US,
                                 (last_us - FIRST_MINUTE_US) // MINUTE_US)
    return symh, extrema


def quiet_slots(series: dict) -> list[dict]:
    """Input: {ap, sme, symh} minute arrays. Output: low-activity 3-hour slots."""
    slots = []
    ap = series["ap"]
    sme = series["sme"]
    symh = series["symh"]
    for start in range(0, len(sme) - SLOT_MINUTES + 1, SLOT_MINUTES):
        end = start + SLOT_MINUTES
        sme_values = sme[start:end]
        symh_values = symh[start:end]
        if not np.isfinite(sme_values).all() or not np.isfinite(symh_values).all():
            continue
        mean_sme = float(np.mean(sme_values))
        mean_symh = float(np.mean(symh_values))
        if ap[start] <= 4 and mean_sme <= SME_QUIET_LIMIT_NT \
                and mean_symh > SYMH_QUIET_MEAN_MIN_NT:
            slots.append({"start_index": start, "end_index": end,
                          "observed_ap": float(ap[start]),
                          "mean_sme_nt": mean_sme,
                          "mean_symh_nt": mean_symh})
    return slots


def slot_ratios(slots: list[dict]) -> list[dict]:
    """Input: low-activity slots. Output: slots with paired density ratios."""
    targets = {FIRST_MINUTE_US + index * MINUTE_US: ["candidate"]
               for slot in slots
               for index in range(slot["start_index"], slot["end_index"])}
    print(f"Pairing {len(targets)} quiet minute labels", flush=True)
    ratios = pair_candidates(targets)
    paired = []
    for slot in slots:
        values = np.array([
            ratios[FIRST_MINUTE_US + index * MINUTE_US]
            for index in range(slot["start_index"], slot["end_index"])
            if FIRST_MINUTE_US + index * MINUTE_US in ratios
        ])
        if len(values) < 0.8 * SLOT_MINUTES:
            continue
        paired.append({**slot, "paired_minutes": len(values),
                       "mean_log_density_ratio": float(np.mean(values)),
                       "density_ratio": math.exp(float(np.mean(values)))})
    return paired


def utc_minute(index: int) -> str:
    """Input: study minute index. Output: UTC time text."""
    return datetime.fromtimestamp(
        (FIRST_MINUTE_US + index * MINUTE_US) / 1_000_000, timezone.utc
    ).isoformat()


def paired_event_rows(events: list[tuple[str, int]], extrema: dict,
                      slots: list[dict]) -> list[dict]:
    """Input: events, strong-minimum bounds, quiet slots. Output: best pre/post rows."""
    rows = []
    for storm_id, _ in events:
        first, last = extrema[storm_id]
        pre = [slot for slot in slots if slot["end_index"] <= first]
        post = [slot for slot in slots if slot["start_index"] >= last]
        pre_ap = np.array([slot["observed_ap"] for slot in pre])[:, None]
        post_ap = np.array([slot["observed_ap"] for slot in post])[None, :]
        pre_sme = np.array([slot["mean_sme_nt"] for slot in pre])[:, None]
        post_sme = np.array([slot["mean_sme_nt"] for slot in post])[None, :]
        pre_log = np.array([slot["mean_log_density_ratio"] for slot in pre])[:, None]
        post_log = np.array([slot["mean_log_density_ratio"] for slot in post])[None, :]
        ap_gap = abs(pre_ap - post_ap)
        sme_gap = abs(pre_sme - post_sme) / ((pre_sme + post_sme) / 2)
        ratio_gap = np.exp(abs(pre_log - post_log)) - 1
        close = (ap_gap <= 1) & (sme_gap <= 0.20) & (ratio_gap <= 0.10)
        pre_distance = np.array([first - slot["end_index"] for slot in pre])[:, None]
        post_distance = np.array([slot["start_index"] - last for slot in post])[None, :]
        total_distance = pre_distance + post_distance
        if close.any():
            choice = np.unravel_index(
                np.argmin(np.where(close, total_distance, np.inf)), close.shape)
            status = "within_provisional_tolerances"
        else:
            mismatch = np.maximum.reduce((
                np.broadcast_to(ap_gap, sme_gap.shape),
                sme_gap / 0.20,
                ratio_gap / 0.10,
            ))
            choice = np.unravel_index(np.argmin(mismatch), mismatch.shape)
            status = "no_close_pair_best_mismatch"
        before = pre[choice[0]]
        after = post[choice[1]]
        rows.append({
            "storm_id": storm_id,
            "status": status,
            "first_strong_minimum_utc": utc_minute(first),
            "last_strong_minimum_utc": utc_minute(last),
            "pre_start_utc": utc_minute(before["start_index"]),
            "post_start_utc": utc_minute(after["start_index"]),
            "pre_distance_from_first_minimum_hours": float(pre_distance[choice[0], 0]) / 60,
            "post_distance_from_last_minimum_hours": float(post_distance[0, choice[1]]) / 60,
            "pre_ap": before["observed_ap"],
            "post_ap": after["observed_ap"],
            "ap_absolute_gap": float(ap_gap[choice]),
            "pre_mean_sme_nt": before["mean_sme_nt"],
            "post_mean_sme_nt": after["mean_sme_nt"],
            "sme_relative_gap": float(sme_gap[choice]),
            "pre_density_ratio": before["density_ratio"],
            "post_density_ratio": after["density_ratio"],
            "density_ratio_relative_gap": float(ratio_gap[choice]),
            "retrospective_r_quiet_candidate": math.exp(
                (before["mean_log_density_ratio"] + after["mean_log_density_ratio"]) / 2),
        })
    return rows


def save_rows(rows: list[dict], path: Path) -> None:
    """Input: [{field: value}], CSV path. Output: saved CSV."""
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Input: frozen three-year sources. Output: quiet-slot and paired-event CSVs."""
    sme, events = read_source(SOURCE)
    ap, _ = read_ap_minutes(AP_SOURCE)
    symh, extrema = source_symh_and_extrema(events, len(sme))
    selected = quiet_slots({"ap": ap, "sme": sme, "symh": symh})
    print(f"Found {len(selected)} low-activity slots", flush=True)
    slots = slot_ratios(selected)
    for slot in slots:
        slot["start_utc"] = utc_minute(slot["start_index"])
        slot["end_exclusive_utc"] = utc_minute(slot["end_index"])
    save_rows(slots, SLOT_REPORT)
    rows = paired_event_rows(events, extrema, slots)
    save_rows(rows, PAIR_REPORT)
    print(f"Saved {len(slots)} slots and {len(rows)} event pairs", flush=True)


if __name__ == "__main__":
    main()
