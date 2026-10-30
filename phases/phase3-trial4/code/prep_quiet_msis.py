"""Pair quiet-ap MSIS with Swarm-A L2 at native samples and phase anchors."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase0.code.calculation.density.calc_msis_p2_4 import (
    calculate_msis_density, load_msis_weather, sample_drivers,
)
from phases.phase0.code.data.density.load_dnsapod import load_dnsapod
from phases.phase2.code.prep_24_density_t0_phase import (
    DensityPaths, checked_manifest, minute_label, minute_targets, required_days,
)
from phases.phase3.code.calc_h_tau import phase_support, phase_weighted_mean


SOURCE = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
OUTPUT = Path("phases/phase3/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite")
AP_REFERENCE = 4.0


def pair_quiet_day(zip_path: Path, targets: dict, weather: dict) -> dict:
    """Input: DNSAPOD ZIP, {minute: storms}, weather. Output: paired minute sums."""
    selected = []
    drivers = []
    for sample in load_dnsapod(zip_path)["samples"]:
        minute_us = minute_label(sample["time_us"])
        storm_ids = targets.get(minute_us)
        if storm_ids is None or sample["rho_l2_kg_m3"] is None:
            continue
        driver = sample_drivers(sample["time_us"], weather)
        if driver is None:
            continue
        driver["ap_values"] = [AP_REFERENCE] * 7
        selected.append((sample, storm_ids, minute_us))
        drivers.append(driver)
    densities = calculate_msis_density([row[0] for row in selected], drivers)
    totals = {}
    for (sample, storm_ids, minute_us), rho_quiet in zip(
        selected, densities, strict=True
    ):
        if rho_quiet is None:
            continue
        for storm_id in storm_ids:
            sums = totals.setdefault((storm_id, minute_us), [0.0, 0.0, 0])
            sums[0] += sample["rho_l2_kg_m3"]
            sums[1] += rho_quiet
            sums[2] += 1
    return totals


def source_event_rows(database: sqlite3.Connection, storm_id: str) -> list[tuple]:
    """Input: frozen P2.6 connection and storm ID. Output: paired minute inputs."""
    return database.execute("""
        SELECT feature.source_time_us,feature.u_rel_rad,
               density.paired_sample_count,density.rho_l2_kg_m3,
               density.rho_msis_kg_m3
        FROM storm_minute_feature_v5 AS feature
        JOIN storm_density_1min_v5 AS density
          ON density.storm_id=feature.storm_id
         AND density.source_time_us=feature.source_time_us
        WHERE feature.storm_id=? ORDER BY feature.source_time_us
    """, (storm_id,)).fetchall()


def insert_event(database: sqlite3.Connection, storm_id: str,
                 inputs: dict) -> None:
    """Input: destination, storm ID, {source_rows, totals}. Output: density rows."""
    source_rows = inputs["source_rows"]
    totals = inputs["totals"]
    time_us = np.fromiter((row[0] for row in source_rows), dtype=np.int64)
    phase = np.fromiter((row[1] for row in source_rows), dtype=float)
    pair_count = np.fromiter((row[2] for row in source_rows), dtype=np.int16)
    l2 = np.full(len(source_rows), np.nan)
    quiet = np.full(len(source_rows), np.nan)
    full = np.full(len(source_rows), np.nan)
    for index, row in enumerate(source_rows):
        sums = totals.get((storm_id, row[0]), [0.0, 0.0, 0])
        if sums[2] != row[2]:
            raise ValueError(f"Quiet MSIS lost native paired samples: {storm_id}:{row[0]}")
        if sums[2]:
            l2[index] = sums[0] / sums[2]
            quiet[index] = sums[1] / sums[2]
            full[index] = row[4]
            if not math.isclose(l2[index], row[3], rel_tol=1e-10):
                raise ValueError(f"L2 pairing differs from P2.6: {storm_id}:{row[0]}")
    support = phase_support(phase, pair_count)
    l2_phase = phase_weighted_mean(l2, pair_count, support)
    quiet_phase = phase_weighted_mean(quiet, pair_count, support)
    full_phase = phase_weighted_mean(full, pair_count, support)
    rows = (
        (storm_id, int(time_us[index]), int(pair_count[index]),
         float(l2[index]) if np.isfinite(l2[index]) else None,
         float(quiet[index]) if np.isfinite(quiet[index]) else None,
         float(l2_phase[index]) if support["valid"][index] else None,
         float(quiet_phase[index]) if support["valid"][index] else None,
         float(full_phase[index]) if support["valid"][index] else None,
         float(math.log(l2_phase[index] / quiet_phase[index]))
         if support["valid"][index] else None,
         int(support["valid"][index]),
         "phase3_quiet_density_v1")
        for index in range(len(source_rows))
    )
    database.executemany("INSERT INTO phase3_quiet_density_minute VALUES "
                         "(?,?,?,?,?,?,?,?,?,?,?)", rows)


def create_output(database: sqlite3.Connection) -> None:
    """Input: new Phase 3 connection. Output: keyed density and metadata tables."""
    database.executescript("""
        CREATE TABLE phase3_quiet_density_minute (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            paired_sample_count INTEGER NOT NULL,
            rho_l2_kg_m3 REAL,
            rho_msis_quiet_kg_m3 REAL,
            rho_l2_phase_kg_m3 REAL,
            rho_msis_quiet_phase_kg_m3 REAL,
            rho_msis_full_phase_kg_m3 REAL,
            log_l2_over_quiet_phase REAL,
            phase_is_valid_80pct INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE phase3_quiet_density_metadata (
            name TEXT PRIMARY KEY,value TEXT NOT NULL
        );
    """)
    database.executemany("INSERT INTO phase3_quiet_density_metadata VALUES (?,?)", (
        ("ap_reference", "seven values fixed at 4"),
        ("f107_source", "P2.4 prior-day F10.7 and centered F10.7A"),
        ("phase_window", "u +/- pi, paired native samples, centered"),
        ("source", str(SOURCE)),
    ))


def main() -> None:
    """Input: frozen P2.6, DNSAPOD, weather. Output: Phase 3 quiet density SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as source:
        targets = minute_targets(source)
        days = required_days(source)
        storm_ids = [row[0] for row in source.execute(
            "SELECT storm_id FROM storm_event_t0_phase_v5 ORDER BY t0_time_us")]
    paths = DensityPaths()
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    totals = {}
    files = checked_manifest(paths, days)
    for file_number, zip_path in enumerate(files, 1):
        for key, incoming in pair_quiet_day(zip_path, targets, weather).items():
            sums = totals.setdefault(key, [0.0, 0.0, 0])
            for index in range(3):
                sums[index] += incoming[index]
        if file_number % 25 == 0 or file_number == len(files):
            print(f"Paired {file_number}/{len(files)} DNSAPOD days", flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="swarm_a_phase3_quiet_density_v1.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as result, closing(
            sqlite3.connect(uri, uri=True)
        ) as source:
            create_output(result)
            for storm_id in storm_ids:
                with result:
                    insert_event(result, storm_id, {
                        "source_rows": source_event_rows(source, storm_id),
                        "totals": totals,
                    })
            count = result.execute(
                "SELECT count(*) FROM phase3_quiet_density_minute").fetchone()[0]
            if count != sum(len(storms) for storms in targets.values()):
                raise ValueError("Quiet-density output lost event minute keys.")
            if result.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Quiet-density SQLite integrity check failed.")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Saved {count} Phase 3 quiet-density minute rows")


if __name__ == "__main__":
    main()
