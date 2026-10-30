"""Search M2 SME time constants while holding the trial event multipliers fixed."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from calc_m2_tau import score_tau_grid, sufficient_statistics


TRIAL_R = Path("phases/phase3-trial/data/sqlite/swarm_a_m2_r_grid_trial_v1.sqlite")
M2_RESIDUAL = Path("phases/phase3/data/sqlite/swarm_a_phase3_m2_residual_diagnostic_v1.sqlite")
H_TAU = Path("phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite")
OUTPUT = Path("phases/phase3-trial/data/sqlite/swarm_a_m2_tau_fixed_r_v1.sqlite")
VERSION = "m2_tau_fixed_r_v1"
TAU_COLUMNS = ",".join(f"h.h_phase_tau_{index:02d}_nt" for index in range(41))


def open_sources() -> sqlite3.Connection:
    """Input: three read-only SQLite paths. Output: attached read-only connection."""
    trial_uri = f"file:{TRIAL_R.resolve().as_posix()}?mode=ro"
    database = sqlite3.connect(trial_uri, uri=True)
    database.execute("ATTACH DATABASE ? AS residual", (
        f"file:{M2_RESIDUAL.resolve().as_posix()}?mode=ro",))
    database.execute("ATTACH DATABASE ? AS response", (
        f"file:{H_TAU.resolve().as_posix()}?mode=ro",))
    return database


def load_event_statistics(database: sqlite3.Connection, event: tuple) -> dict:
    """Input: source connection, (storm_id, fixed_R, count). Output: fit sums."""
    storm_id, trial_r, expected_minutes = event
    query = f"""
        SELECT m.residual_log_density,{TAU_COLUMNS}
        FROM residual.phase3_m2_residual_minute AS m
        JOIN response.phase3_h_tau_minute AS h
          ON m.storm_id=h.storm_id AND m.time_us=h.time_us
        WHERE m.storm_id=? AND h.phase_is_valid_80pct=1
        ORDER BY m.time_us
    """
    rows = database.execute(query, (storm_id,)).fetchall()
    if len(rows) != expected_minutes:
        raise ValueError(f"Phase support mismatch for {storm_id}: {len(rows)} rows")
    anomaly = np.array([row[0] for row in rows]) - math.log(trial_r)
    response = np.array([row[1:] for row in rows])
    return sufficient_statistics(anomaly, response)


def write_results(database: sqlite3.Connection, event_results: list,
                  global_scores: list) -> None:
    """Input: new SQLite, [event grids], [global grid]. Output: derived tables."""
    database.executescript("""
        CREATE TABLE m2_tau_global_grid (
            tau_hours REAL PRIMARY KEY,
            gain_per_nt REAL NOT NULL,
            rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE m2_tau_event_grid (
            storm_id TEXT NOT NULL,
            tau_hours REAL NOT NULL,
            fixed_r REAL NOT NULL,
            gain_per_nt REAL NOT NULL,
            rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,tau_hours)
        );
        CREATE TABLE m2_tau_event_summary (
            storm_id TEXT PRIMARY KEY,
            valid_minutes INTEGER NOT NULL,
            fixed_r REAL NOT NULL,
            best_tau_hours REAL NOT NULL,
            best_gain_per_nt REAL NOT NULL,
            best_rmse_log_density REAL NOT NULL,
            tau_5pct_lower_hours REAL NOT NULL,
            tau_5pct_upper_hours REAL NOT NULL,
            at_grid_boundary INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        );
    """)
    database.executemany(
        "INSERT INTO m2_tau_global_grid VALUES (?,?,?,?)",
        ((tau, gain, error, VERSION) for tau, gain, error in global_scores),
    )
    for storm_id, fixed_r, minutes, scores in event_results:
        database.executemany(
            "INSERT INTO m2_tau_event_grid VALUES (?,?,?,?,?,?)",
            ((storm_id, tau, fixed_r, gain, error, VERSION)
             for tau, gain, error in scores),
        )
        best_tau, best_gain, best_error = min(scores, key=lambda row: row[2])
        near_best = [tau for tau, _, error in scores if error <= 1.05 * best_error]
        database.execute(
            "INSERT INTO m2_tau_event_summary VALUES (?,?,?,?,?,?,?,?,?,?)",
            (storm_id, minutes, fixed_r, best_tau, best_gain, best_error,
             min(near_best), max(near_best), int(best_tau in (0, 10)), VERSION),
        )


def main() -> None:
    """Input: frozen response/residuals and trial R. Output: independent tau SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    with closing(open_sources()) as source:
        events = source.execute(
            "SELECT storm_id,chosen_r,valid_minutes FROM m2_r_trial_storm ORDER BY storm_id"
        ).fetchall()
        if len(events) != 25:
            raise ValueError(f"Expected 25 fixed multipliers, found {len(events)}")
        event_results = []
        global_statistics = None
        for event in events:
            storm_id, fixed_r, minutes = event
            statistics = load_event_statistics(source, event)
            event_results.append((storm_id, fixed_r, minutes,
                                  score_tau_grid(statistics)))
            if global_statistics is None:
                global_statistics = statistics
            else:
                global_statistics["minutes"] += statistics["minutes"]
                global_statistics["anomaly_squared"] += statistics["anomaly_squared"]
                global_statistics["cross"] += statistics["cross"]
                global_statistics["response_squared"] += statistics["response_squared"]
    global_scores = score_tau_grid(global_statistics)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="m2_tau_fixed_r_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            write_results(database, event_results, global_scores)
            database.commit()
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("M2 tau SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    best_tau, best_gain, best_error = min(global_scores, key=lambda row: row[2])
    print(f"25 events, common tau={best_tau:g} h, "
          f"G={best_gain:.8g} 1/nT, RMSE={best_error:.6f}")


if __name__ == "__main__":
    main()
