"""Draw density and decay comparisons for the configured Phase 7 storm set."""

import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from phases.phase1.code.prep_10_phase_orbit_mean import phase_orbit_rows
from phases.phase7.code.load_phase7_two_storms import (
    PHASE1R,
    RUN_LABEL,
    RUN_ROOT,
    STORM_IDS,
    read_only,
)


DENSITY = RUN_ROOT / "data" / "sqlite" / "swarm_a_phase7_density_v1.sqlite"
DECAY = RUN_ROOT / "data" / "sqlite" / "swarm_a_phase7_decay_v1.sqlite"
OUTPUT = RUN_ROOT / "figures" / f"phase7_{RUN_LABEL}.png"
HOUR_US = 3_600_000_000


def grouped_rows(path: Path, query: str) -> dict[str, list[sqlite3.Row]]:
    """Input: SQLite path and ordered query. Output: {storm_id: [rows]}."""
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    with closing(read_only(path)) as database:
        for row in database.execute(query):
            grouped[str(row["storm_id"])].append(row)
    if set(grouped) != set(STORM_IDS):
        raise ValueError(f"Phase 7 figure storms differ from selection: {path}")
    return dict(grouped)


def storm_epoch_us(storm_id: str) -> int:
    """Input: SYYYYMMDDTHHMM storm ID. Output: UTC epoch us."""
    value = datetime.strptime(storm_id[1:], "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1_000_000)


def pod_orbit_decline(
    connection: sqlite3.Connection, bounds: tuple[int, int]
) -> list[tuple[int, float]]:
    """Input: Phase 1R and event [start, end]. Output: complete-orbit POD decline points."""
    start_time_us, end_time_us = bounds
    source_rows = connection.execute("""
        SELECT q.chunk_id,m.time_us,m.mean_semi_major_axis_m,
               m.mean_argument_of_perigee_rad,m.mean_anomaly_rad
        FROM swarm_a_mean_orbit_elements_v1 AS m
        JOIN swarm_a_pod_quality AS q ON q.time_us=m.time_us
        WHERE m.time_us>=? AND m.time_us<=?
          AND q.is_usable=1 AND q.chunk_id IS NOT NULL
          AND m.rejection_reason IS NULL
        ORDER BY q.chunk_id,m.time_us
    """, (start_time_us - 6 * HOUR_US, end_time_us)).fetchall()
    orbits = list(phase_orbit_rows(source_rows))
    reference_rows = [row for row in orbits if row[0] < start_time_us]
    if not reference_rows:
        raise ValueError("No complete pre-window Phase 1R orbit for Phase 7 figure.")
    reference = float(reference_rows[-1][2])
    points = [
        (int(row[0]), float(row[2]) - reference)
        for row in orbits
        if row[1] >= start_time_us and row[0] <= end_time_us
    ]
    if not points:
        raise ValueError("No complete Phase 1R orbit inside Phase 7 window.")
    return points


def draw_figure() -> Path:
    """Input: Phase 7 density/decay and Phase 1R. Output: selected-event PNG."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    density = grouped_rows(DENSITY, """
        SELECT storm_id,time_us,rho_l2_phase_kg_m3,rho_m0_full_phase_kg_m3,
               rho_ridge_external_kg_m3
        FROM phase7_density_minute_v1 ORDER BY storm_id,time_us
    """)
    decay = grouped_rows(DECAY, """
        SELECT storm_id,time_us,predicted_m0_covered_delta_a_m,
               predicted_ridge_covered_delta_a_m
        FROM phase7_decay_minute_v1 ORDER BY storm_id,time_us
    """)
    figure, axes = plt.subplots(
        len(density), 2, figsize=(14, 4 * len(density)), constrained_layout=True,
        squeeze=False,
    )
    with closing(read_only(PHASE1R)) as phase1:
        for row_index, storm_id in enumerate(sorted(density)):
            t0_time_us = storm_epoch_us(storm_id)
            density_rows = density[storm_id]
            decay_rows = decay[storm_id]
            hours = [(row["time_us"] - t0_time_us) / HOUR_US for row in density_rows]
            density_axis = axes[row_index, 0]
            density_axis.plot(
                hours,
                [row["rho_l2_phase_kg_m3"] / 1e-12 for row in density_rows],
                color="#111827",
                linewidth=0.8,
                label="L2",
            )
            density_axis.plot(
                hours,
                [row["rho_m0_full_phase_kg_m3"] / 1e-12 for row in density_rows],
                color="#2563eb",
                linewidth=0.8,
                label="M0",
            )
            density_axis.plot(
                hours,
                [row["rho_ridge_external_kg_m3"] / 1e-12 for row in density_rows],
                color="#d97706",
                linewidth=0.8,
                label="Ridge",
            )
            density_axis.axvline(0, color="#64748b", linestyle="--", linewidth=0.8)
            density_axis.set(
                title=f"{storm_id}: density",
                ylabel="Density (1e-12 kg/m3)",
            )
            density_axis.grid(alpha=0.2)
            density_axis.legend(loc="upper right", fontsize=8)

            start_time_us = int(decay_rows[0]["time_us"])
            end_time_us = int(decay_rows[-1]["time_us"])
            pod_points = pod_orbit_decline(phase1, (start_time_us, end_time_us))
            decay_axis = axes[row_index, 1]
            decay_axis.plot(
                [(time_us - t0_time_us) / HOUR_US for time_us, _ in pod_points],
                [value for _, value in pod_points],
                color="#111827",
                marker="o",
                markersize=2,
                linewidth=0.8,
                label="POD orbit mean",
            )
            decay_hours = [(row["time_us"] - t0_time_us) / HOUR_US for row in decay_rows]
            decay_axis.plot(
                decay_hours,
                [row["predicted_m0_covered_delta_a_m"] for row in decay_rows],
                color="#2563eb",
                linewidth=0.9,
                label="M0",
            )
            decay_axis.plot(
                decay_hours,
                [row["predicted_ridge_covered_delta_a_m"] for row in decay_rows],
                color="#d97706",
                linewidth=0.9,
                label="Ridge",
            )
            decay_axis.axvline(0, color="#64748b", linestyle="--", linewidth=0.8)
            decay_axis.set(title=f"{storm_id}: cumulative semi-major-axis change", ylabel="Delta a (m)")
            decay_axis.grid(alpha=0.2)
            decay_axis.legend(loc="lower left", fontsize=8)
    axes[-1, 0].set_xlabel("Hours from t0")
    axes[-1, 1].set_xlabel("Hours from t0")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT, dpi=180)
    plt.close(figure)
    return OUTPUT


def draw_individual_figures() -> list[Path]:
    """Input: Phase 7 density/decay and Phase 1R. Output: [one PNG per storm]."""
    density = grouped_rows(DENSITY, """
        SELECT storm_id,time_us,rho_l2_phase_kg_m3,rho_m0_full_phase_kg_m3,
               rho_ridge_external_kg_m3
        FROM phase7_density_minute_v1 ORDER BY storm_id,time_us
    """)
    decay = grouped_rows(DECAY, """
        SELECT storm_id,time_us,predicted_m0_covered_delta_a_m,
               predicted_ridge_covered_delta_a_m
        FROM phase7_decay_minute_v1 ORDER BY storm_id,time_us
    """)
    paths = []
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with closing(read_only(PHASE1R)) as phase1:
        for storm_id in sorted(density):
            path = OUTPUT.parent / f"phase7_{RUN_LABEL}_{storm_id}.png"
            if path.exists():
                raise FileExistsError(path)
            t0_time_us = storm_epoch_us(storm_id)
            density_rows = density[storm_id]
            decay_rows = decay[storm_id]
            figure, axes = plt.subplots(1, 2, figsize=(14, 4), constrained_layout=True)
            hours = [(row["time_us"] - t0_time_us) / HOUR_US for row in density_rows]
            axes[0].plot(hours, [row["rho_l2_phase_kg_m3"] / 1e-12 for row in density_rows],
                         color="#111827", linewidth=0.8, label="L2")
            axes[0].plot(hours, [row["rho_m0_full_phase_kg_m3"] / 1e-12 for row in density_rows],
                         color="#2563eb", linewidth=0.8, label="M0")
            axes[0].plot(hours, [row["rho_ridge_external_kg_m3"] / 1e-12 for row in density_rows],
                         color="#d97706", linewidth=0.8, label="Ridge")
            axes[0].axvline(0, color="#64748b", linestyle="--", linewidth=0.8)
            axes[0].set(title=f"{storm_id}: density", xlabel="Hours from t0",
                        ylabel="Density (1e-12 kg/m3)")
            axes[0].grid(alpha=0.2)
            axes[0].legend(loc="upper right", fontsize=8)

            pod_points = pod_orbit_decline(
                phase1, (int(decay_rows[0]["time_us"]), int(decay_rows[-1]["time_us"])),
            )
            decay_hours = [(row["time_us"] - t0_time_us) / HOUR_US for row in decay_rows]
            axes[1].plot([(time_us - t0_time_us) / HOUR_US for time_us, _ in pod_points],
                         [value for _, value in pod_points], color="#111827", marker="o",
                         markersize=2, linewidth=0.8, label="POD orbit mean")
            axes[1].plot(decay_hours,
                         [row["predicted_m0_covered_delta_a_m"] for row in decay_rows],
                         color="#2563eb", linewidth=0.9, label="M0")
            axes[1].plot(decay_hours,
                         [row["predicted_ridge_covered_delta_a_m"] for row in decay_rows],
                         color="#d97706", linewidth=0.9, label="Ridge")
            axes[1].axvline(0, color="#64748b", linestyle="--", linewidth=0.8)
            axes[1].set(title=f"{storm_id}: cumulative semi-major-axis change",
                        xlabel="Hours from t0", ylabel="Delta a (m)")
            axes[1].grid(alpha=0.2)
            axes[1].legend(loc="lower left", fontsize=8)
            figure.savefig(path, dpi=180)
            plt.close(figure)
            paths.append(path)
    return paths


def main() -> None:
    """Input: fixed Phase 7 sources. Output: comparison figure path."""
    print(draw_figure())


if __name__ == "__main__":
    main()
