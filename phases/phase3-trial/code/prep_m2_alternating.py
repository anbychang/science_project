"""Save the alternating M2 R and tau experiment without touching Phase 3."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from calc_m2_alternating import choose_r_trial, common_tau_grid, event_sums
from prep_m2_tau_fixed_r import open_sources, TAU_COLUMNS


OUTPUT = Path("phases/phase3-trial/data/sqlite/swarm_a_m2_alternating_v1.sqlite")
VERSION = "m2_alternating_v1"
MAX_ITERATIONS = 100


def load_event_sums() -> tuple[dict, dict]:
    """Input: read-only Phase 3 and trial SQLite. Output: event sums and initial R."""
    events = {}
    initial_r = {}
    with closing(open_sources()) as source:
        trial_rows = source.execute(
            "SELECT storm_id,chosen_r,valid_minutes FROM m2_r_trial_storm ORDER BY storm_id"
        ).fetchall()
        if len(trial_rows) != 25:
            raise ValueError(f"Expected 25 trial multipliers, found {len(trial_rows)}")
        query = f"""
            SELECT m.residual_log_density,{TAU_COLUMNS}
            FROM residual.phase3_m2_residual_minute AS m
            JOIN response.phase3_h_tau_minute AS h
              ON m.storm_id=h.storm_id AND m.time_us=h.time_us
            WHERE m.storm_id=? AND h.phase_is_valid_80pct=1
            ORDER BY m.time_us
        """
        for storm_id, initial_value, expected_minutes in trial_rows:
            rows = source.execute(query, (storm_id,)).fetchall()
            if len(rows) != expected_minutes:
                raise ValueError(f"Phase support mismatch for {storm_id}")
            residual = np.array([row[0] for row in rows])
            response = np.array([row[1:] for row in rows])
            events[storm_id] = event_sums(residual, response)
            initial_r[storm_id] = initial_value
    return events, initial_r


def alternate(events: dict, initial_r: dict) -> tuple[list, dict, list, bool]:
    """Input: event sums and initial R. Output: iterations, final R/grid, convergence."""
    r_by_storm = initial_r.copy()
    iterations = []
    total_minutes = sum(event["minutes"] for event in events.values())
    converged = False
    for iteration in range(1, MAX_ITERATIONS + 1):
        grid = common_tau_grid(events, r_by_storm)
        tau_hours, gain_per_nt, rmse_before = min(grid, key=lambda row: row[2])
        next_r = {}
        squared_error_after = 0.0
        for storm_id, event in events.items():
            next_r[storm_id], event_rmse = choose_r_trial(
                event, tau_hours, gain_per_nt
            )
            squared_error_after += event["minutes"] * event_rmse * event_rmse
        rmse_after = math.sqrt(squared_error_after / total_minutes)
        changed = sum(next_r[storm_id] != r_by_storm[storm_id]
                      for storm_id in events)
        if rmse_after > rmse_before + 1e-10:
            raise ValueError("R update increased the training error")
        iterations.append((iteration, tau_hours, gain_per_nt, rmse_before,
                           rmse_after, changed, r_by_storm.copy(), next_r.copy()))
        r_by_storm = next_r
        if changed == 0:
            converged = True
            break
    return iterations, r_by_storm, common_tau_grid(events, r_by_storm), converged


def save_results(results: tuple, events: dict, initial_r: dict) -> None:
    """Input: fit results, event sums, initial R. Output: independent SQLite."""
    iterations, final_r, final_grid, converged = results
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="m2_alternating_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE m2_alternation_iteration (
                    iteration INTEGER PRIMARY KEY,
                    tau_hours REAL NOT NULL,
                    gain_per_nt REAL NOT NULL,
                    rmse_before_r_update REAL NOT NULL,
                    rmse_after_r_update REAL NOT NULL,
                    r_changed_count INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE m2_alternation_r (
                    iteration INTEGER NOT NULL,
                    storm_id TEXT NOT NULL,
                    r_before REAL NOT NULL,
                    r_after REAL NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (iteration,storm_id)
                );
                CREATE TABLE m2_alternation_global_grid (
                    tau_hours REAL PRIMARY KEY,
                    gain_per_nt REAL NOT NULL,
                    rmse_log_density REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE m2_alternation_storm (
                    storm_id TEXT PRIMARY KEY,
                    valid_minutes INTEGER NOT NULL,
                    initial_r REAL NOT NULL,
                    final_r REAL NOT NULL,
                    final_rmse_log_density REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE m2_alternation_metadata (
                    algorithm_version TEXT PRIMARY KEY,
                    iteration_count INTEGER NOT NULL,
                    converged INTEGER NOT NULL
                );
            """)
            for number, tau, gain, before_rmse, after_rmse, changed, before_r, after_r in iterations:
                database.execute("INSERT INTO m2_alternation_iteration VALUES (?,?,?,?,?,?,?)",
                                 (number, tau, gain, before_rmse, after_rmse, changed, VERSION))
                database.executemany("INSERT INTO m2_alternation_r VALUES (?,?,?,?,?)",
                                     ((number, storm_id, before_r[storm_id],
                                       after_r[storm_id], VERSION) for storm_id in events))
            database.executemany("INSERT INTO m2_alternation_global_grid VALUES (?,?,?,?)",
                                 ((tau, gain, error, VERSION)
                                  for tau, gain, error in final_grid))
            final_tau, final_gain, _ = min(final_grid, key=lambda row: row[2])
            database.executemany("INSERT INTO m2_alternation_storm VALUES (?,?,?,?,?,?)",
                                 ((storm_id, event["minutes"], initial_r[storm_id],
                                   final_r[storm_id],
                                   choose_r_trial(event, final_tau, final_gain)[1],
                                   VERSION)
                                  for storm_id, event in events.items()))
            database.execute("INSERT INTO m2_alternation_metadata VALUES (?,?,?)",
                             (VERSION, len(iterations), int(converged)))
            database.commit()
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("M2 alternating SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: fixed Phase 3 and M2 trial data. Output: alternating trial SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    events, initial_r = load_event_sums()
    results = alternate(events, initial_r)
    if not results[3]:
        raise RuntimeError("Alternating M2 trial did not converge")
    save_results(results, events, initial_r)
    iterations, _, final_grid, converged = results
    best = min(final_grid, key=lambda row: row[2])
    print(f"Iterations={len(iterations)}, converged={converged}, "
          f"tau={best[0]:g} h, G={best[1]:.8g} 1/nT, RMSE={best[2]:.6f}")


if __name__ == "__main__":
    main()
