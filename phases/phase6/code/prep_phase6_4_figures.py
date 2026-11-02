"""Draw the P6.4 density and semi-major-axis decline comparisons."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MICROSECONDS_PER_HOUR = 3_600_000_000
MICROSECONDS_PER_MINUTE = 60_000_000
MAXIMUM_POD_GAP_US = 10_000_000
FIGURE_DPI = 180
DENSITY_PLOT_SCALE_KG_M3 = 1.0e-12
MODEL_COLORS = {
    "POD orbit mean": "#111827",
    "L2": "#111827",
    "M0": "#64748b",
    "P5 V2 Ridge": "#ea580c",
}
DENSITY_LINES = (
    ("rho_l2_kg_m3", "L2", 1.2),
    ("rho_m0_kg_m3", "M0", 1.0),
    ("rho_ridge_kg_m3", "P5 V2 Ridge", 1.0),
)


@dataclass(frozen=True)
class FigurePaths:
    """Input: P6.4 and Phase 1 SQLite. Output: comparison PNG paths."""

    comparison: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_4_decay_comparison_v1.sqlite",
    )
    phase1: Path = Path(
        "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
    )
    ridge_density: Path = Path(
        "phases/phase5-v2/data/sqlite/storm_r_ridge_density_v1.sqlite",
    )
    decay_figure: Path = Path(
        "phases/phase6/figures/phase6_4_decay_time_25_storms.png",
    )
    density_figure: Path = Path(
        "phases/phase6/figures/phase6_4_density_time_25_storms.png",
    )


@dataclass(frozen=True)
class OrbitMeanPoint:
    """Input: one accepted Phase 1 orbit. Output: event-relative orbit-mean change."""

    time_us: int
    segment_index: int
    delta_a_m: float


@dataclass(frozen=True)
class DecayPanel:
    """Input: one storm's minute and orbit rows. Output: one decline panel input."""

    storm_id: str
    minute_rows: list[sqlite3.Row]
    pod_orbit_points: list[OrbitMeanPoint]


def database_uri(path: Path) -> str:
    """Input: SQLite path. Output: read-only SQLite URI."""
    return f"file:{path.resolve().as_posix()}?mode=ro"


def read_only(path: Path) -> sqlite3.Connection:
    """Input: SQLite path. Output: read-only connection with named rows."""
    connection = sqlite3.connect(database_uri(path), uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_event_series(
    connection: sqlite3.Connection,
    l2_density_path: Path,
) -> dict[str, list[sqlite3.Row]]:
    """Input: P6.4/L2 SQLite. Output: {storm_id: [joined density rows]}."""
    connection.execute(
        "ATTACH DATABASE ? AS l2",
        (database_uri(l2_density_path),),
    )
    expected_minute_count = connection.execute(
        "SELECT COUNT(*) FROM phase6_4_decay_comparison_minute_v1",
    ).fetchone()[0]
    events: dict[str, list[sqlite3.Row]] = {}
    rows = connection.execute("""
        SELECT c.storm_id,c.time_us,c.block_index,c.chunk_id,
               c.observed_covered_delta_a_m,c.predicted_m0_covered_delta_a_m,
               c.predicted_ridge_covered_delta_a_m,c.rho_m0_kg_m3,
               c.rho_ridge_kg_m3,d.rho_l2_phase_kg_m3 AS rho_l2_kg_m3
        FROM phase6_4_decay_comparison_minute_v1 AS c
        JOIN l2.density_comparison AS d USING (storm_id,time_us)
        ORDER BY c.storm_id,c.time_us
    """)
    for row in rows:
        events.setdefault(str(row["storm_id"]), []).append(row)
    joined_minute_count = sum(len(event_rows) for event_rows in events.values())
    if joined_minute_count != expected_minute_count:
        raise ValueError(
            "P6.4 L2 density join mismatch: "
            f"{joined_minute_count}/{expected_minute_count} minutes.",
        )
    if len(events) != 25:
        raise ValueError(f"P6.4 figures require 25 storms, found {len(events)}.")
    return events


def event_orbit_mean_points(
    reference_mean_a_m: float,
    orbit_means: list[tuple[int, int, float, int]],
) -> list[OrbitMeanPoint]:
    """Input: event reference and complete orbits. Output: continuous POD segments."""
    points = []
    segment_index = 0
    previous_time_us = None
    previous_chunk_id = None
    for time_us, orbit_start_time_us, mean_a_m, chunk_id in orbit_means:
        new_segment = (
            previous_time_us is None
            or chunk_id != previous_chunk_id
            or orbit_start_time_us - previous_time_us > MAXIMUM_POD_GAP_US
        )
        if new_segment:
            segment_index += 1
        points.append(OrbitMeanPoint(
            time_us,
            segment_index,
            mean_a_m - reference_mean_a_m,
        ))
        previous_time_us = time_us
        previous_chunk_id = chunk_id
    return points


def load_pod_orbit_mean_declines(
    connection: sqlite3.Connection,
    events: dict[str, list[sqlite3.Row]],
) -> dict[str, list[OrbitMeanPoint]]:
    """Input: Phase 1 orbit means and P6.4 events. Output: orbit-mean POD trends."""
    event_points: dict[str, list[OrbitMeanPoint]] = {}
    for storm_id, minute_rows in events.items():
        event_start_time_us = int(minute_rows[0]["time_us"])
        first_chunk_id = int(minute_rows[0]["chunk_id"])
        reference = connection.execute("""
            SELECT phase_weighted_mean_semi_major_axis_m
            FROM swarm_a_phase_orbit_mean_v2
            WHERE time_us < ? AND chunk_id = ?
            ORDER BY time_us DESC
            LIMIT 1
        """, (event_start_time_us, first_chunk_id)).fetchone()
        if reference is None:
            raise ValueError(f"P6.4 found no pre-event POD orbit for {storm_id}.")
        reference_mean_a_m = float(reference[0])
        event_stop_time_us = int(minute_rows[-1]["time_us"])
        event_chunk_ids = {int(row["chunk_id"]) for row in minute_rows}
        orbit_means = [
            (int(row[0]), int(row[1]), float(row[2]), int(row[3]))
            for row in connection.execute("""
                SELECT time_us,orbit_start_time_us,
                       phase_weighted_mean_semi_major_axis_m,chunk_id
                FROM swarm_a_phase_orbit_mean_v2
                WHERE orbit_start_time_us >= ? AND time_us <= ?
                ORDER BY time_us
            """, (event_start_time_us, event_stop_time_us))
            if int(row[3]) in event_chunk_ids
        ]
        points = event_orbit_mean_points(reference_mean_a_m, orbit_means)
        if not points:
            raise ValueError(f"P6.4 found no complete POD orbit for {storm_id}.")
        event_points[storm_id] = points
    return event_points


def storm_epoch_us(storm_id: str) -> int:
    """Input: SYYYYMMDDTHHMM storm ID. Output: UTC epoch microseconds."""
    event_time = datetime.strptime(storm_id[1:], "%Y%m%dT%H%M").replace(
        tzinfo=timezone.utc,
    )
    return int(event_time.timestamp() * 1_000_000)


def relative_hours(rows: list[sqlite3.Row], t0_time_us: int) -> list[float]:
    """Input: {[time_us, ...], t0}. Output: [relative_hour, ...]."""
    return [
        (int(row["time_us"]) - t0_time_us) / MICROSECONDS_PER_HOUR
        for row in rows
    ]


def density_gap_pairs(
    rows: list[sqlite3.Row],
) -> list[tuple[sqlite3.Row, sqlite3.Row]]:
    """Input: ordered minute rows. Output: endpoint pairs around each data gap."""
    return [
        (previous, current)
        for previous, current in zip(rows, rows[1:])
        if int(current["time_us"]) - int(previous["time_us"])
        > MICROSECONDS_PER_MINUTE
    ]


def draw_decay_panel(ax, panel: DecayPanel) -> None:
    """Input: {axes, one storm's minute and orbit rows}. Output: decline panel."""
    t0_time_us = storm_epoch_us(panel.storm_id)
    first_orbit_segment = panel.pod_orbit_points[0].segment_index
    for segment_index, point_iter in groupby(
        panel.pod_orbit_points,
        key=lambda point: point.segment_index,
    ):
        points = list(point_iter)
        ax.plot(
            [
                (point.time_us - t0_time_us) / MICROSECONDS_PER_HOUR
                for point in points
            ],
            [point.delta_a_m for point in points],
            color=MODEL_COLORS["POD orbit mean"],
            linewidth=1.4,
            marker="o",
            markersize=1.8,
            label="POD orbit mean" if segment_index == first_orbit_segment else None,
        )
    for block_number, block_rows_iter in groupby(
        panel.minute_rows,
        key=lambda row: row["block_index"],
    ):
        block_rows = list(block_rows_iter)
        hours = relative_hours(block_rows, t0_time_us)
        labels = block_number == panel.minute_rows[0]["block_index"]
        ax.plot(
            hours,
            [row["predicted_m0_covered_delta_a_m"] for row in block_rows],
            color=MODEL_COLORS["M0"],
            linewidth=1.2,
            label="M0" if labels else None,
        )
        ax.plot(
            hours,
            [row["predicted_ridge_covered_delta_a_m"] for row in block_rows],
            color=MODEL_COLORS["P5 V2 Ridge"],
            linewidth=1.2,
            label="P5 V2 Ridge" if labels else None,
        )
    ax.axvline(0.0, color="#9ca3af", linewidth=0.7, linestyle="--")
    ax.set_title(panel.storm_id[1:9], fontsize=9)
    ax.grid(alpha=0.2, linewidth=0.5)


def draw_density_panel(ax, storm_id: str, rows: list[sqlite3.Row]) -> None:
    """Input: {axes, storm minute rows}. Output: one density panel."""
    t0_time_us = storm_epoch_us(storm_id)
    for density_field, model_name, line_width in DENSITY_LINES:
        times = []
        densities = []
        for previous, current in zip(rows, rows[1:]):
            start = int(previous["time_us"])
            stop = int(current["time_us"])
            for time_us in range(start, stop, MICROSECONDS_PER_MINUTE):
                fraction = (time_us - start) / (stop - start)
                density = previous[density_field] + fraction * (
                    current[density_field] - previous[density_field]
                )
                times.append((time_us - t0_time_us) / MICROSECONDS_PER_HOUR)
                densities.append(density / DENSITY_PLOT_SCALE_KG_M3)
        times.append((int(rows[-1]["time_us"]) - t0_time_us) / MICROSECONDS_PER_HOUR)
        densities.append(rows[-1][density_field] / DENSITY_PLOT_SCALE_KG_M3)
        ax.plot(
            times, densities, color=MODEL_COLORS[model_name],
            linewidth=line_width, label=model_name,
        )
    ax.axvline(0.0, color="#9ca3af", linewidth=0.7, linestyle="--")
    ax.set_title(storm_id[1:9], fontsize=9)
    ax.grid(alpha=0.2, linewidth=0.5)


def save_decay_figure(
    panels: list[DecayPanel],
    output_path: Path,
) -> None:
    """Input: {25 decay panels, PNG path}. Output: orbit-mean POD/model figure."""
    figure, axes = plt.subplots(5, 5, figsize=(19, 15), sharex=True)
    for index, panel in enumerate(panels):
        ax = axes.flat[index]
        draw_decay_panel(ax, panel)
        if index // 5 == 4:
            ax.set_xlabel("Hours from t0")
        if index % 5 == 0:
            ax.set_ylabel("Semi-major-axis change (m)")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    figure.suptitle("P6.4 orbit-mean POD and model-predicted semi-major-axis decline")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    write_figure(figure, output_path)


def save_density_figure(
    events: dict[str, list[sqlite3.Row]],
    output_path: Path,
) -> None:
    """Input: {25 event series, PNG path}. Output: L2/M0/Ridge density figure."""
    figure, axes = plt.subplots(5, 5, figsize=(19, 15), sharex=True)
    for index, (storm_id, rows) in enumerate(events.items()):
        ax = axes.flat[index]
        draw_density_panel(ax, storm_id, rows)
        if index // 5 == 4:
            ax.set_xlabel("Hours from t0")
        if index % 5 == 0:
            ax.set_ylabel("Density (1e-12 kg/m³)")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    figure.suptitle("P6.4 observed L2 and model density")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    write_figure(figure, output_path)


def write_figure(figure, output_path: Path) -> None:
    """Input: {Matplotlib figure, PNG path}. Output: atomically written PNG."""
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.stem + ".part.png")
    temporary.unlink(missing_ok=True)
    try:
        figure.savefig(temporary, dpi=FIGURE_DPI, bbox_inches="tight")
        os.replace(temporary, output_path)
    finally:
        plt.close(figure)
        temporary.unlink(missing_ok=True)


def run(paths: FigurePaths = FigurePaths()) -> dict[str, str]:
    """Input: default P6.4 paths. Output: two verified figure paths."""
    with closing(read_only(paths.comparison)) as connection:
        events = load_event_series(connection, paths.ridge_density)
    with closing(read_only(paths.phase1)) as connection:
        orbit_means = load_pod_orbit_mean_declines(connection, events)
    panels = [
        DecayPanel(storm_id, rows, orbit_means[storm_id])
        for storm_id, rows in events.items()
    ]
    save_decay_figure(panels, paths.decay_figure)
    save_density_figure(events, paths.density_figure)
    return {
        "decay_figure": str(paths.decay_figure),
        "density_figure": str(paths.density_figure),
    }


def main() -> None:
    """Input: no arguments. Output: P6.4 figure paths."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.prep_phase6_4_figures")
    print(run())


if __name__ == "__main__":
    main()
