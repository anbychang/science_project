"""Refine the exploratory response-time grid without changing its data model."""

import csv
import math
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from satellite_orbit.phase3.calc_h_tau import filtered_sme, phase_weighted_mean
from satellite_orbit.phase3.prep_exploratory_fit import (
    GRID_REPORT, QUIET_DENSITY, load_r_candidates,
)
from satellite_orbit.phase3.prep_h_tau_phase import SOURCE, load_event, load_sme


REPORT = Path("output/report/phase3_tau_grid_005h_exploratory.csv")
FIGURE = Path("output/image/Phase3/tau_minimum_005h_exploratory.png")
SME_REFERENCE_NT = 65.0
TAU_STEP_HOURS = 0.05
TAU_STEPS = 201


def load_event_anomalies(events: list[dict], r_by_storm: dict) -> int:
    """Input: event support and {storm: R}. Output: paired anchor count; attaches z."""
    uri = f"file:{QUIET_DENSITY.resolve().as_posix()}?mode=ro"
    total = 0
    with closing(sqlite3.connect(uri, uri=True)) as database:
        for event in events:
            rows = database.execute("""
                SELECT time_us,log_l2_over_quiet_phase,phase_is_valid_80pct
                FROM phase3_quiet_density_minute
                WHERE storm_id=? ORDER BY time_us
            """, (event["storm_id"],)).fetchall()
            times = np.fromiter((row[0] for row in rows), dtype=np.int64)
            valid = np.fromiter((row[2] for row in rows), dtype=bool)
            if not np.array_equal(times, event["time_us"]) or not np.array_equal(
                valid, event["support"]["valid"]
            ):
                raise ValueError(f"Density and phase support differ: {event['storm_id']}")
            event["z"] = np.array([
                row[1] - math.log(r_by_storm[event["storm_id"]])
                for row in rows if row[2]
            ])
            total += len(event["z"])
    return total


def refine_grid(sme: np.ndarray, events: list[dict], fit_count: int) -> list[dict]:
    """Input: [SME], [event support and z], fit count. Output: 201 fit rows."""
    z_squared = sum(float(event["z"] @ event["z"]) for event in events)
    rows = []
    for tau_index in range(TAU_STEPS):
        tau_hours = tau_index * TAU_STEP_HOURS
        response = filtered_sme(sme, tau_hours) - SME_REFERENCE_NT
        cross = 0.0
        response_squared = 0.0
        for event in events:
            raw = response[event["minute_index"]]
            phase = phase_weighted_mean(raw, event["pair_count"], event["support"])
            paired_phase = phase[event["support"]["valid"]]
            cross += float(paired_phase @ event["z"])
            response_squared += float(paired_phase @ paired_phase)
        gain = cross / response_squared
        rmse = math.sqrt(max(z_squared - gain * cross, 0) / fit_count)
        rows.append({"tau_hours": round(tau_hours, 2),
                     "gain_per_nt": gain, "train_rmse_log_density": rmse,
                     "fit_minutes": fit_count,
                     "status": "provisional_R_exploratory"})
    return rows


def check_coarse_grid(rows: list[dict]) -> None:
    """Input: 0.05-hour rows. Output: raises if shared 0.25-hour points differ."""
    with GRID_REPORT.open(encoding="utf-8-sig", newline="") as source:
        coarse = list(csv.DictReader(source))
    for index, original in enumerate(coarse):
        refined = rows[5 * index]
        for name in ("gain_per_nt", "train_rmse_log_density"):
            if not math.isclose(float(original[name]), refined[name], abs_tol=1e-10):
                raise ValueError(f"Fine grid changed the coarse fit at {index / 4} h.")


def draw_minimum(rows: list[dict]) -> None:
    """Input: 0.05-hour fit rows. Output: zoomed minimum PNG."""
    near = [row for row in rows if 3 <= row["tau_hours"] <= 7]
    best = min(rows, key=lambda row: row["train_rmse_log_density"])
    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    axis.plot([row["tau_hours"] for row in near],
              [row["train_rmse_log_density"] for row in near], color="#2563eb")
    axis.scatter(best["tau_hours"], best["train_rmse_log_density"],
                 color="#dc2626", zorder=3)
    axis.set(xlabel="tau (hours)", ylabel="Train RMSE (log density)",
             title="Exploratory fine grid with provisional R")
    axis.grid(alpha=0.25)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: frozen Phase 2 and provisional R. Output: finer grid CSV and PNG."""
    if REPORT.exists() or FIGURE.exists():
        raise FileExistsError("Fine-grid exploratory output already exists.")
    r_by_storm = load_r_candidates()
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        sme, first_time_us = load_sme(database)
        storm_ids = [row[0] for row in database.execute(
            "SELECT storm_id FROM storm_event_t0_phase_v5 ORDER BY t0_time_us")]
        events = [load_event(database, storm_id, first_time_us)
                  for storm_id in storm_ids]
    fit_count = load_event_anomalies(events, r_by_storm)
    rows = refine_grid(sme, events, fit_count)
    check_coarse_grid(rows)
    with REPORT.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    draw_minimum(rows)
    best = min(rows, key=lambda row: row["train_rmse_log_density"])
    print(f"Fine-grid minimum: {best['tau_hours']} h, "
          f"G={best['gain_per_nt']:.8f} 1/nT, "
          f"RMSE={best['train_rmse_log_density']:.8f}")


if __name__ == "__main__":
    main()
