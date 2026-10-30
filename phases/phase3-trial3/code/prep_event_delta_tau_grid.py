"""Fit one constant delay and response time per storm, independently."""

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "phase3-trial2" / "code"))
from calc_trial2_delay import DELTA_MINUTES, fit_gain, response_statistics
from load_trial2_inputs import PHASE3_PREDICTION, load_continuous_sme, load_events
from prep_trial2_delay import check_mainline


OUTPUT = Path(
    "phases/phase3-trial3/data/sqlite/swarm_a_phase3_trial3_event_delta_tau_v1.sqlite"
)
VERSION = "phase3_trial3_event_delta_tau_v1"
TAU_HOURS = tuple(index / 4 for index in range(41))


def load_event_provenance() -> dict[str, tuple[int, float]]:
    """Input: frozen P3 overview. Output: {storm_id: (t0 time_us, R distance d)}."""
    uri = f"file:{PHASE3_PREDICTION.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute(
            "SELECT storm_id,t0_time_us,r_pre_distance_days "
            "FROM phase3_25storm_overview"
        ).fetchall()
    return {storm_id: (t0, distance) for storm_id, t0, distance in rows}


def fit_event_grids(sme_nt: np.ndarray, events: list[dict]) -> tuple[list, list]:
    """Input: continuous SME and [M1 events]. Output: [event fits], [grid rows]."""
    candidates = [(tau, delta) for tau in TAU_HOURS for delta in DELTA_MINUTES]
    cross, response_squared = response_statistics(sme_nt, events, candidates)
    provenance = load_event_provenance()
    event_rows = []
    grid_rows = []
    for event_index, event in enumerate(events):
        gains, squared_errors = fit_gain(
            cross[:, event_index], response_squared[:, event_index],
            event["anomaly_squared"],
        )
        errors = np.sqrt(np.maximum(squared_errors, 0) / event["count"])
        if not np.isfinite(errors).any():
            raise ValueError(f"No positive-gain candidate: {event['storm_id']}")
        best_index = int(np.argmin(errors))
        zero_delay_indices = [index for index, (_, delay) in enumerate(candidates)
                              if delay == 0]
        zero_index = min(zero_delay_indices, key=lambda index: errors[index])
        near = np.flatnonzero(errors <= 1.05 * errors[best_index])
        near_taus = [candidates[index][0] for index in near]
        near_delays = [candidates[index][1] for index in near]
        storm_id = event["storm_id"]
        t0, r_distance = provenance[storm_id]
        tau, delay = candidates[best_index]
        event_rows.append((
            storm_id, t0, event["count"], event["r"], r_distance,
            tau, delay, float(gains[best_index]), float(errors[best_index]),
            candidates[zero_index][0], float(gains[zero_index]),
            float(errors[zero_index]),
            float(1 - errors[best_index] / errors[zero_index]),
            min(near_taus), max(near_taus), min(near_delays), max(near_delays),
            int(tau in (0, 10)), int(delay in (0, 360)), VERSION,
        ))
        grid_rows.extend((
            storm_id, candidate_tau, candidate_delay,
            float(gains[index]), float(errors[index]), VERSION,
        ) for index, (candidate_tau, candidate_delay) in enumerate(candidates)
           if np.isfinite(errors[index]))
    return event_rows, grid_rows


def save_sqlite(event_rows: list, grid_rows: list, reproduction_error_nt: float) -> Path:
    """Input: [fits], [grid], M1 check. Output: new independent SQLite path."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    expected_grid_rows = 25 * len(TAU_HOURS) * len(DELTA_MINUTES)
    if len(event_rows) != 25 or len(grid_rows) != expected_grid_rows:
        raise ValueError("Expected a complete 25-event tau/delta grid")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="trial3_event_grid_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE trial3_metadata (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE trial3_event_fit (
                    storm_id TEXT PRIMARY KEY,
                    t0_time_us INTEGER NOT NULL,
                    valid_anchor_count INTEGER NOT NULL,
                    r_quiet REAL NOT NULL,
                    r_pre_distance_days REAL NOT NULL,
                    best_tau_hours REAL NOT NULL,
                    best_delta_minutes INTEGER NOT NULL,
                    best_gain_per_nt REAL NOT NULL,
                    best_rmse_log_density REAL NOT NULL,
                    zero_delta_tau_hours REAL NOT NULL,
                    zero_delta_gain_per_nt REAL NOT NULL,
                    zero_delta_rmse_log_density REAL NOT NULL,
                    relative_rmse_improvement REAL NOT NULL,
                    near5_tau_low_hours REAL NOT NULL,
                    near5_tau_high_hours REAL NOT NULL,
                    near5_delta_low_minutes INTEGER NOT NULL,
                    near5_delta_high_minutes INTEGER NOT NULL,
                    tau_boundary INTEGER NOT NULL,
                    delta_boundary INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE trial3_event_grid (
                    storm_id TEXT NOT NULL,
                    tau_hours REAL NOT NULL,
                    delta_minutes INTEGER NOT NULL,
                    gain_per_nt REAL NOT NULL,
                    rmse_log_density REAL NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id,tau_hours,delta_minutes)
                );
            """)
            database.executemany("INSERT INTO trial3_metadata VALUES (?,?)", (
                ("algorithm_version", VERSION),
                ("tau_grid_hours", "0..10 by 0.25"),
                ("delta_grid_minutes", "0..360 by 15"),
                ("gain", "one positive fitted value per storm and candidate"),
                ("r_quiet", "frozen Phase 3 pre-event calibration"),
                ("m1_reproduction_max_abs_h_nt", str(reproduction_error_nt)),
                ("analysis", "in-sample event fit; not a held-out forecast"),
            ))
            database.executemany(
                f"INSERT INTO trial3_event_fit VALUES ({','.join('?' * 20)})",
                event_rows,
            )
            database.executemany(
                "INSERT INTO trial3_event_grid VALUES (?,?,?,?,?,?)", grid_rows
            )
            database.commit()
            if (database.execute("SELECT count(*) FROM trial3_event_fit").fetchone()[0]
                    != 25):
                raise ValueError("Expected 25 event fits")
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Trial 3 SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    return OUTPUT


def main() -> None:
    """Input: frozen P2/P3 SQLite. Output: 25-event trial SQLite and summary."""
    minute_times, sme_nt = load_continuous_sme()
    events = load_events(minute_times)
    reproduction_error = check_mainline(sme_nt, events)
    event_rows, grid_rows = fit_event_grids(sme_nt, events)
    output = save_sqlite(event_rows, grid_rows, reproduction_error)
    print(f"Saved {len(event_rows)} storms and {len(grid_rows)} grid rows to {output}")
    for row in event_rows:
        print(row[0], f"R={row[3]:.6f}", f"tau={row[5]:.2f}h",
              f"delta={row[6]}min", f"G={row[7]:.9f}",
              f"RMSE={row[8]:.6f}", f"improvement={row[12]:.3%}")


if __name__ == "__main__":
    main()
