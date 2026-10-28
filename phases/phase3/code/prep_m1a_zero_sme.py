"""Fit an isolated M1A variant with a zero SME reference."""

import csv
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

from phases.phase3.code.prep_phase3_rquiet_candidates import pair_candidates
from phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean
from phases.phase3.code.prep_exploratory_fit import QUIET_DENSITY
from phases.phase3.code.prep_h_tau_phase import SOURCE, load_event, load_sme


WINDOWS = Path("phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv")
OUTPUT = Path("phases/phase3/data/sqlite/swarm_a_phase3_m1a_zero_sme_v1.sqlite")
VERSION = "phase3_m1a_zero_sme_v1"
MINUTE_US = 60_000_000
MAX_GAIN_PER_NT = 0.01


def utc_us(value: str) -> int:
    """Input: UTC ISO timestamp. Output: integer microseconds since Unix epoch."""
    return round(datetime.fromisoformat(value).timestamp() * 1_000_000)


def load_quiet_windows(first_time_us: int) -> dict[str, dict]:
    """Input: SME first time_us. Output: {storm: pre-window indices and log ratios}."""
    with WINDOWS.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    targets = {}
    for row in rows:
        start = utc_us(row["near_zero_start_utc"])
        end = utc_us(row["near_zero_end_exclusive_utc"])
        targets.update({time_us: [row["storm_id"]]
                        for time_us in range(start, end, MINUTE_US)})
    ratios = pair_candidates(targets)
    windows = {}
    for row in rows:
        start = utc_us(row["near_zero_start_utc"])
        end = utc_us(row["near_zero_end_exclusive_utc"])
        times = np.arange(start, end, MINUTE_US, dtype=np.int64)
        if len(times) != int(row["paired_l2_minutes"]) or any(
            int(time_us) not in ratios for time_us in times
        ):
            raise ValueError(f"Quiet density coverage changed: {row['storm_id']}")
        elapsed_us = times - first_time_us
        if np.any(elapsed_us % MINUTE_US):
            raise ValueError(f"Quiet minute alignment changed: {row['storm_id']}")
        windows[row["storm_id"]] = {
            "minute_index": elapsed_us // MINUTE_US,
            "log_ratio": np.array([ratios[int(time_us)] for time_us in times]),
            "source_r_candidate": float(row["r_near_zero_median_candidate"]),
        }
        if not math.isclose(float(np.median(np.exp(windows[row["storm_id"]]["log_ratio"]))),
                            windows[row["storm_id"]]["source_r_candidate"],
                            rel_tol=1e-10):
            raise ValueError(f"Original R could not be reproduced: {row['storm_id']}")
    if len(windows) != 25:
        raise ValueError(f"Expected 25 calibration windows, got {len(windows)}")
    return windows


def load_context() -> dict:
    """Input: frozen SME, phase support and quiet MSIS. Output: M1A fit context."""
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        sme, first_time_us = load_sme(source)
        storm_ids = [row[0] for row in source.execute(
            "SELECT storm_id FROM storm_event_t0_phase_v5 ORDER BY t0_time_us")]
        events = {storm_id: load_event(source, storm_id, first_time_us)
                  for storm_id in storm_ids}
    windows = load_quiet_windows(first_time_us)
    density_uri = f"file:{QUIET_DENSITY.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(density_uri, uri=True)) as database:
        for storm_id, event in events.items():
            rows = database.execute("""
                SELECT time_us,rho_l2_phase_kg_m3,rho_msis_quiet_phase_kg_m3
                FROM phase3_quiet_density_minute
                WHERE storm_id=? AND phase_is_valid_80pct=1 ORDER BY time_us
            """, (storm_id,)).fetchall()
            times = np.array([row[0] for row in rows], dtype=np.int64)
            if not np.array_equal(times, event["time_us"][event["support"]["valid"]]):
                raise ValueError(f"Event density and phase support differ: {storm_id}")
            event["valid_time_us"] = times
            event["l2"] = np.array([row[1] for row in rows])
            event["quiet"] = np.array([row[2] for row in rows])
            event["log_ratio"] = np.log(event["l2"] / event["quiet"])
            event["calibration"] = windows[storm_id]
    return {"sme": sme, "events": events}


def fit_at_tau(context: dict, tau_hours: float) -> dict:
    """Input: M1A context and tau hours. Output: fitted gain, RMSE and event R values."""
    filtered = filtered_sme(context["sme"], tau_hours)
    statistics = []
    for event in context["events"].values():
        phase = phase_weighted_mean(filtered[event["minute_index"]],
                                    event["pair_count"], event["support"])
        f = phase[event["support"]["valid"]]
        y = event["log_ratio"]
        quiet = event["calibration"]
        statistics.append({
            "storm_id": event["storm_id"], "f": f,
            "f_quiet": filtered[quiet["minute_index"]],
            "y_quiet": quiet["log_ratio"], "n": len(y),
            "sum_y": float(np.sum(y)), "sum_f": float(np.sum(f)),
            "sum_y2": float(y @ y), "sum_f2": float(f @ f),
            "sum_yf": float(y @ f),
        })

    def squared_error(gain: float) -> float:
        """Input: candidate G in 1/nT. Output: pooled squared log-density error."""
        total = 0.0
        for item in statistics:
            baseline = math.log(float(np.median(np.exp(
                item["y_quiet"] - gain * item["f_quiet"]))))
            total += (item["sum_y2"] - 2 * baseline * item["sum_y"]
                      - 2 * gain * item["sum_yf"] + item["n"] * baseline ** 2
                      + 2 * baseline * gain * item["sum_f"]
                      + gain ** 2 * item["sum_f2"])
        return total

    optimum = minimize_scalar(squared_error, bounds=(0, MAX_GAIN_PER_NT),
                              method="bounded", options={"xatol": 1e-11})
    if not optimum.success or not 0 < optimum.x < MAX_GAIN_PER_NT:
        raise ValueError(f"M1A gain not identified at tau={tau_hours} h")
    gain = float(optimum.x)
    calibrations = {
        item["storm_id"]: float(np.median(np.exp(
            item["y_quiet"] - gain * item["f_quiet"])))
        for item in statistics
    }
    return {"tau_hours": tau_hours, "gain_per_nt": gain,
            "rmse_log_density": math.sqrt(max(optimum.fun, 0)
                                          / sum(item["n"] for item in statistics)),
            "calibrations": calibrations}


def save_results(context: dict, grid: list[dict]) -> None:
    """Input: M1A context and tau grid. Output: isolated fit and prediction SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    best = min(grid, key=lambda row: row["rmse_log_density"])
    filtered = filtered_sme(context["sme"], best["tau_hours"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="m1a_zero_sme_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            with database:
                database.execute("""CREATE TABLE phase3_m1a_grid (
                    tau_seconds INTEGER PRIMARY KEY,
                    gain_per_nt REAL NOT NULL,
                    rmse_log_density REAL NOT NULL,
                    algorithm_version TEXT NOT NULL)""")
                database.execute("""CREATE TABLE phase3_m1a_event (
                    storm_id TEXT PRIMARY KEY,
                    tau_seconds INTEGER NOT NULL,
                    r_zero_sme_extrapolated REAL NOT NULL,
                    quiet_minutes INTEGER NOT NULL,
                    fit_minutes INTEGER NOT NULL,
                    rmse_log_density REAL NOT NULL,
                    algorithm_version TEXT NOT NULL)""")
                database.execute("""CREATE TABLE phase3_m1a_prediction_minute (
                    storm_id TEXT NOT NULL,
                    time_us INTEGER NOT NULL,
                    rho_l2_phase_kg_m3 REAL NOT NULL,
                    rho_msis_quiet_phase_kg_m3 REAL NOT NULL,
                    sme_filtered_phase_nt REAL NOT NULL,
                    rho_m1a_phase_kg_m3 REAL NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id,time_us))""")
                database.executemany("INSERT INTO phase3_m1a_grid VALUES (?,?,?,?)",
                                     ((round(row["tau_hours"] * 3600),
                                       row["gain_per_nt"], row["rmse_log_density"],
                                       VERSION) for row in grid))
                for event in context["events"].values():
                    storm_id = event["storm_id"]
                    phase = phase_weighted_mean(filtered[event["minute_index"]],
                                                event["pair_count"], event["support"])
                    f = phase[event["support"]["valid"]]
                    r = best["calibrations"][storm_id]
                    prediction = event["quiet"] * r * np.exp(best["gain_per_nt"] * f)
                    if not np.isfinite(prediction).all() or np.any(prediction <= 0):
                        raise ValueError(f"Invalid M1A prediction: {storm_id}")
                    rmse = float(np.sqrt(np.mean(
                        np.log(event["l2"] / prediction) ** 2)))
                    database.execute("INSERT INTO phase3_m1a_event VALUES (?,?,?,?,?,?,?)",
                                     (storm_id, round(best["tau_hours"] * 3600), r,
                                      len(event["calibration"]["log_ratio"]),
                                      len(f), rmse, VERSION))
                    database.executemany("INSERT INTO phase3_m1a_prediction_minute "
                                         "VALUES (?,?,?,?,?,?,?)",
                                         ((storm_id, int(time), float(l2), float(quiet),
                                           float(value), float(pred), VERSION)
                                          for time, l2, quiet, value, pred in zip(
                                              event["valid_time_us"], event["l2"],
                                              event["quiet"], f, prediction,
                                              strict=True)))
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("M1A SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"M1A tau={best['tau_hours']:.2f} h, "
          f"G={best['gain_per_nt']:.9f} 1/nT, "
          f"RMSE={best['rmse_log_density']:.6f}")


def main() -> None:
    """Input: frozen event data and original pre-event windows. Output: M1A SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    context = load_context()
    grid = [fit_at_tau(context, step / 4) for step in range(41)]
    coarse = min(grid, key=lambda row: row["rmse_log_density"])["tau_hours"]
    if 0 < coarse < 10:
        fine = [round(coarse - 0.25 + step * 0.05, 2) for step in range(11)]
        existing = {row["tau_hours"] for row in grid}
        grid.extend(fit_at_tau(context, tau) for tau in fine if tau not in existing)
    save_results(context, grid)


if __name__ == "__main__":
    main()
