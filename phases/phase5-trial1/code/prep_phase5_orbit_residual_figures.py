"""Plot the observed one-orbit L2 difference from the fixed D-model."""

import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


ROOT = Path("phases/phase5-trial1")
SOURCE = ROOT / "data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite"
TRIAL4 = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
FIGURES = ROOT / "figures/orbit_residual_25storm"
HOUR_US = 3_600_000_000


def read_only(path: Path) -> sqlite3.Connection:
    """Input: SQLite path. Output: read-only connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def load_orbit_residuals() -> dict[str, list[tuple[int, float]]]:
    """Input: saved Trial 1 orbit anchors. Output: {storm_id: [(time_us, log_residual)]}."""
    grouped: dict[str, list[tuple[int, float]]] = defaultdict(list)
    with closing(read_only(SOURCE)) as database:
        rows = database.execute("""
            SELECT storm_id,time_us,rho_l2_phase_kg_m3,rho_trial4_phase_kg_m3,
                   residual_log_density
            FROM phase4_trial4_gpr_prediction ORDER BY storm_id,time_us
        """).fetchall()
    for storm_id, time_us, l2_density, d_model_density, residual in rows:
        if (l2_density <= 0 or d_model_density <= 0
                or not math.isclose(residual, math.log(l2_density / d_model_density),
                                    rel_tol=1e-12, abs_tol=1e-12)):
            raise ValueError(f"Stored D-model residual differs: {storm_id}, {time_us}")
        grouped[storm_id].append((time_us, residual))
    if len(rows) != 2295 or len(grouped) != 25:
        raise ValueError("Expected 2,295 saved anchors across 25 storms.")
    return dict(grouped)


def load_event_times() -> dict[str, int]:
    """Input: frozen Trial 4 overview. Output: {storm_id: t0_time_us}."""
    with closing(read_only(TRIAL4)) as database:
        rows = database.execute(
            "SELECT storm_id,t0_time_us FROM trial4_25storm_overview"
        ).fetchall()
    if len(rows) != 25:
        raise ValueError("Expected 25 Trial 4 event times.")
    return dict(rows)


def draw_event(storm_id: str, rows: list[tuple[int, float]], t0_us: int) -> None:
    """Input: storm ID, [(anchor time, log residual)], event time. Output: one PNG."""
    hours = [(time_us - t0_us) / HOUR_US for time_us, _ in rows]
    percent_difference = [100 * math.expm1(residual) for _, residual in rows]
    figure, axis = plt.subplots(figsize=(11, 4), layout="constrained")
    axis.plot(hours, percent_difference, color="#2563eb", marker="o",
              markersize=2.5, linewidth=1)
    axis.axhline(0, color="#374151", linewidth=1)
    axis.axvline(0, color="#6b7280", linestyle="--", linewidth=1)
    axis.set_title(f"{storm_id}: L2 relative to D-model, one point per orbit")
    axis.set_xlabel(r"Hours from event time $t_0$")
    axis.set_ylabel("L2 / D-model - 1 (%)")
    axis.grid(alpha=0.2)
    figure.savefig(FIGURES / f"{storm_id.lower()}_orbit_residual.png", dpi=160)
    plt.close(figure)


def main() -> None:
    """Input: frozen orbit anchors and event times. Output: 25 residual PNGs."""
    grouped = load_orbit_residuals()
    event_times = load_event_times()
    if set(grouped) != set(event_times):
        raise ValueError("Trial 1 anchors and Trial 4 events differ.")
    FIGURES.mkdir(parents=True, exist_ok=True)
    for storm_id, rows in grouped.items():
        draw_event(storm_id, rows, event_times[storm_id])
    print(f"Saved {len(grouped)} per-orbit residual figures from 2,295 anchors")


if __name__ == "__main__":
    main()
