"""Render P1.5.5 phase-harmonic and P1.5.6 decay-candidate figures."""

import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import cos, sin
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from phases.phase0.code.data.database.prep_raw_schema import connect_database
from phases.phase1.code.prep_10_phase_orbit_mean import TWO_PI, unwrapped_phase


DEFAULT_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
)
DEFAULT_OUTPUT_DIRECTORY = Path("images")
MONTHLY_COMPARISON_MONTH = "2025-06"
DECAY_RATE_MONTH = "2025-06"
DECAY_RATE_DAY = "2025-06-15"
PHASE_ORBIT_TABLE = "swarm_a_phase_orbit_mean_v2"
MEAN_ORBIT_TABLE = "swarm_a_mean_orbit_elements_v1"
POD_QUALITY_TABLE = "swarm_a_pod_quality"
TRAILING_DECAY_TABLE = "swarm_a_phase_harmonic_decay_trailing_1h_v1"
MICROSECONDS_PER_SECOND = 1_000_000
FIGURE_DPI = 180
HARMONIC_MARKER_SIZE = 3
MONTHLY_MARKER_SIZE = 1


@dataclass(frozen=True)
class FourierFitOrbit:
    """Input: one stored phase orbit and its usable B-L mean-element rows
    Output: data required to show its H2/H3 reconstruction"""

    time_us: int
    phase_weighted_mean_a_m: float
    h2_cosine_m: float
    h2_sine_m: float
    h3_cosine_m: float
    h3_sine_m: float
    source_rows: list[tuple[int, float, float, float]]


def require_phase_tables(connection: sqlite3.Connection) -> None:
    """Input: SQLite connection
    Output: required P1.5 phase tables are confirmed present"""
    table_names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    required_tables = {
        PHASE_ORBIT_TABLE,
        MEAN_ORBIT_TABLE,
        POD_QUALITY_TABLE,
        TRAILING_DECAY_TABLE,
    }
    missing_tables = required_tables - table_names
    if missing_tables:
        raise ValueError(f"Missing phase tables: {', '.join(sorted(missing_tables))}")


def read_harmonic_rows(connection: sqlite3.Connection) -> list[tuple[int, float, float]]:
    """Input: SQLite connection with P1.5.4 rows
    Output: [(time_us, H2 amplitude m, H3 amplitude m), ...]"""
    return connection.execute(f"""
        SELECT time_us, h2_amplitude_m, h3_amplitude_m
        FROM {PHASE_ORBIT_TABLE}
        ORDER BY time_us
    """).fetchall()


def read_phase_orbit_mean_rows(connection: sqlite3.Connection) -> list[tuple[int, float]]:
    """Input: SQLite connection with P1.5.4 rows
    Output: [(orbit endpoint time_us, phase-weighted mean a m), ...]"""
    return connection.execute(f"""
        SELECT time_us, phase_weighted_mean_semi_major_axis_m
        FROM {PHASE_ORBIT_TABLE}
        ORDER BY time_us
    """).fetchall()


def read_trailing_decay_rows(
    connection: sqlite3.Connection,
) -> list[tuple[int, float, float]]:
    """Input: SQLite connection with P1.5.6 rows
    Output: [(time_us, rate m/day, 1-sigma m/day)]"""
    return connection.execute(f"""
        SELECT time_us, decay_rate_m_day, decay_rate_1sigma_m_day
        FROM {TRAILING_DECAY_TABLE}
        ORDER BY time_us
    """).fetchall()


def read_example_fit_orbit(connection: sqlite3.Connection) -> FourierFitOrbit:
    """Input: SQLite connection with P1.5.4 source and output tables
    Output: middle valid phase orbit with its source samples"""
    orbit_count = connection.execute(
        f"SELECT COUNT(*) FROM {PHASE_ORBIT_TABLE}"
    ).fetchone()[0]
    selected_row = connection.execute(f"""
        SELECT time_us, orbit_start_time_us, phase_weighted_mean_semi_major_axis_m,
               h2_cosine_m, h2_sine_m, h3_cosine_m, h3_sine_m, chunk_id
        FROM {PHASE_ORBIT_TABLE}
        ORDER BY time_us
        LIMIT 1 OFFSET ?
    """, (orbit_count // 2,)).fetchone()
    if selected_row is None:
        raise ValueError("No phase orbit is available for the Fourier-fit figure.")
    time_us, start_time_us, mean_a_m, h2_cosine_m, h2_sine_m, h3_cosine_m, h3_sine_m, chunk_id = selected_row
    source_rows = connection.execute(f"""
        SELECT mean.time_us, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN {POD_QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1
          AND quality.chunk_id = ?
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
          AND mean.time_us >= ?
          AND mean.time_us <= ?
        ORDER BY mean.time_us
    """, (chunk_id, start_time_us, time_us)).fetchall()
    return FourierFitOrbit(
        time_us,
        mean_a_m,
        h2_cosine_m,
        h2_sine_m,
        h3_cosine_m,
        h3_sine_m,
        source_rows,
    )


def utc_datetimes(rows: list[tuple[int, ...]]) -> list[datetime]:
    """Input: rows whose first field is UTC Unix microseconds
    Output: matching UTC datetimes"""
    return [
        datetime.fromtimestamp(row[0] / MICROSECONDS_PER_SECOND, timezone.utc)
        for row in rows
    ]


def reconstruct_phase_orbit(
    orbit: FourierFitOrbit,
) -> list[tuple[float, float, float]]:
    """Input: one phase orbit with H2/H3 coefficients
    Output: [(relative phase rad, raw deviation m, H2/H3 fit m), ...]"""
    reconstructed_rows = []
    previous_raw_phase_rad = None
    previous_phase_rad = None
    first_phase_rad = None
    for _, semi_major_axis_m, omega_rad, mean_anomaly_rad in orbit.source_rows:
        raw_phase_rad = (omega_rad + mean_anomaly_rad) % TWO_PI
        phase_rad = unwrapped_phase(
            raw_phase_rad, previous_raw_phase_rad, previous_phase_rad,
        )
        if first_phase_rad is None:
            first_phase_rad = phase_rad
        fitted_deviation_m = phase_fit_deviation_m(
            (
                orbit.h2_cosine_m,
                orbit.h2_sine_m,
                orbit.h3_cosine_m,
                orbit.h3_sine_m,
            ),
            phase_rad,
        )
        reconstructed_rows.append((
            phase_rad - first_phase_rad,
            semi_major_axis_m - orbit.phase_weighted_mean_a_m,
            fitted_deviation_m,
        ))
        previous_raw_phase_rad = raw_phase_rad
        previous_phase_rad = phase_rad
    return reconstructed_rows


def phase_fit_deviation_m(
    harmonic_coefficients_m: tuple[float, float, float, float],
    phase_rad: float,
) -> float:
    """Input: (H2 cosine, H2 sine, H3 cosine, H3 sine) in m and phase in rad.
    Output: fitted H2/H3 deviation in m."""
    h2_cosine_m, h2_sine_m, h3_cosine_m, h3_sine_m = harmonic_coefficients_m
    return (
        h2_cosine_m * cos(2.0 * phase_rad)
        + h2_sine_m * sin(2.0 * phase_rad)
        + h3_cosine_m * cos(3.0 * phase_rad)
        + h3_sine_m * sin(3.0 * phase_rad)
    )


def month_time_bounds(month: str) -> tuple[int, int]:
    """Input: UTC calendar month as YYYY-MM.
    Output: [month start, next month start) in Unix microseconds."""
    month_start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    next_month = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )
    return (
        int(month_start.timestamp() * MICROSECONDS_PER_SECOND),
        int(next_month.timestamp() * MICROSECONDS_PER_SECOND),
    )


def day_time_bounds(day: str) -> tuple[int, int]:
    """Input: UTC calendar day as YYYY-MM-DD
    Output: [day start, next day start) in Unix microseconds"""
    day_start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    next_day = day_start + timedelta(days=1)
    return (
        int(day_start.timestamp() * MICROSECONDS_PER_SECOND),
        int(next_day.timestamp() * MICROSECONDS_PER_SECOND),
    )


def read_monthly_fit_rows(
    connection: sqlite3.Connection, month: str,
) -> list[tuple[int, float, float, float, float, float, float, float, float]]:
    """Input: SQLite connection and UTC calendar month.
    Output: raw mean-a rows with their containing orbit H2/H3 fit."""
    start_time_us, stop_time_us = month_time_bounds(month)
    orbit_rows = connection.execute(f"""
        SELECT orbit_start_time_us, time_us, chunk_id,
               phase_weighted_mean_semi_major_axis_m,
               h2_cosine_m, h2_sine_m, h3_cosine_m, h3_sine_m
        FROM {PHASE_ORBIT_TABLE}
        WHERE time_us >= ? AND time_us < ?
        ORDER BY time_us
    """, (start_time_us, stop_time_us)).fetchall()
    if not orbit_rows:
        return []
    source_rows = connection.execute(f"""
        SELECT mean.time_us, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad,
               quality.chunk_id
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN {POD_QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE mean.time_us >= ? AND mean.time_us <= ?
          AND quality.is_usable = 1
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
        ORDER BY mean.time_us
    """, (orbit_rows[0][0], orbit_rows[-1][1])).fetchall()
    result_rows = []
    orbit_index = 0
    for time_us, semi_major_axis_m, omega_rad, mean_anomaly_rad, chunk_id in source_rows:
        while orbit_index < len(orbit_rows) and time_us > orbit_rows[orbit_index][1]:
            orbit_index += 1
        if orbit_index == len(orbit_rows):
            break
        orbit_start_time_us, _, orbit_chunk_id, mean_a_m, *coefficients_m = orbit_rows[orbit_index]
        if time_us >= orbit_start_time_us and chunk_id == orbit_chunk_id:
            result_rows.append((
                time_us, semi_major_axis_m, mean_a_m, *coefficients_m,
                omega_rad, mean_anomaly_rad,
            ))
    return result_rows


def configure_time_axis(axis: plt.Axes) -> None:
    """Input: Matplotlib axis with UTC dates
    Output: concise UTC date labels on the axis"""
    locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axis.grid(alpha=0.25)


def save_harmonic_figure(
    harmonic_rows: list[tuple[int, float, float]], output_path: Path,
) -> None:
    """Input: P1.5.5 harmonic rows and PNG destination
    Output: saved H2/H3 amplitude figure"""
    if not harmonic_rows:
        raise ValueError("No phase-harmonic rows are available for plotting.")
    dates = utc_datetimes(harmonic_rows)
    h2_amplitudes_m = [row[1] for row in harmonic_rows]
    h3_amplitudes_m = [row[2] for row in harmonic_rows]
    figure, axis = plt.subplots(figsize=(12, 4), constrained_layout=True)
    axis.scatter(dates, h2_amplitudes_m, s=HARMONIC_MARKER_SIZE, label="H2 amplitude")
    axis.scatter(dates, h3_amplitudes_m, s=HARMONIC_MARKER_SIZE, label="H3 amplitude")
    axis.set_title("P1.5.5 phase-harmonic diagnostic (working candidate)")
    axis.set_ylabel("Fourier amplitude (m)")
    axis.legend(loc="upper right")
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_phase_mean_figure(
    phase_mean_rows: list[tuple[int, float]], output_path: Path,
) -> None:
    """Input: P1.5.4 phase-weighted mean rows and PNG destination
    Output: saved complete-orbit mean time-series figure"""
    if not phase_mean_rows:
        raise ValueError("No phase-orbit mean rows are available for plotting.")
    figure, axis = plt.subplots(figsize=(12, 4), constrained_layout=True)
    axis.scatter(
        utc_datetimes(phase_mean_rows),
        [row[1] for row in phase_mean_rows],
        s=HARMONIC_MARKER_SIZE,
    )
    axis.set_title("P1.5.4 phase-weighted complete-orbit mean (working candidate)")
    axis.set_ylabel("Mean semi-major axis (m)")
    axis.ticklabel_format(axis="y", style="plain", useOffset=True)
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_fourier_fit_figure(orbit: FourierFitOrbit, output_path: Path) -> None:
    """Input: one stored phase orbit and PNG destination
    Output: saved raw-versus-H2/H3 reconstruction figure"""
    reconstructed_rows = reconstruct_phase_orbit(orbit)
    if not reconstructed_rows:
        raise ValueError("No source samples are available for the Fourier-fit figure.")
    phase_rad = [row[0] for row in reconstructed_rows]
    raw_deviation_m = [row[1] for row in reconstructed_rows]
    fitted_deviation_m = [row[2] for row in reconstructed_rows]
    residual_m = [raw_value_m - fitted_value_m for raw_value_m, fitted_value_m in zip(raw_deviation_m, fitted_deviation_m)]
    orbit_end_utc = datetime.fromtimestamp(
        orbit.time_us / MICROSECONDS_PER_SECOND, timezone.utc,
    ).strftime("%Y-%m-%d %H:%M UTC")
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    axes[0].scatter(phase_rad, raw_deviation_m, s=HARMONIC_MARKER_SIZE, label="raw B-L mean a - phase mean")
    axes[0].plot(phase_rad, fitted_deviation_m, color="tab:orange", label="H2/H3 Fourier reconstruction")
    axes[0].axhline(0.0, color="black", linewidth=1, label="stored phase-weighted mean")
    axes[0].set_ylabel("Deviation from phase mean (m)")
    axes[0].set_title(f"P1.5.4 representative orbit ending {orbit_end_utc}")
    axes[0].legend(loc="upper right")
    axes[0].grid(alpha=0.25)
    axes[1].scatter(phase_rad, residual_m, s=HARMONIC_MARKER_SIZE)
    axes[1].axhline(0.0, color="black", linewidth=1)
    axes[1].set_xlabel("Relative phase u (rad)")
    axes[1].set_ylabel("Raw - H2/H3 fit (m)")
    axes[1].grid(alpha=0.25)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_monthly_fit_comparison(
    rows: list[tuple[int, float, float, float, float, float, float, float, float]],
    month: str,
    output_path: Path,
) -> None:
    """Input: monthly raw rows, H2/H3 fits, month label, and PNG path.
    Output: saved raw-versus-residual comparison for one month."""
    if not rows:
        raise ValueError(f"No phase-fit rows are available for {month}.")
    dates = utc_datetimes(rows)
    raw_a_m = [row[1] for row in rows]
    baseline_a_m = [row[2] for row in rows]
    fitted_deviation_m = [
        phase_fit_deviation_m(row[3:7], (row[7] + row[8]) % TWO_PI)
        for row in rows
    ]
    residual_a_m = [
        raw_value_m - fitted_value_m
        for raw_value_m, fitted_value_m in zip(raw_a_m, fitted_deviation_m)
    ]
    figure, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, constrained_layout=True)
    axes[0].scatter(dates, raw_a_m, s=MONTHLY_MARKER_SIZE, alpha=0.35, label="raw B-L mean a")
    axes[0].plot(dates, baseline_a_m, color="black", linewidth=0.6, label="stored orbit mean")
    axes[0].set_ylabel("Semi-major axis (m)")
    axes[0].set_title(f"{month}: before H2/H3 subtraction")
    axes[0].legend(loc="upper right")
    axes[1].scatter(dates, residual_a_m, s=MONTHLY_MARKER_SIZE, alpha=0.35, color="tab:green", label="raw a - H2/H3 fit")
    axes[1].plot(dates, baseline_a_m, color="black", linewidth=0.6, label="stored orbit mean")
    axes[1].set_ylabel("Semi-major axis (m)")
    axes[1].set_title(f"{month}: after H2/H3 subtraction")
    axes[1].legend(loc="upper right")
    axes[2].scatter(dates, fitted_deviation_m, s=MONTHLY_MARKER_SIZE, alpha=0.35, color="tab:orange")
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set_ylabel("Removed H2/H3 (m)")
    axes[2].set_title("Fitted intra-orbit component removed from raw a")
    axes[2].set_xlabel("UTC")
    for axis in axes:
        configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def trailing_decay_limits(rows: list[tuple[int, float, float]]) -> tuple[float, float]:
    """Input: P1.5.6 trailing slope rows
    Output: y-axis limits in m/day"""
    if not rows:
        raise ValueError("No P1.5.6 trailing decay rows are available for plotting.")
    minimum_rate_m_day = min(row[1] for row in rows)
    maximum_rate_m_day = max(row[1] for row in rows)
    margin_m_day = max((maximum_rate_m_day - minimum_rate_m_day) * 0.05, 1.0)
    return minimum_rate_m_day - margin_m_day, maximum_rate_m_day + margin_m_day


def time_window_rows(
    rows: list[tuple[int, float, float]], start_time_us: int, stop_time_us: int,
) -> list[tuple[int, float, float]]:
    """Input: ordered decay rows and UTC [start, stop) bounds
    Output: decay rows inside the requested time window"""
    return [
        row for row in rows
        if start_time_us <= row[0] < stop_time_us
    ]


def save_decay_figure(
    rows: list[tuple[int, float, float]], output_path: Path,
) -> None:
    """Input: P1.5.6 trailing slopes and PNG destination
    Output: saved one-hour trailing decay figure"""
    y_limits_m_day = trailing_decay_limits(rows)
    figure, axis = plt.subplots(figsize=(12, 4), constrained_layout=True)
    axis.plot(
        utc_datetimes(rows),
        [row[1] for row in rows],
        linewidth=0.6,
        alpha=0.75,
        label="1 h trailing H2/H3 local OLS",
    )
    axis.set_title("P1.5.6 trailing 1-hour decay rate (working; unfiltered)")
    axis.set_ylabel("Decay rate (m/day)")
    axis.set_ylim(*y_limits_m_day)
    axis.legend(loc="lower left")
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_trailing_decay_figure(
    database_path: Path = DEFAULT_DATABASE,
    output_path: Path = Path("images/phase-harmonic-decay-trailing-1h.png"),
) -> Path:
    """Input: SQLite path and PNG destination
    Output: saved P1.5.6 trailing-decay figure path"""
    connection = connect_database(database_path)
    try:
        table_exists = connection.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = ?
        """, (TRAILING_DECAY_TABLE,)).fetchone()
        if table_exists is None:
            raise ValueError(f"Missing phase table: {TRAILING_DECAY_TABLE}")
        rows = read_trailing_decay_rows(connection)
    finally:
        connection.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_decay_figure(rows, output_path)
    return output_path


def save_trailing_decay_scale_figures(
    database_path: Path = DEFAULT_DATABASE,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
) -> dict[str, Path]:
    """Input: SQLite path and output directory
    Output: {three_year_png, month_png, day_png} for one decay-rate method"""
    connection = connect_database(database_path)
    try:
        rows = read_trailing_decay_rows(connection)
    finally:
        connection.close()
    output_directory.mkdir(parents=True, exist_ok=True)
    month_start_time_us, month_stop_time_us = month_time_bounds(DECAY_RATE_MONTH)
    day_start_time_us, day_stop_time_us = day_time_bounds(DECAY_RATE_DAY)
    figure_paths = {
        "three_year_png": output_directory / "decay-rate-trailing-1h-2023-2026.png",
        "month_png": output_directory / f"decay-rate-trailing-1h-{DECAY_RATE_MONTH}.png",
        "day_png": output_directory / f"decay-rate-trailing-1h-{DECAY_RATE_DAY}.png",
    }
    save_decay_figure(rows, figure_paths["three_year_png"])
    save_decay_figure(
        time_window_rows(rows, month_start_time_us, month_stop_time_us),
        figure_paths["month_png"],
    )
    save_decay_figure(
        time_window_rows(rows, day_start_time_us, day_stop_time_us),
        figure_paths["day_png"],
    )
    return figure_paths


def save_phase_orbit_figures(
    database_path: Path = DEFAULT_DATABASE,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
) -> dict[str, Path]:
    """Input: P1.5.4--P1.5.6 SQLite path and output directory
    Output: {harmonics_png, phase_mean_png, fourier_fit_png, monthly_fit_png, decay_png}"""
    if not database_path.exists():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    output_directory.mkdir(parents=True, exist_ok=True)
    connection = connect_database(database_path)
    try:
        require_phase_tables(connection)
        harmonic_rows = read_harmonic_rows(connection)
        phase_mean_rows = read_phase_orbit_mean_rows(connection)
        trailing_decay_rows = read_trailing_decay_rows(connection)
        example_fit_orbit = read_example_fit_orbit(connection)
        monthly_fit_rows = read_monthly_fit_rows(connection, MONTHLY_COMPARISON_MONTH)
    finally:
        connection.close()
    harmonic_path = output_directory / "phase-orbit-harmonics-2023-2026.png"
    phase_mean_path = output_directory / "phase-orbit-mean-2023-2026.png"
    fourier_fit_path = output_directory / "phase-orbit-fourier-fit-example.png"
    monthly_fit_path = output_directory / (
        f"phase-orbit-fit-comparison-{MONTHLY_COMPARISON_MONTH}.png"
    )
    decay_path = output_directory / "phase-orbit-decay-candidates-2023-2026.png"
    save_harmonic_figure(harmonic_rows, harmonic_path)
    save_phase_mean_figure(phase_mean_rows, phase_mean_path)
    save_fourier_fit_figure(example_fit_orbit, fourier_fit_path)
    save_monthly_fit_comparison(
        monthly_fit_rows, MONTHLY_COMPARISON_MONTH, monthly_fit_path,
    )
    save_decay_figure(trailing_decay_rows, decay_path)
    return {
        "harmonics_png": harmonic_path,
        "phase_mean_png": phase_mean_path,
        "fourier_fit_png": fourier_fit_path,
        "monthly_fit_png": monthly_fit_path,
        "decay_png": decay_path,
    }


def main() -> None:
    """Input: python -m ...prep_11_phase_orbit_figures [DATABASE] [OUTPUT_DIR]
    Output: paths of saved P1.5 phase-orbit PNG figures"""
    arguments = sys.argv[1:]
    if len(arguments) > 2:
        raise ValueError("Usage: [DATABASE] [OUTPUT_DIR]")
    database_path = Path(arguments[0]) if arguments else DEFAULT_DATABASE
    output_directory = Path(arguments[1]) if len(arguments) == 2 else DEFAULT_OUTPUT_DIRECTORY
    figure_paths = save_phase_orbit_figures(database_path, output_directory)
    for figure_path in figure_paths.values():
        print(figure_path)


if __name__ == "__main__":
    main()
