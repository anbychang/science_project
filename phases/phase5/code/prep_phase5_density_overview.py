"""Draw one 5x5 overview of the Phase 5 held-out density curves."""

import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PREDICTIONS = Path("phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite")
EVENTS = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
FIGURE = Path("phases/phase5/figures/phase5_density_25storm_overview.png")
MICROSECONDS_PER_DAY = 86_400_000_000
DENSITY_PLOT_SCALE = 1e12


def load_storms() -> dict[str, list[tuple]]:
    """Input: Phase 5 SQLite. Output: {storm_id: [(time_us, phase_rad, L2, D-model, GPR_or_none), ...]}."""
    uri = f"file:{PREDICTIONS.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT anchor.storm_id,anchor.time_us,anchor.u_rel_rad,
                   anchor.rho_l2_phase_kg_m3,anchor.rho_trial4_phase_kg_m3,
                   prediction.rho_pooled_gpr_kg_m3
            FROM phase5_orbit_anchor AS anchor
            LEFT JOIN phase5_orbit_prediction AS prediction
              ON prediction.storm_id=anchor.storm_id
             AND prediction.time_us=anchor.time_us
            ORDER BY anchor.storm_id,anchor.time_us
        """).fetchall()
    storms = defaultdict(list)
    for storm_id, time_us, phase_rad, l2, phase4, phase5 in rows:
        if (not all(math.isfinite(value) and value > 0 for value in (l2, phase4))
                or phase5 is not None and
                (not math.isfinite(phase5) or phase5 <= 0)):
            raise ValueError(f"Invalid density in {storm_id}.")
        storms[storm_id].append((time_us, phase_rad, l2, phase4, phase5))
    predictions = sum(row[5] is not None for row in rows)
    if len(storms) != 25 or len(rows) != 2295 or predictions != 2265:
        raise ValueError("Expected 25 storms, 2,295 anchors and 2,265 predictions.")
    return dict(storms)


def load_event_times() -> dict[str, int]:
    """Input: fixed Phase 4 event SQLite. Output: {storm_id: t0_time_us}."""
    uri = f"file:{EVENTS.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        return dict(database.execute(
            "SELECT storm_id,t0_time_us FROM trial4_25storm_overview"))


def draw_overview(storms: dict[str, list[tuple]], event_times: dict[str, int]) -> Path:
    """Input: {storm: [held-out orbit]}, {storm: t0_us}. Output: one 5x5 PNG path."""
    if len(storms) != 25 or set(storms) != set(event_times):
        raise ValueError("Storms and event times differ.")
    figure, axes = plt.subplots(5, 5, figsize=(19, 16), sharex=True,
                               constrained_layout=True)
    for axis, (storm_id, rows) in zip(axes.flat, sorted(storms.items()), strict=True):
        days_from_t0 = []
        l2_density = []
        phase4_density = []
        phase5_density = []
        last_grid = None
        for time_us, phase_rad, l2, phase4, phase5 in rows:
            day = (time_us - event_times[storm_id]) / MICROSECONDS_PER_DAY
            grid = round(phase_rad / (2 * math.pi))
            if last_grid is not None and grid != last_grid + 1:
                days_from_t0.append(day)
                l2_density.append(math.nan)
                phase4_density.append(math.nan)
                phase5_density.append(math.nan)
            days_from_t0.append(day)
            l2_density.append(l2 * DENSITY_PLOT_SCALE)
            phase4_density.append(phase4 * DENSITY_PLOT_SCALE)
            phase5_density.append(
                phase5 * DENSITY_PLOT_SCALE if phase5 is not None else math.nan)
            last_grid = grid
        for density, color in (
            (l2_density, "#111827"),
            (phase4_density, "#2563eb"),
            (phase5_density, "#d97706"),
        ):
            axis.plot(days_from_t0, density, linewidth=0.9, color=color)
        axis.axvline(0, color="#9ca3af", linewidth=0.6, linestyle="--")
        axis.set_title(storm_id[1:9], fontsize=9)
        axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel("Days from t0")
    for axis in axes[:, 0]:
        axis.set_ylabel("Density (1e-12 kg/m3)")
    figure.suptitle(
        "25 storms: Swarm-A L2 (black), Phase 4 (blue), Phase 5 GPR (orange)",
        fontsize=13,
    )
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)
    return FIGURE


def main() -> None:
    """Input: fixed Phase 4 t0 and Phase 5 predictions. Output: one 5x5 PNG."""
    path = draw_overview(load_storms(), load_event_times())
    if path.stat().st_size == 0:
        raise ValueError("Phase 5 density overview is empty.")
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
