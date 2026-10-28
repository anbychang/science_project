"""Diagnose per-event tau for the zero-SME M1A variant."""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

from research_workspace.phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean
from research_workspace.phases.phase3.code.prep_m1a_zero_sme import (
    MAX_GAIN_PER_NT, load_context,
)


OUTPUT = Path("research_workspace/phases/phase3/data/sqlite/swarm_a_phase3_m1a_event_tau_v1.sqlite")
VERSION = "phase3_m1a_event_tau_v1"


def fit_event(event: dict, f_event: np.ndarray, f_quiet: np.ndarray) -> tuple:
    """Input: event ratios and filtered SME arrays. Output: G, R at zero SME, RMSE."""
    y = event["log_ratio"]
    y_quiet = event["calibration"]["log_ratio"]
    n = len(y)
    sum_y = float(np.sum(y))
    sum_f = float(np.sum(f_event))
    sum_y2 = float(y @ y)
    sum_f2 = float(f_event @ f_event)
    sum_yf = float(y @ f_event)

    def squared_error(gain: float) -> float:
        """Input: candidate G in 1/nT. Output: event squared log-density error."""
        baseline = np.log(np.median(np.exp(y_quiet - gain * f_quiet)))
        return (sum_y2 - 2 * baseline * sum_y - 2 * gain * sum_yf
                + n * baseline ** 2 + 2 * baseline * gain * sum_f
                + gain ** 2 * sum_f2)

    optimum = minimize_scalar(squared_error, bounds=(0, MAX_GAIN_PER_NT),
                              method="bounded", options={"xatol": 1e-11})
    if not optimum.success:
        raise ValueError(f"M1A event fit failed: {event['storm_id']}")
    gain = float(optimum.x)
    r = float(np.median(np.exp(y_quiet - gain * f_quiet)))
    return gain, r, float(np.sqrt(max(optimum.fun, 0) / n))


def save_grid(rows: list[tuple]) -> None:
    """Input: [event-tau fit row]. Output: independent M1A event diagnostic SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="m1a_event_tau_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            with database:
                database.execute("""CREATE TABLE phase3_m1a_event_tau_grid (
                    storm_id TEXT NOT NULL,
                    tau_seconds INTEGER NOT NULL,
                    gain_per_nt REAL NOT NULL,
                    r_zero_sme_extrapolated REAL NOT NULL,
                    rmse_log_density REAL NOT NULL,
                    fit_minutes INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id,tau_seconds))""")
                database.execute("""CREATE TABLE phase3_m1a_event_tau_summary (
                    storm_id TEXT PRIMARY KEY,
                    best_tau_seconds INTEGER NOT NULL,
                    best_gain_per_nt REAL NOT NULL,
                    best_r_zero_sme_extrapolated REAL NOT NULL,
                    best_rmse_log_density REAL NOT NULL,
                    hits_10h_boundary INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL)""")
                database.executemany("INSERT INTO phase3_m1a_event_tau_grid "
                                     "VALUES (?,?,?,?,?,?,?)", rows)
                for storm_id in sorted({row[0] for row in rows}):
                    best = min((row for row in rows if row[0] == storm_id),
                               key=lambda row: row[4])
                    database.execute("INSERT INTO phase3_m1a_event_tau_summary "
                                     "VALUES (?,?,?,?,?,?,?)",
                                     (storm_id, best[1], best[2], best[3], best[4],
                                      int(best[1] == 36_000), VERSION))
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("M1A event SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: original pre-event windows and event data. Output: 25-event tau SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    context = load_context()
    rows = []
    for step in range(41):
        filtered = filtered_sme(context["sme"], step / 4)
        for event in context["events"].values():
            phase = phase_weighted_mean(filtered[event["minute_index"]],
                                        event["pair_count"], event["support"])
            f_event = phase[event["support"]["valid"]]
            f_quiet = filtered[event["calibration"]["minute_index"]]
            gain, r, rmse = fit_event(event, f_event, f_quiet)
            rows.append((event["storm_id"], step * 900, gain, r, rmse,
                         len(f_event), VERSION))
    save_grid(rows)
    print(f"Saved {len(rows)} per-event M1A grid rows")


if __name__ == "__main__":
    main()
