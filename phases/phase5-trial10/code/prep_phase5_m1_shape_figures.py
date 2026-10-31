"""Draw held-out M1 shape GPR curves and per-storm RMSE changes."""

import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path("phases/phase5-trial10")
RESULT = ROOT / "data/sqlite/swarm_a_phase5_m1_shape_gpr_v1.sqlite"
M1 = Path("phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
OVERVIEW = ROOT / "figures/m1_shape_gpr_25storm_overview.png"
RMSE = ROOT / "figures/m1_shape_gpr_event_rmse_change.png"
MICROSECONDS_PER_DAY = 86_400_000_000
DENSITY_SCALE = 1e12


def load_result() -> tuple[dict, list[tuple], dict]:
    """Input: read-only Trial 10 and Phase 3 SQLite. Output: {storm: [rows]}, event metrics, {storm: t0_us}."""
    result_uri = f"file:{RESULT.resolve().as_posix()}?mode=ro"
    m1_uri = f"file:{M1.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(result_uri, uri=True)) as database:
        predictions = database.execute("""
            SELECT storm_id,time_us,grid_index,rho_l2_kg_m3,rho_m1_kg_m3,rho_gpr_kg_m3
            FROM prediction ORDER BY storm_id,time_us
        """).fetchall()
        metrics = database.execute("""
            SELECT storm_id,m1_log_rmse,gpr_log_rmse FROM event_metric ORDER BY storm_id
        """).fetchall()
    with closing(sqlite3.connect(m1_uri, uri=True)) as database:
        event_times = dict(database.execute(
            "SELECT storm_id,t0_time_us FROM phase3_25storm_overview"))
    storms = defaultdict(list)
    for row in predictions:
        storms[row[0]].append(row[1:])
    if len(storms) != 25 or len(metrics) != 25 or set(storms) != set(event_times):
        raise ValueError("Trial 10 figures require the same 25 storms.")
    return dict(storms), metrics, event_times


def draw_overview(storms: dict, event_times: dict) -> None:
    """Input: {storm: [orbit density rows]}, {storm: t0_us}. Output: 5x5 three-line PNG."""
    figure, axes = plt.subplots(5, 5, figsize=(19, 16), sharex=True,
                               constrained_layout=True)
    for axis, (storm_id, rows) in zip(axes.flat, sorted(storms.items()), strict=True):
        days = []
        l2 = []
        m1 = []
        gpr = []
        previous_grid = None
        for time_us, grid, l2_density, m1_density, gpr_density in rows:
            day = (time_us - event_times[storm_id]) / MICROSECONDS_PER_DAY
            if previous_grid is not None and grid != previous_grid + 1:
                days.append(day)
                l2.append(math.nan)
                m1.append(math.nan)
                gpr.append(math.nan)
            days.append(day)
            l2.append(l2_density * DENSITY_SCALE)
            m1.append(m1_density * DENSITY_SCALE)
            gpr.append(gpr_density * DENSITY_SCALE)
            previous_grid = grid
        for density, color in ((l2, "#111827"), (m1, "#2563eb"),
                               (gpr, "#d97706")):
            axis.plot(days, density, color=color, linewidth=0.9)
        axis.axvline(0, color="#9ca3af", linewidth=0.6, linestyle="--")
        axis.set_title(storm_id[1:9], fontsize=9)
        axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel("Days from t0")
    for axis in axes[:, 0]:
        axis.set_ylabel("Density (1e-12 kg/m3)")
    figure.suptitle("25 storms: L2 (black), Phase 3 M1 (blue), M1-shape GPR (orange)",
                    fontsize=13)
    OVERVIEW.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OVERVIEW, dpi=180)
    plt.close(figure)


def draw_event_rmse(metrics: list[tuple]) -> None:
    """Input: [(storm, M1 RMSE, GPR RMSE), ...]. Output: per-storm RMSE-change PNG."""
    ordered = sorted(metrics, key=lambda row: row[2] - row[1])
    labels = [row[0][1:9] for row in ordered]
    changes = [row[2] - row[1] for row in ordered]
    colors = ["#15803d" if change < 0 else "#b45309" for change in changes]
    figure, axis = plt.subplots(figsize=(9, 10), layout="constrained")
    axis.barh(labels, changes, color=colors)
    axis.axvline(0, color="#111827", linewidth=0.8)
    axis.set_xlabel("Held-out log RMSE change: GPR minus M1 (negative is better)")
    axis.set_title("M1-only three-feature GPR: 25 storm results")
    axis.grid(axis="x", alpha=0.15)
    figure.savefig(RMSE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: saved held-out SQLite. Output: two separate comparison PNGs."""
    storms, metrics, event_times = load_result()
    draw_overview(storms, event_times)
    draw_event_rmse(metrics)
    print(f"Saved {OVERVIEW} and {RMSE}")


if __name__ == "__main__":
    main()
