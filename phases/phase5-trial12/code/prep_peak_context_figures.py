"""Draw held-out temporal GP density curves and event shape RMSE changes."""

import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path("phases/phase5-trial12")
RESULT = ROOT / "data/sqlite/swarm_a_phase5_peak_context_gpr_v1.sqlite"
SOURCE = Path("phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
OVERVIEW = ROOT / "figures/peak_context_gpr_25storm_overview.png"
CHANGE = ROOT / "figures/peak_context_gpr_event_shape_change.png"
DAY_US = 86_400_000_000
SCALE = 1e12


def load_result() -> tuple[dict, list, dict]:
    """Input: saved Trial 12 SQLite and event t0. Output: predictions, event scores, times."""
    uri = f"file:{RESULT.resolve().as_posix()}?mode=ro"
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT storm_id,time_us,grid_index,rho_l2_kg_m3,rho_m1_kg_m3,rho_gp_kg_m3
            FROM prediction ORDER BY storm_id,grid_index
        """).fetchall()
        scores = database.execute("""
            SELECT storm_id,m1_shape_rmse,gp_shape_rmse
            FROM event_metric ORDER BY storm_id
        """).fetchall()
    with closing(sqlite3.connect(source_uri, uri=True)) as database:
        times = dict(database.execute(
            "SELECT storm_id,t0_time_us FROM phase3_25storm_overview"))
    by_storm = defaultdict(list)
    for storm, *values in rows:
        by_storm[storm].append(values)
    if len(by_storm) != 25 or len(scores) != 25 or set(by_storm) != set(times):
        raise ValueError("Figures require the same 25 storms.")
    return dict(by_storm), scores, times


def draw_overview(storms: dict, times: dict) -> None:
    """Input: {storm: [orbit densities]}, {storm: t0_us}. Output: 5x5 PNG."""
    figure, axes = plt.subplots(5, 5, figsize=(19, 16), sharex=True,
                               constrained_layout=True)
    for axis, (storm, rows) in zip(axes.flat, sorted(storms.items()), strict=True):
        days, l2, m1, gp = [], [], [], []
        previous_grid = None
        for time_us, grid, l2_density, m1_density, gp_density in rows:
            day = (time_us - times[storm]) / DAY_US
            if previous_grid is not None and grid != previous_grid + 1:
                days.append(day)
                l2.append(math.nan)
                m1.append(math.nan)
                gp.append(math.nan)
            days.append(day)
            l2.append(l2_density * SCALE)
            m1.append(m1_density * SCALE)
            gp.append(gp_density * SCALE)
            previous_grid = grid
        for density, color in ((l2, "#111827"), (m1, "#2563eb"),
                               (gp, "#d97706")):
            axis.plot(days, density, color=color, linewidth=0.9)
        axis.axvline(0, color="#9ca3af", linewidth=0.6, linestyle="--")
        axis.set_title(storm[1:9], fontsize=9)
        axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel("Days from t0")
    for axis in axes[:, 0]:
        axis.set_ylabel("Density (1e-12 kg/m3)")
    figure.suptitle("25 storms: L2 (black), M1 (blue), peak-context GP (orange)",
                    fontsize=13)
    OVERVIEW.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OVERVIEW, dpi=180)
    plt.close(figure)


def draw_event_change(scores: list) -> None:
    """Input: [(storm, M1 shape RMSE, GP shape RMSE)]. Output: event change PNG."""
    ordered = sorted(scores, key=lambda row: row[2] - row[1])
    labels = [row[0][1:9] for row in ordered]
    changes = [row[2] - row[1] for row in ordered]
    colors = ["#15803d" if value < 0 else "#b45309" for value in changes]
    figure, axis = plt.subplots(figsize=(9, 10), layout="constrained")
    axis.barh(labels, changes, color=colors)
    axis.axvline(0, color="#111827", linewidth=0.8)
    axis.set_xlabel("Held-out shape RMSE change: GP minus M1 (negative is better)")
    axis.set_title("Peak-context GP: per-storm curve-shape result")
    axis.grid(axis="x", alpha=0.15)
    figure.savefig(CHANGE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: saved Trial 12 SQLite. Output: two separate comparison PNGs."""
    storms, scores, times = load_result()
    draw_overview(storms, times)
    draw_event_change(scores)
    print(f"Saved {OVERVIEW} and {CHANGE}")


if __name__ == "__main__":
    main()
