"""Build an independent, in-sample R-grid trial for aligned full MSIS."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from calc_m2_r_grid import choose_trial, score_r_grid


SOURCE = Path("phases/phase3/data/sqlite/swarm_a_phase3_m2_residual_diagnostic_v1.sqlite")
OUTPUT = Path("phases/phase3-trial/data/sqlite/swarm_a_m2_r_grid_trial_v1.sqlite")
VERSION = "m2_r_grid_trial_v1"


def load_events() -> list[tuple[str, list[tuple[int, float, float, float]]]]:
    """Input: frozen Phase 3 residual SQLite. Output: [(storm_id, [paired minute]), ...]."""
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as database:
        rows = database.execute("""
            SELECT storm_id,time_us,rho_l2_phase_kg_m3,
                   rho_m0_aligned_phase_kg_m3,residual_log_density
            FROM phase3_m2_residual_minute
            ORDER BY storm_id,time_us
        """).fetchall()
    events = []
    for storm_id, time_us, rho_l2, rho_m0, residual in rows:
        if rho_l2 <= 0 or rho_m0 <= 0 or not math.isfinite(residual):
            raise ValueError(f"Invalid density pair at {storm_id}, {time_us}")
        if not events or events[-1][0] != storm_id:
            events.append((storm_id, []))
        events[-1][1].append((time_us, rho_l2, rho_m0, residual))
    if len(events) != 25:
        raise ValueError(f"Expected 25 events, found {len(events)}")
    return events


def write_trial(database: sqlite3.Connection, events: list) -> None:
    """Input: SQLite connection, [events]. Output: three derived trial tables."""
    database.executescript("""
        CREATE TABLE m2_r_trial_grid (
            storm_id TEXT NOT NULL,
            trial_r REAL NOT NULL,
            rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,trial_r)
        );
        CREATE TABLE m2_r_trial_storm (
            storm_id TEXT PRIMARY KEY,
            valid_minutes INTEGER NOT NULL,
            chosen_r REAL NOT NULL,
            m0_rmse_log_density REAL NOT NULL,
            m2_oracle_rmse_log_density REAL NOT NULL,
            chosen_at_grid_boundary INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE m2_r_trial_minute (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            rho_l2_phase_kg_m3 REAL NOT NULL,
            rho_m0_aligned_phase_kg_m3 REAL NOT NULL,
            rho_m2_oracle_phase_kg_m3 REAL NOT NULL,
            residual_m2_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
    """)
    for storm_id, minutes in events:
        ratios = [minute[3] for minute in minutes]
        scores = score_r_grid(ratios)
        chosen_r, chosen_rmse = choose_trial(scores)
        m0_rmse = next(error for trial_r, error in scores if trial_r == 1.0)
        database.executemany(
            "INSERT INTO m2_r_trial_grid VALUES (?,?,?,?)",
            ((storm_id, trial_r, error, VERSION) for trial_r, error in scores),
        )
        database.execute(
            "INSERT INTO m2_r_trial_storm VALUES (?,?,?,?,?,?,?)",
            (storm_id, len(minutes), chosen_r, m0_rmse, chosen_rmse,
             int(chosen_r in (0.4, 1.6)), VERSION),
        )
        database.executemany(
            "INSERT INTO m2_r_trial_minute VALUES (?,?,?,?,?,?,?)",
            ((storm_id, time_us, rho_l2, rho_m0, chosen_r * rho_m0,
              residual - math.log(chosen_r), VERSION)
             for time_us, rho_l2, rho_m0, residual in minutes),
        )


def main() -> None:
    """Input: frozen M2 residual database. Output: separate M2 trial SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    events = load_events()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="m2_r_trial_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            write_trial(database, events)
            database.commit()
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("M2 trial SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Saved {len(events)} M2 event trials to {OUTPUT}")


if __name__ == "__main__":
    main()
