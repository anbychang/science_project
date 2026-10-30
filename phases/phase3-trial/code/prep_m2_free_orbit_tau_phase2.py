"""Fit an independent tau per Phase 2 orbit while carrying SME response forward."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from load_m2_orbit_inputs import read_free_tau_events, read_minute_sme
from calc_m2_free_orbit_tau import (
    MAX_SWEEPS, TAU_GRID_HOURS, fit_event_orbit_tau,
)
from prep_m2_orbit_tau_phase2 import prepare_events


OUTPUT = Path("phases/phase3-trial/data/sqlite/swarm_a_m2_free_orbit_tau_phase2_v1.sqlite")
VERSION = "m2_free_orbit_tau_phase2_v1"


def fit_all_events() -> tuple[list, float]:
    """Input: read-only Phase 2 and M2 trial sources. Output: [event fits], fixed G."""
    times, sme_nt = read_minute_sme()
    events, gain = read_free_tau_events(times)
    prepared = prepare_events(times, sme_nt, events)
    fitted = []
    for index, event in enumerate(prepared, 1):
        result = fit_event_orbit_tau(event, gain)
        fitted.append((event, result))
        print(f"{index}/25 {event['storm_id']} "
              f"RMSE {math.sqrt(result['initial_sse'] / len(event['anomaly'])):.4f} -> "
              f"{math.sqrt(result['final_sse'] / len(event['anomaly'])):.4f} "
              f"sweeps={len(result['sweeps'])} "
              f"converged={result['converged']}", flush=True)
    return fitted, gain


def write_trial(database: sqlite3.Connection, fitted: list,
                gain_per_nt: float) -> None:
    """Input: new SQLite, [event fits], gain 1/nT. Output: derived tables."""
    database.executescript("""
        CREATE TABLE m2_free_tau_event (
            storm_id TEXT PRIMARY KEY,
            orbit_count INTEGER NOT NULL,
            valid_minutes INTEGER NOT NULL,
            fixed_r REAL NOT NULL,
            fixed_gain_per_nt REAL NOT NULL,
            initial_rmse_log_density REAL NOT NULL,
            final_rmse_log_density REAL NOT NULL,
            boundary_orbit_count INTEGER NOT NULL,
            sweep_count INTEGER NOT NULL,
            converged INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE m2_free_tau_orbit (
            storm_id TEXT NOT NULL,
            orbit_index INTEGER NOT NULL,
            first_minute_time_us INTEGER NOT NULL,
            last_minute_time_us INTEGER NOT NULL,
            fitted_tau_hours REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,orbit_index)
        );
        CREATE TABLE m2_free_tau_sweep (
            storm_id TEXT NOT NULL,
            sweep INTEGER NOT NULL,
            changed_orbit_count INTEGER NOT NULL,
            rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,sweep)
        );
        CREATE TABLE m2_free_tau_minute (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            orbit_index INTEGER NOT NULL,
            tau_at_anchor_hours REAL NOT NULL,
            h_phase_nt REAL NOT NULL,
            rho_l2_phase_kg_m3 REAL NOT NULL,
            rho_m0_phase_kg_m3 REAL NOT NULL,
            rho_m2_phase_kg_m3 REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE m2_free_tau_metadata (
            algorithm_version TEXT PRIMARY KEY,
            tau_grid_start_hours REAL NOT NULL,
            tau_grid_stop_hours REAL NOT NULL,
            tau_grid_step_hours REAL NOT NULL,
            max_sweeps INTEGER NOT NULL
        );
    """)
    database.execute("INSERT INTO m2_free_tau_metadata VALUES (?,?,?,?,?)",
                     (VERSION, TAU_GRID_HOURS[0], TAU_GRID_HOURS[-1],
                      TAU_GRID_HOURS[1] - TAU_GRID_HOURS[0], MAX_SWEEPS))
    for event, result in fitted:
        storm_id = event["storm_id"]
        orbit_tau = result["tau_by_orbit"]
        labels = event["orbit_labels"]
        edges = event["orbit_edges"]
        valid = event["support"]["valid"]
        count = len(event["anomaly"])
        boundary_count = int(np.sum((orbit_tau == 0) | (orbit_tau == 10)))
        database.execute("INSERT INTO m2_free_tau_event VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (storm_id, len(orbit_tau), count, event["r"], gain_per_nt,
                          math.sqrt(result["initial_sse"] / count),
                          math.sqrt(result["final_sse"] / count), boundary_count,
                          len(result["sweeps"]), int(result["converged"]), VERSION))
        database.executemany("INSERT INTO m2_free_tau_orbit VALUES (?,?,?,?,?,?)",
                             ((storm_id, int(labels[edges[index]]),
                               int(event["times"][edges[index]]),
                               int(event["times"][edges[index + 1] - 1]),
                               float(orbit_tau[index]), VERSION)
                              for index in range(len(orbit_tau))))
        database.executemany("INSERT INTO m2_free_tau_sweep VALUES (?,?,?,?,?)",
                             ((storm_id, sweep, changed,
                               math.sqrt(sse / count), VERSION)
                              for sweep, changed, sse in result["sweeps"]))
        phase_response = result["phase_response"]
        predicted = event["r"] * event["rho_m0"] * np.exp(
            gain_per_nt * phase_response
        )
        database.executemany("INSERT INTO m2_free_tau_minute VALUES (?,?,?,?,?,?,?,?,?)",
                             ((storm_id, int(time), int(label),
                               float(orbit_tau[int(label - labels[0])]),
                               float(h_value), float(l2), float(m0), float(m2), VERSION)
                              for time, label, h_value, l2, m0, m2 in zip(
                                  event["times"][valid], labels[valid], phase_response,
                                  event["rho_l2"], event["rho_m0"], predicted,
                                  strict=True)))


def main() -> None:
    """Input: Phase 2 and prior trial data. Output: free orbit tau SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    fitted, gain = fit_all_events()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="m2_free_tau_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            write_trial(database, fitted, gain)
            database.commit()
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Free orbit tau SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    minutes = sum(len(event["anomaly"]) for event, _ in fitted)
    initial_sse = sum(result["initial_sse"] for _, result in fitted)
    final_sse = sum(result["final_sse"] for _, result in fitted)
    print(f"Pooled RMSE {math.sqrt(initial_sse / minutes):.6f} -> "
          f"{math.sqrt(final_sse / minutes):.6f}; saved {OUTPUT}")


if __name__ == "__main__":
    main()
