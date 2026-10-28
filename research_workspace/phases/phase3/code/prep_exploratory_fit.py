"""Fit an exploratory 41-point SME response grid with provisional R values."""

import csv
import math
import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


QUIET_DENSITY = Path("research_workspace/phases/phase3/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite")
H_TAU = Path("research_workspace/phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite")
R_CANDIDATES = Path("research_workspace/phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv")
GRID_REPORT = Path("research_workspace/phases/phase3/data/analysis/phase3_baseline_grid_exploratory.csv")
EVENT_REPORT = Path("research_workspace/phases/phase3/data/analysis/phase3_baseline_event_exploratory.csv")
FIGURE = Path("research_workspace/phases/phase3/figures/rmse_tau_exploratory.png")
TAU_STEPS = 41


def load_r_candidates() -> dict[str, float]:
    """Input: provisional 25-event CSV. Output: {storm_id: positive R}."""
    with R_CANDIDATES.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    result = {row["storm_id"]: float(row["r_near_zero_median_candidate"])
              for row in rows}
    if len(rows) != 25 or len(result) != 25 or any(r <= 0 for r in result.values()):
        raise ValueError("Provisional R table needs 25 positive event values.")
    return result


def load_fit_arrays(r_by_storm: dict[str, float]) -> tuple:
    """Input: {storm: R}. Output: [z], [N x 41 phase H], [storm index], [IDs]."""
    uri = f"file:{QUIET_DENSITY.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        h_uri = f"file:{H_TAU.resolve().as_posix()}?mode=ro"
        database.execute("ATTACH DATABASE ? AS h", (h_uri,))
        bad_rows, joined_rows = database.execute("""
            SELECT sum(q.phase_is_valid_80pct<>h.phase_is_valid_80pct),
                   sum(q.phase_is_valid_80pct)
            FROM phase3_quiet_density_minute AS q
            JOIN h.phase3_h_tau_minute AS h
              ON q.storm_id=h.storm_id AND q.time_us=h.time_us
        """).fetchone()
        row_count = database.execute(
            "SELECT sum(phase_is_valid_80pct) FROM phase3_quiet_density_minute"
        ).fetchone()[0]
        if bad_rows or joined_rows != row_count:
            raise ValueError("Quiet density and SME-response phase support differ.")
        identifiers = list(r_by_storm)
        storm_index = {storm_id: index for index, storm_id in enumerate(identifiers)}
        z = np.empty(row_count)
        h = np.empty((row_count, TAU_STEPS))
        event_index = np.empty(row_count, dtype=np.int16)
        columns = ",".join(f"h.h_phase_tau_{index:02d}_nt"
                           for index in range(TAU_STEPS))
        query = ("SELECT q.storm_id,q.log_l2_over_quiet_phase,"
                 + columns + " FROM phase3_quiet_density_minute AS q "
                 "JOIN h.phase3_h_tau_minute AS h "
                 "ON q.storm_id=h.storm_id AND q.time_us=h.time_us "
                 "WHERE q.phase_is_valid_80pct=1 "
                 "ORDER BY q.storm_id,q.time_us")
        for row_index, row in enumerate(database.execute(query)):
            z[row_index] = row[1] - math.log(r_by_storm[row[0]])
            h[row_index] = row[2:]
            event_index[row_index] = storm_index[row[0]]
    if not np.isfinite(z).all() or not np.isfinite(h).all():
        raise ValueError("Fit arrays contain missing or non-finite paired values.")
    return z, h, event_index, identifiers


def fit_grid(z: np.ndarray, h: np.ndarray) -> list[dict]:
    """Input: [log-density anomaly], [N x 41 response]. Output: grid rows."""
    cross = h.T @ z
    squared_response = np.sum(h * h, axis=0)
    gain = cross / squared_response
    squared_error = np.sum(z * z) - 2 * gain * cross + gain * gain * squared_response
    rmse = np.sqrt(np.maximum(squared_error, 0) / len(z))
    return [{"tau_hours": index / 4, "gain_per_nt": float(gain[index]),
             "train_rmse_log_density": float(rmse[index]),
             "fit_minutes": len(z), "status": "provisional_R_exploratory"}
            for index in range(TAU_STEPS)]


def event_rows(data: dict, grid: list[dict]) -> list[dict]:
    """Input: {z, h, event_index, identifiers} and grid. Output: event RMSE."""
    z = data["z"]
    h = data["h"]
    event_index = data["event_index"]
    best = min(range(TAU_STEPS), key=lambda index: grid[index]["train_rmse_log_density"])
    residual = z - grid[best]["gain_per_nt"] * h[:, best]
    return [{"storm_id": storm_id, "tau_hours": best / 4,
             "gain_per_nt": grid[best]["gain_per_nt"],
             "fit_minutes": int(np.count_nonzero(event_index == index)),
             "rmse_log_density": float(np.sqrt(np.mean(residual[event_index == index] ** 2))),
             "status": "provisional_R_exploratory"}
            for index, storm_id in enumerate(data["identifiers"])]


def write_csv(rows: list[dict], path: Path) -> None:
    """Input: [{field: value}] and new path. Output: saved CSV."""
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_grid(rows: list[dict]) -> None:
    """Input: 41 fit rows. Output: exploratory RMSE and gain plot."""
    tau = [row["tau_hours"] for row in rows]
    rmse = [row["train_rmse_log_density"] for row in rows]
    gain = [row["gain_per_nt"] for row in rows]
    figure, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True,
                                     constrained_layout=True)
    axes[0].plot(tau, rmse, color="#2563eb", marker=".")
    axes[0].set(ylabel="Train RMSE (log density)",
                title="Exploratory Phase 3: provisional R, 25 storms")
    axes[1].plot(tau, gain, color="#d97706", marker=".")
    axes[1].axhline(0, color="#64748b", linestyle="--", linewidth=1)
    axes[1].set(xlabel="tau (hours)", ylabel="G (1/nT)", xlim=(0, 10))
    for axis in axes:
        axis.grid(alpha=0.25)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: Phase 3 density, response and candidate R. Output: fit CSVs and plot."""
    if GRID_REPORT.exists() or EVENT_REPORT.exists() or FIGURE.exists():
        raise FileExistsError("Exploratory fit output already exists.")
    z, h, event_index, identifiers = load_fit_arrays(load_r_candidates())
    grid = fit_grid(z, h)
    write_csv(grid, GRID_REPORT)
    data = {"z": z, "h": h, "event_index": event_index,
            "identifiers": identifiers}
    write_csv(event_rows(data, grid), EVENT_REPORT)
    draw_grid(grid)
    best = min(grid, key=lambda row: row["train_rmse_log_density"])
    print(f"Saved exploratory fit: tau={best['tau_hours']} h, "
          f"G={best['gain_per_nt']:.6g} 1/nT, "
          f"RMSE={best['train_rmse_log_density']:.5f}")


if __name__ == "__main__":
    main()
