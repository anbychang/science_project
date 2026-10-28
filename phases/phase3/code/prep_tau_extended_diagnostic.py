"""Extend boundary-hit event tau fits without changing the Phase 3 baseline."""

import csv
import math
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean
from phases.phase3.code.prep_exploratory_fit import load_fit_arrays, load_r_candidates
from phases.phase3.code.prep_h_tau_phase import (
    SME_REFERENCE_NT, SOURCE, load_event, load_sme,
)


EVENT_REPORT = Path("phases/phase3/data/analysis/phase3_event_tau_exploratory.csv")
OUTPUT = Path("phases/phase3/data/sqlite/swarm_a_phase3_tau_extended_diagnostic_v1.sqlite")
VERSION = "phase3_tau_extended_diagnostic_v1"


def boundary_storm_ids() -> list[str]:
    """Input: original event fit CSV. Output: [storm ID with tau=10 h]."""
    with EVENT_REPORT.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    result = [row["storm_id"] for row in rows if float(row["tau_hours"]) == 10.0]
    if len(result) != 7:
        raise ValueError(f"Expected seven original boundary hits, got {len(result)}.")
    return result


def tau_grid_hours() -> list[float]:
    """Input: none. Output: 10..72 h by 0.5 h, then 73..240 h by 1 h."""
    return [step / 2 for step in range(20, 145)] + list(range(73, 241))


def fit_event(response: np.ndarray, event: dict, target: np.ndarray) -> tuple[float, float]:
    """Input: [SME anomaly], phase event, [log-density anomaly]. Output: gain and RMSE."""
    phase = phase_weighted_mean(response[event["minute_index"]],
                                event["pair_count"], event["support"])
    h = phase[event["support"]["valid"]]
    if len(h) != len(target):
        raise ValueError(f"Phase and density support differ for {event['storm_id']}.")
    gain = float((h @ target) / (h @ h))
    rmse = float(np.sqrt(np.mean((target - gain * h) ** 2)))
    return gain, rmse


def save_grid(rows: list[tuple]) -> None:
    """Input: [extended fit row]. Output: separate diagnostic SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(OUTPUT)) as database:
        with database:
            database.execute("""
                CREATE TABLE phase3_tau_extended_grid (
                    storm_id TEXT NOT NULL,
                    tau_seconds INTEGER NOT NULL,
                    gain_per_nt REAL NOT NULL,
                    rmse_log_density REAL NOT NULL,
                    fit_minutes INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id, tau_seconds)
                )
            """)
            database.executemany("INSERT INTO phase3_tau_extended_grid VALUES (?,?,?,?,?,?)", rows)
            database.execute("""
                CREATE TABLE phase3_tau_extended_summary (
                    storm_id TEXT PRIMARY KEY,
                    best_tau_seconds INTEGER NOT NULL,
                    best_rmse_log_density REAL NOT NULL,
                    rmse_at_10h REAL NOT NULL,
                    best_hits_240h_boundary INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                )
            """)
            for storm_id in sorted({row[0] for row in rows}):
                event_rows = [row for row in rows if row[0] == storm_id]
                best = min(event_rows, key=lambda row: row[3])
                database.execute("INSERT INTO phase3_tau_extended_summary VALUES (?,?,?,?,?,?)",
                                 (storm_id, best[1], best[3], event_rows[0][3],
                                  int(best[1] == 240 * 3600), VERSION))
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Diagnostic SQLite integrity check failed.")


def main() -> None:
    """Input: frozen Phase 3 data and original boundary hits. Output: independent SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    storm_ids = boundary_storm_ids()
    z, original_h, event_index, identifiers = load_fit_arrays(load_r_candidates())
    index = {storm_id: position for position, storm_id in enumerate(identifiers)}
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as source:
        sme, first_time_us = load_sme(source)
        events = {storm_id: load_event(source, storm_id, first_time_us)
                  for storm_id in storm_ids}
    targets = {storm_id: z[event_index == index[storm_id]] for storm_id in storm_ids}
    rows = []
    for tau_hours in tau_grid_hours():
        response = filtered_sme(sme, tau_hours) - SME_REFERENCE_NT
        for storm_id in storm_ids:
            gain, rmse = fit_event(response, events[storm_id], targets[storm_id])
            if tau_hours == 10.0:
                original = original_h[event_index == index[storm_id], 40]
                original_gain = float((original @ targets[storm_id]) / (original @ original))
                original_rmse = math.sqrt(float(np.mean(
                    (targets[storm_id] - original_gain * original) ** 2)))
                if abs(rmse - original_rmse) > 1e-6:
                    raise ValueError(f"Original 10 h fit does not match: {storm_id}")
            rows.append((storm_id, round(tau_hours * 3600), gain, rmse,
                         len(targets[storm_id]), VERSION))
    save_grid(rows)
    print(f"Saved {len(rows)} diagnostic grid rows for {len(storm_ids)} storms")


if __name__ == "__main__":
    main()
