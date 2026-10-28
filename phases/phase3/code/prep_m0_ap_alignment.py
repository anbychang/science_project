"""Recalculate retrospective M0 with MSIS's specified Ap history."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pymsis

from phases.phase0.code.calculation.density.calc_msis_p2_4 import (
    calculate_msis_density, load_msis_weather,
)
from phases.phase0.code.data.density.load_dnsapod import load_dnsapod
from phases.phase2.code.prep_24_density_t0_phase import (
    DensityPaths, checked_manifest, minute_label, minute_targets, required_days,
)
from phases.phase3.code.calc_h_tau import phase_support, phase_weighted_mean
from phases.phase3.code.calc_m0_ap import msis_ap_history
from phases.phase3.code.prep_quiet_msis import (
    OUTPUT as EXISTING_PHASE_DENSITY,
    SOURCE,
    source_event_rows,
)


OUTPUT = Path("phases/phase3/data/sqlite/swarm_a_phase3_m0_ap_alignment_v1.sqlite")
ALGORITHM_VERSION = "phase3_m0_ap_alignment_v1"


def pair_day(zip_path: Path, targets: dict, weather: dict) -> dict:
    """Input: DNSAPOD ZIP, {minute: storms}, weather. Output: corrected paired sums."""
    selected = []
    drivers = []
    for sample in load_dnsapod(zip_path)["samples"]:
        minute_us = minute_label(sample["time_us"])
        storm_ids = targets.get(minute_us)
        if storm_ids is None or sample["rho_l2_kg_m3"] is None:
            continue
        sample_time = datetime.fromtimestamp(sample["time_us"] / 1_000_000,
                                             timezone.utc)
        solar = weather["daily_solar"].get(sample_time.date())
        ap_values = msis_ap_history(sample_time, weather["ap_slots"])
        if solar is None or ap_values is None:
            raise ValueError(f"Missing retrospective weather at {sample_time}.")
        selected.append((sample, storm_ids, minute_us))
        drivers.append({**solar, "ap_values": ap_values})
    densities = calculate_msis_density([item[0] for item in selected], drivers)
    totals = {}
    for (sample, storm_ids, minute_us), density in zip(
        selected, densities, strict=True
    ):
        if density is None:
            raise ValueError(f"Invalid MSIS density at {sample['time_us']}.")
        for storm_id in storm_ids:
            sums = totals.setdefault((storm_id, minute_us), [0.0, 0.0, 0])
            sums[0] += sample["rho_l2_kg_m3"]
            sums[1] += density
            sums[2] += 1
    return totals


def collect_paired_sums(source: sqlite3.Connection, weather: dict) -> dict:
    """Input: frozen P2.6 and weather. Output: {storm/minute: paired sums}."""
    targets = minute_targets(source)
    files = checked_manifest(DensityPaths(), required_days(source))
    totals = {}
    for zip_path in files:
        for key, daily_sums in pair_day(zip_path, targets, weather).items():
            accumulated = totals.setdefault(key, [0.0, 0.0, 0])
            for index in range(3):
                accumulated[index] += daily_sums[index]
    return totals


def prepare_event(storm_id: str, source_rows: list[tuple], totals: dict) -> dict:
    """Input: storm ID, frozen minutes, paired sums. Output: aligned phase series."""
    times = np.fromiter((row[0] for row in source_rows), dtype=np.int64)
    phases = np.fromiter((row[1] for row in source_rows), dtype=float)
    pairs = np.fromiter((row[2] for row in source_rows), dtype=np.int16)
    observed = np.full(len(times), np.nan)
    legacy = np.full(len(times), np.nan)
    aligned = np.full(len(times), np.nan)
    for index, row in enumerate(source_rows):
        sums = totals.get((storm_id, row[0]), [0.0, 0.0, 0])
        if sums[2] != row[2]:
            raise ValueError(f"Paired sample count changed: {storm_id}:{row[0]}.")
        if sums[2]:
            observed[index] = sums[0] / sums[2]
            legacy[index] = row[4]
            aligned[index] = sums[1] / sums[2]
            if not math.isclose(observed[index], row[3], rel_tol=1e-10):
                raise ValueError(f"L2 pairing changed: {storm_id}:{row[0]}.")
    support = phase_support(phases, pairs)
    observed_phase = phase_weighted_mean(observed, pairs, support)
    legacy_phase = phase_weighted_mean(legacy, pairs, support)
    aligned_phase = phase_weighted_mean(aligned, pairs, support)
    valid = support["valid"]
    if any(np.any(~np.isfinite(values[valid]) | (values[valid] <= 0))
           for values in (observed_phase, legacy_phase, aligned_phase)):
        raise ValueError(f"Invalid phase density for {storm_id}.")
    return {"storm_id": storm_id, "time_us": times, "pair_count": pairs,
            "observed": observed, "legacy": legacy, "aligned": aligned,
            "observed_phase": observed_phase, "legacy_phase": legacy_phase,
            "aligned_phase": aligned_phase, "valid": valid}


def verify_existing_phase(database: sqlite3.Connection, event: dict) -> None:
    """Input: existing Phase 3 density and new event. Output: validated old series."""
    rows = database.execute("""
        SELECT time_us,phase_is_valid_80pct,rho_l2_phase_kg_m3,
               rho_msis_full_phase_kg_m3
        FROM phase3_quiet_density_minute
        WHERE storm_id=? ORDER BY time_us
    """, (event["storm_id"],)).fetchall()
    if len(rows) != len(event["time_us"]):
        raise ValueError(f"Existing phase count differs for {event['storm_id']}.")
    times = np.fromiter((row[0] for row in rows), dtype=np.int64)
    valid = np.fromiter((row[1] for row in rows), dtype=bool)
    if (not np.array_equal(times, event["time_us"])
            or not np.array_equal(valid, event["valid"])):
        raise ValueError(f"Existing phase keys differ for {event['storm_id']}.")
    for key, column in (("observed_phase", 2), ("legacy_phase", 3)):
        previous = np.array([row[column] for row, keep in zip(rows, valid, strict=True)
                             if keep], dtype=float)
        if not np.allclose(previous, event[key][valid], rtol=1e-10, atol=0):
            raise ValueError(f"Existing {key} differs for {event['storm_id']}.")


def score_event(event: dict) -> dict:
    """Input: one paired phase event. Output: old and corrected log RMSE."""
    valid = event["valid"]
    observed = event["observed_phase"][valid]
    legacy = event["legacy_phase"][valid]
    aligned = event["aligned_phase"][valid]
    return {"storm_id": event["storm_id"],
            "valid_phase_minutes": int(np.count_nonzero(valid)),
            "rmse_legacy_log_density": float(np.sqrt(np.mean(
                np.log(observed / legacy) ** 2))),
            "rmse_aligned_log_density": float(np.sqrt(np.mean(
                np.log(observed / aligned) ** 2))),
            "median_aligned_over_legacy": float(np.median(aligned / legacy))}


def create_tables(database: sqlite3.Connection) -> None:
    """Input: new SQLite connection. Output: versioned minute and storm tables."""
    database.executescript("""
        CREATE TABLE phase3_m0_ap_alignment_minute (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            paired_sample_count INTEGER NOT NULL,
            rho_l2_kg_m3 REAL,
            rho_m0_legacy_kg_m3 REAL,
            rho_m0_aligned_kg_m3 REAL,
            rho_l2_phase_kg_m3 REAL,
            rho_m0_legacy_phase_kg_m3 REAL,
            rho_m0_aligned_phase_kg_m3 REAL,
            phase_is_valid_80pct INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE phase3_m0_ap_alignment_storm (
            storm_id TEXT PRIMARY KEY,
            valid_phase_minutes INTEGER NOT NULL,
            rmse_legacy_log_density REAL NOT NULL,
            rmse_aligned_log_density REAL NOT NULL,
            median_aligned_over_legacy REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase3_m0_ap_alignment_metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    database.executemany("INSERT INTO phase3_m0_ap_alignment_metadata VALUES (?,?)", (
        ("source", SOURCE.as_posix()),
        ("gfz_ap", DensityPaths().gfz_ap.as_posix()),
        ("solar", DensityPaths().solar.as_posix()),
        ("pymsis_version", pymsis.__version__),
        ("msis_version", "2.0"),
        ("ap_history", "current-day Ap; current 3h slot; 3/6/9h; 12-33h; 36-57h"),
        ("phase_window", "u +/- pi, paired native samples, centered"),
        ("f107", "previous UTC day; centered 81-day F10.7A, unchanged"),
        ("fit_parameters", "none"),
        ("algorithm_version", ALGORITHM_VERSION),
    ))


def insert_event(database: sqlite3.Connection, event: dict) -> None:
    """Input: output SQLite and aligned event. Output: keyed minute and score rows."""
    valid = event["valid"]
    database.executemany("""
        INSERT INTO phase3_m0_ap_alignment_minute VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        (event["storm_id"], int(event["time_us"][index]),
         int(event["pair_count"][index]),
         float(event["observed"][index]) if event["pair_count"][index] else None,
         float(event["legacy"][index]) if event["pair_count"][index] else None,
         float(event["aligned"][index]) if event["pair_count"][index] else None,
         float(event["observed_phase"][index]) if valid[index] else None,
         float(event["legacy_phase"][index]) if valid[index] else None,
         float(event["aligned_phase"][index]) if valid[index] else None,
         int(valid[index]), ALGORITHM_VERSION)
        for index in range(len(event["time_us"]))
    ))
    score = score_event(event)
    database.execute("""
        INSERT INTO phase3_m0_ap_alignment_storm VALUES (?,?,?,?,?,?)
    """, (score["storm_id"], score["valid_phase_minutes"],
          score["rmse_legacy_log_density"], score["rmse_aligned_log_density"],
          score["median_aligned_over_legacy"], ALGORITHM_VERSION))


def save_events(events: list[dict]) -> None:
    """Input: 25 recomputed events. Output: independent derived SQLite."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix="phase3_m0_ap_alignment.",
                                    suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            create_tables(database)
            for event in events:
                with database:
                    insert_event(database, event)
            totals = database.execute("""
                SELECT count(*),sum(phase_is_valid_80pct)
                FROM phase3_m0_ap_alignment_minute
            """).fetchone()
            storm_count = database.execute(
                "SELECT count(*) FROM phase3_m0_ap_alignment_storm"
            ).fetchone()[0]
            if (totals != (217_912, 214_907) or storm_count != 25
                    or database.execute("PRAGMA integrity_check").fetchone()[0]
                    != "ok"):
                raise ValueError("M0 alignment SQLite failed count or integrity checks.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: frozen P2.6 and raw weather. Output: no-fit corrected M0 SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    paths = DensityPaths()
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    existing_uri = f"file:{EXISTING_PHASE_DENSITY.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        paired_sums = collect_paired_sums(source, weather)
        storm_ids = [row[0] for row in source.execute(
            "SELECT storm_id FROM storm_event_t0_phase_v5 ORDER BY t0_time_us")]
        if len(storm_ids) != 25:
            raise ValueError("Expected 25 frozen Phase 2 storms.")
        with closing(sqlite3.connect(existing_uri, uri=True)) as existing:
            events = []
            for storm_id in storm_ids:
                event = prepare_event(storm_id, source_event_rows(source, storm_id),
                                      paired_sums)
                verify_existing_phase(existing, event)
                events.append(event)
    save_events(events)
    print(f"Saved corrected M0 for {len(events)} storms in {OUTPUT}")


if __name__ == "__main__":
    main()
