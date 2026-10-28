"""Generate report figures from the immutable three-year working database."""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from math import cos, pi, sin
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phases.phase1.code.calc_orbit_decay_diagnostics import (
    PhaseHarmonicSample,
    ordinary_least_squares,
    phase_harmonic_ols,
)
from phases.phase1.code.prep_11_phase_orbit_figures import (
    read_example_fit_orbit,
    reconstruct_phase_orbit,
)


MEAN_ORBIT_TABLE = "swarm_a_mean_orbit_elements_v1"
QUALITY_TABLE = "swarm_a_pod_quality"
CANDIDATE_TABLE = "swarm_a_phase_harmonic_decay_candidates_v1"
MICROSECONDS_PER_SECOND = 1_000_000
MICROSECONDS_PER_DAY = 86_400 * MICROSECONDS_PER_SECOND
WORKING_START = "2023-07-01"
WORKING_STOP = "2026-07-01"
EXAMPLE_DAY = "2025-06-01"
OLS_EXAMPLE_START = "2024-05-03T01:46:22Z"
OLS_EXAMPLE_STOP = "2024-05-03T06:28:22Z"
MAY_2024_START = "2024-05-01T00:00:00Z"
MAY_2024_STOP = "2024-06-01T00:00:00Z"
ORBIT_RAISE_DATABASE_PATH = (
    PROJECT_ROOT / "phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite"
)
ORBIT_RAISE_CONTEXT_START = "2023-04-01"
ORBIT_RAISE_CONTEXT_STOP = "2023-09-01"
ORBIT_RAISE_START = "2023-04-26"
ORBIT_RAISE_STOP = "2023-06-08"
FIGURE_DPI = 180
# MATLAB-style publication palette for the candidate series.
THREE_ORBIT_RAW_COLOR = "#0072BD"
FIVE_ORBIT_RAW_COLOR = "#D95319"
THREE_ORBIT_JOINT_COLOR = "#77AC30"
FIVE_ORBIT_JOINT_COLOR = "#4E8A18"


def open_read_only_database(database_path: Path) -> sqlite3.Connection:
    """Input: SQLite database path.
    Output: read-only SQLite connection."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    return sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)


def utc_time_bounds(day: str) -> tuple[int, int]:
    """Input: UTC date as YYYY-MM-DD.
    Output: [start, stop) Unix microseconds."""
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    stop = start + timedelta(days=1)
    return int(start.timestamp() * MICROSECONDS_PER_SECOND), int(
        stop.timestamp() * MICROSECONDS_PER_SECOND
    )


def iso_utc_to_us(value: str) -> int:
    """Input: UTC timestamp as YYYY-MM-DDTHH:MM:SSZ.
    Output: Unix microseconds."""
    timestamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    return int(timestamp.timestamp() * MICROSECONDS_PER_SECOND)


def utc_datetimes(time_us_values: list[int]) -> list[datetime]:
    """Input: Unix microseconds.
    Output: matching UTC datetime values."""
    return [
        datetime.fromtimestamp(value / MICROSECONDS_PER_SECOND, timezone.utc)
        for value in time_us_values
    ]


def configure_chinese_font() -> None:
    """Input: none.
    Output: Matplotlib uses a Windows Traditional-Chinese font when available."""
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False


def configure_time_axis(axis: plt.Axes) -> None:
    """Input: axis with UTC datetime values.
    Output: compact UTC date labels and a light grid."""
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axis.grid(alpha=0.22)


def read_daily_mean_rows(connection: sqlite3.Connection) -> list[tuple[int, float]]:
    """Input: working-database connection.
    Output: [(UTC day start, daily raw mean semi-major axis m), ...]."""
    start_time_us, stop_time_us = utc_time_bounds(WORKING_START)
    _, working_stop_time_us = utc_time_bounds(WORKING_STOP)
    return connection.execute(
        f"""
        SELECT (mean.time_us / ?) * ?, AVG(mean.mean_semi_major_axis_m)
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN {QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.time_us >= ?
          AND mean.time_us < ?
        GROUP BY (mean.time_us / ?) * ?
        ORDER BY mean.time_us
        """,
        (
            MICROSECONDS_PER_DAY,
            MICROSECONDS_PER_DAY,
            start_time_us,
            working_stop_time_us,
            MICROSECONDS_PER_DAY,
            MICROSECONDS_PER_DAY,
        ),
    ).fetchall()


def read_example_day_rows(connection: sqlite3.Connection) -> list[tuple[int, float, float, float]]:
    """Input: working-database connection.
    Output: [(time_us, raw mean semi-major axis m, omega rad, M rad), ...]."""
    start_time_us, stop_time_us = utc_time_bounds(EXAMPLE_DAY)
    return connection.execute(
        f"""
        SELECT mean.time_us, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN {QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
          AND mean.time_us >= ?
          AND mean.time_us < ?
        ORDER BY mean.time_us
        """,
        (start_time_us, stop_time_us),
    ).fetchall()


def read_orbit_raise_rows() -> list[tuple[int, float, int | None, int]]:
    """Input: full-mission source database and 2023 event dates.
    Output: [(UTC day, daily mean semi-major axis m, chunk_id, is_usable), ...]."""
    start_time_us, _ = utc_time_bounds(ORBIT_RAISE_CONTEXT_START)
    stop_time_us, _ = utc_time_bounds(ORBIT_RAISE_CONTEXT_STOP)
    with open_read_only_database(ORBIT_RAISE_DATABASE_PATH) as connection:
        return connection.execute(
        f"""
        SELECT (mean.time_us / ?) * ?, AVG(mean.mean_semi_major_axis_m),
               MIN(quality.chunk_id), MIN(quality.is_usable)
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN {QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.time_us >= ?
          AND mean.time_us < ?
        GROUP BY (mean.time_us / ?) * ?
        ORDER BY mean.time_us
        """,
        (
            MICROSECONDS_PER_DAY,
            MICROSECONDS_PER_DAY,
            start_time_us,
            stop_time_us,
            MICROSECONDS_PER_DAY,
            MICROSECONDS_PER_DAY,
        ),
    ).fetchall()


def read_ols_example_samples(
    connection: sqlite3.Connection,
) -> list[PhaseHarmonicSample]:
    """Input: working-database connection.
    Output: raw samples in one stored three-orbit candidate window."""
    start_time_us = iso_utc_to_us(OLS_EXAMPLE_START)
    stop_time_us = iso_utc_to_us(OLS_EXAMPLE_STOP)
    rows = connection.execute(
        f"""
        SELECT mean.time_us, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad,
               quality.chunk_id
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN {QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
          AND mean.time_us >= ?
          AND mean.time_us <= ?
        ORDER BY mean.time_us
        """,
        (start_time_us, stop_time_us),
    ).fetchall()
    return [
        PhaseHarmonicSample(
            time_us, semi_major_axis_m,
            (argument_of_perigee_rad + mean_anomaly_rad) % (2.0 * pi), chunk_id,
        )
        for time_us, semi_major_axis_m, argument_of_perigee_rad, mean_anomaly_rad, chunk_id in rows
    ]


def read_candidate_rate_rows(
    connection: sqlite3.Connection,
) -> dict[tuple[str, int], list[tuple[int, float]]]:
    """Input: working-database connection.
    Output: {(method, orbit count): [(time_us, rate m/day), ...], ...}."""
    rows = connection.execute(
        f"""
        SELECT decay_method, orbit_window, time_us, decay_rate_m_day
        FROM {CANDIDATE_TABLE}
        WHERE time_us >= ? AND time_us < ?
        ORDER BY decay_method, orbit_window, time_us
        """,
        (iso_utc_to_us(MAY_2024_START), iso_utc_to_us(MAY_2024_STOP)),
    ).fetchall()
    grouped_rows: dict[tuple[str, int], list[tuple[int, float]]] = {}
    for method, orbit_count, time_us, rate_m_day in rows:
        grouped_rows.setdefault((method, orbit_count), []).append((time_us, rate_m_day))
    return grouped_rows


def save_three_year_mean_figure(
    daily_rows: list[tuple[int, float]], output_path: Path,
) -> None:
    """Input: daily raw aggregates and PNG destination.
    Output: saved three-year mean semi-major-axis figure."""
    if not daily_rows:
        raise ValueError("Required three-year mean-element rows are missing.")
    daily_dates = utc_datetimes([row[0] for row in daily_rows])
    figure, axis = plt.subplots(figsize=(13, 4.5), constrained_layout=True)
    axis.plot(daily_dates, [row[1] for row in daily_rows], color="#1d4ed8", linewidth=0.8)
    axis.set_title("三年有效平均元素：每日平均 `mean_semi_major_axis_m`")
    axis.set_ylabel("每日平均半長軸（m）")
    axis.ticklabel_format(axis="y", style="plain", useOffset=True)
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_one_day_mean_figure(
    example_day_rows: list[tuple[int, float, float, float]], output_path: Path,
) -> None:
    """Input: one-day raw mean-element rows and PNG destination.
    Output: saved one-day raw semi-major-axis figure."""
    if not example_day_rows:
        raise ValueError("Required one-day mean-element rows are missing.")
    day_dates = utc_datetimes([row[0] for row in example_day_rows])
    figure, axis = plt.subplots(figsize=(13, 4.5), constrained_layout=True)
    axis.plot(day_dates, [row[1] for row in example_day_rows], color="#475569", linewidth=0.55)
    axis.set_title(f"{EXAMPLE_DAY} UTC：每 10 秒原始 `mean_semi_major_axis_m`（8,640 筆）")
    axis.set_ylabel("平均半長軸（m）")
    axis.ticklabel_format(axis="y", style="plain", useOffset=True)
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_phase_time_figure(
    example_day_rows: list[tuple[int, float, float, float]], output_path: Path,
) -> None:
    """Input: one-day raw mean-element rows and PNG destination.
    Output: saved one-day orbital-phase time series."""
    if not example_day_rows:
        raise ValueError("Required one-day phase rows are missing.")
    day_dates = utc_datetimes([row[0] for row in example_day_rows])
    wrapped_phase_rad = [(row[2] + row[3]) % (2.0 * pi) for row in example_day_rows]
    figure, axis = plt.subplots(figsize=(13, 4.5), constrained_layout=True)
    axis.plot(day_dates, wrapped_phase_rad, color="#c2410c", linewidth=0.55)
    axis.set_title("同日的軌道相位 `u = (omega + M) mod 2pi`")
    axis.set_ylabel("u（rad）")
    axis.set_yticks([0.0, pi, 2.0 * pi], ["0", "pi", "2pi"])
    axis.set_xlabel("UTC")
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_orbit_raise_chunk_figure(
    rows: list[tuple[int, float, int | None, int]], output_path: Path,
) -> None:
    """Input: daily full-mission event rows and PNG destination.
    Output: saved orbit-raise exclusion and chunk-boundary figure."""
    if not rows:
        raise ValueError("No daily rows are available around the orbit-raise campaign.")
    raise_start_time_us, _ = utc_time_bounds(ORBIT_RAISE_START)
    raise_stop_time_us, _ = utc_time_bounds(ORBIT_RAISE_STOP)
    pre_event_rows: list[tuple[int, float]] = []
    excluded_rows: list[tuple[int, float]] = []
    post_event_rows: list[tuple[int, float]] = []
    for time_us, semi_major_axis_m, _chunk_id, is_usable in rows:
        if time_us < raise_start_time_us:
            pre_event_rows.append((time_us, semi_major_axis_m))
        elif time_us >= raise_stop_time_us:
            post_event_rows.append((time_us, semi_major_axis_m))
        else:
            if not is_usable:
                excluded_rows.append((time_us, semi_major_axis_m))
    if not pre_event_rows or not excluded_rows or not post_event_rows:
        raise ValueError("Orbit-raise figure requires rows before, during, and after the campaign.")
    campaign_plot_rows = [pre_event_rows[-1], *excluded_rows]
    post_event_plot_rows = [excluded_rows[-1], *post_event_rows]
    figure, axis = plt.subplots(figsize=(13, 4.8), constrained_layout=True)
    axis.plot(
        utc_datetimes([row[0] for row in pre_event_rows]),
        [row[1] for row in pre_event_rows], color=THREE_ORBIT_RAW_COLOR,
        linewidth=1.6, label="chunk 10：事件前",
    )
    axis.plot(
        utc_datetimes([row[0] for row in post_event_plot_rows]),
        [row[1] for row in post_event_plot_rows], color=THREE_ORBIT_JOINT_COLOR,
        linewidth=1.6, label="chunk 11：事件後",
    )
    raise_start = datetime.strptime(ORBIT_RAISE_START, "%Y-%m-%d").replace(
        tzinfo=timezone.utc,
    )
    raise_stop = datetime.strptime(ORBIT_RAISE_STOP, "%Y-%m-%d").replace(
        tzinfo=timezone.utc,
    )
    axis.axvspan(raise_start, raise_stop, color=FIVE_ORBIT_RAW_COLOR, alpha=0.08)
    axis.axvline(
        raise_start, color="#404040", linewidth=1.25, linestyle="-",
        label="chunk 邊界：campaign 起訖",
    )
    axis.axvline(raise_stop, color="#404040", linewidth=1.25, linestyle="-")
    axis.plot(
        utc_datetimes([row[0] for row in campaign_plot_rows]),
        [row[1] for row in campaign_plot_rows], color=FIVE_ORBIT_RAW_COLOR,
        linewidth=1.6, label="campaign 內原始日平均：排除",
    )
    axis.set_xlim(
        datetime(2023, 4, 1, tzinfo=timezone.utc),
        datetime(2023, 9, 1, tzinfo=timezone.utc),
    )
    axis.set_title("官方軌道抬升事件：資料排除與 chunk 切分")
    axis.set_ylabel("每日平均半長軸（m）")
    axis.set_xlabel("UTC")
    axis.xaxis.set_major_locator(mdates.MonthLocator())
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    axis.ticklabel_format(axis="y", style="plain", useOffset=True)
    axis.grid(alpha=0.22)
    axis.legend(loc="lower right", frameon=True, framealpha=0.94)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_h2h3_reconstruction_figure(
    reconstructed_rows: list[tuple[float, float, float]], output_path: Path,
) -> None:
    """Input: [(phase rad, raw deviation m, H2/H3 fit m), ...] and PNG path.
    Output: saved H2/H3 reconstruction figure."""
    phase_rad = [row[0] for row in reconstructed_rows]
    raw_deviation_m = [row[1] for row in reconstructed_rows]
    fitted_deviation_m = [row[2] for row in reconstructed_rows]
    figure, axis = plt.subplots(figsize=(11, 4.5), constrained_layout=True)
    axis.scatter(phase_rad, raw_deviation_m, s=3, color="#64748b", label="原始偏差")
    axis.plot(phase_rad, fitted_deviation_m, color="#c2410c", label="H2/H3 諧波重建")
    axis.axhline(0.0, color="#0f172a", linewidth=0.8)
    axis.set_title("單一完整軌道：H2/H3 諧波重建")
    axis.set_xlabel("相對軌道相位（rad）")
    axis.set_ylabel("相對相位平均值的偏差（m）")
    axis.legend(loc="upper right")
    axis.grid(alpha=0.22)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_h2h3_residual_figure(
    reconstructed_rows: list[tuple[float, float, float]], output_path: Path,
) -> None:
    """Input: [(phase rad, raw deviation m, H2/H3 fit m), ...] and PNG path.
    Output: saved post-H2/H3 residual figure."""
    phase_rad = [row[0] for row in reconstructed_rows]
    residual_m = [row[1] - row[2] for row in reconstructed_rows]
    figure, axis = plt.subplots(figsize=(11, 4.5), constrained_layout=True)
    axis.scatter(phase_rad, residual_m, s=3, color="#15803d")
    axis.axhline(0.0, color="#0f172a", linewidth=0.8)
    axis.set_title("單一完整軌道：扣除 H2/H3 後的殘差")
    axis.set_xlabel("相對軌道相位（rad）")
    axis.set_ylabel("殘差（m）")
    axis.grid(alpha=0.22)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_candidate_pair_figure(
    candidate_rows: dict[tuple[str, int], list[tuple[int, float]]],
    figure_details: tuple[str, str, str, str], output_path: Path,
) -> None:
    """Input: candidate time series, (title, method, 3/5 colors), and PNG path.
    Output: one saved two-series 3/5-orbit model comparison."""
    title, method, three_orbit_color, five_orbit_color = figure_details
    figure, axis = plt.subplots(figsize=(13, 4.8), constrained_layout=True)
    for orbit_count, color in ((3, three_orbit_color), (5, five_orbit_color)):
        rows = candidate_rows[(method, orbit_count)]
        axis.plot(
            utc_datetimes([row[0] for row in rows]), [row[1] for row in rows],
            color=color, linewidth=1.2, label=f"{orbit_count} 圈",
        )
    all_rates = [rate for rows in candidate_rows.values() for _, rate in rows]
    rate_range = max(all_rates) - min(all_rates)
    axis.set_ylim(min(all_rates) - 0.05 * rate_range,
                  max(all_rates) + 0.05 * rate_range)
    axis.axhline(0.0, color="#0f172a", linewidth=0.8)
    axis.set_title(title)
    axis.set_ylabel("衰減率候選（m/day）")
    axis.set_xlabel("UTC")
    axis.legend(loc="lower left", ncol=2, frameon=True, framealpha=0.94)
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def trend_line_values(
    samples: list[PhaseHarmonicSample], values_m: list[float], rate_m_day: float,
) -> list[float]:
    """Input: samples, fitted values, and OLS rate in m/day.
    Output: matching OLS line values in m."""
    relative_days = [
        (sample.time_us - samples[0].time_us) / MICROSECONDS_PER_DAY
        for sample in samples
    ]
    mean_relative_day = sum(relative_days) / len(relative_days)
    mean_value_m = sum(values_m) / len(values_m)
    return [
        mean_value_m + rate_m_day * (relative_day - mean_relative_day)
        for relative_day in relative_days
    ]


def calculate_ols_example_values(
    samples: list[PhaseHarmonicSample],
) -> tuple[list[float], list[float], float, float]:
    """Input: one complete three-orbit sample window.
    Output: raw values, H2/H3-corrected values, raw rate, and joint rate."""
    if len(samples) < 7:
        raise ValueError("The three-orbit example has too few samples.")
    raw_values_m = [sample.semi_major_axis_m for sample in samples]
    raw_fit = ordinary_least_squares([
        (sample.time_us, sample.semi_major_axis_m) for sample in samples
    ])
    joint_fit = phase_harmonic_ols(samples, (2, 3))
    harmonic_correction_m = [
        sum(
            cosine_m * cos(order * sample.phase_rad)
            + sine_m * sin(order * sample.phase_rad)
            for order, cosine_m, sine_m in joint_fit.harmonic_coefficients_m
        )
        for sample in samples
    ]
    corrected_values_m = [
        value_m - correction_m
        for value_m, correction_m in zip(raw_values_m, harmonic_correction_m)
    ]
    return (
        raw_values_m,
        corrected_values_m,
        raw_fit["rate_m_day"],
        joint_fit.rate_m_day,
    )


def save_raw_ols_example_figure(
    samples: list[PhaseHarmonicSample], output_path: Path,
) -> None:
    """Input: one complete three-orbit sample window and PNG destination.
    Output: saved raw mean-element OLS figure."""
    raw_values_m, _, raw_rate_m_day, _ = calculate_ols_example_values(samples)
    dates = utc_datetimes([sample.time_us for sample in samples])
    raw_line_m = trend_line_values(samples, raw_values_m, raw_rate_m_day)
    figure, axis = plt.subplots(figsize=(13, 4.5), constrained_layout=True)
    axis.plot(dates, raw_values_m, color=THREE_ORBIT_RAW_COLOR, linewidth=0.6, label="原始平均半長軸")
    axis.plot(
        dates, raw_line_m, color=THREE_ORBIT_RAW_COLOR, linewidth=2.0,
        label=f"原始 OLS 斜率：{raw_rate_m_day:.1f} m/day",
    )
    axis.set_title("三圈視窗：原始平均半長軸與原始 OLS")
    axis.set_ylabel("半長軸（m）")
    axis.ticklabel_format(axis="y", style="plain", useOffset=True)
    axis.legend(loc="upper right")
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_corrected_ols_example_figure(
    samples: list[PhaseHarmonicSample], output_path: Path,
) -> None:
    """Input: one complete three-orbit sample window and PNG destination.
    Output: saved H2/H3-corrected OLS figure."""
    _, corrected_values_m, _, joint_rate_m_day = calculate_ols_example_values(samples)
    dates = utc_datetimes([sample.time_us for sample in samples])
    corrected_line_m = trend_line_values(samples, corrected_values_m, joint_rate_m_day)
    figure, axis = plt.subplots(figsize=(13, 4.5), constrained_layout=True)
    axis.plot(dates, corrected_values_m, color=THREE_ORBIT_JOINT_COLOR, linewidth=0.6, label="扣除 H2/H3 後的平均半長軸")
    axis.plot(
        dates, corrected_line_m, color=THREE_ORBIT_JOINT_COLOR, linewidth=2.0,
        label=f"H2/H3 聯合 OLS 斜率：{joint_rate_m_day:.1f} m/day",
    )
    axis.set_title("三圈視窗：扣除 H2/H3 後與聯合 OLS")
    axis.set_ylabel("半長軸（m）")
    axis.set_xlabel("UTC")
    axis.ticklabel_format(axis="y", style="plain", useOffset=True)
    axis.legend(loc="upper right")
    configure_time_axis(axis)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def generate_figures(database_path: Path, output_directory: Path) -> None:
    """Input: immutable SQLite path and output image directory.
    Output: report PNG files written from actual working-database rows."""
    output_directory.mkdir(parents=True, exist_ok=True)
    configure_chinese_font()
    with open_read_only_database(database_path) as connection:
        daily_rows = read_daily_mean_rows(connection)
        example_day_rows = read_example_day_rows(connection)
        ols_example_samples = read_ols_example_samples(connection)
        reconstruction_rows = reconstruct_phase_orbit(read_example_fit_orbit(connection))
        candidate_rate_rows = read_candidate_rate_rows(connection)
    save_three_year_mean_figure(
        daily_rows, output_directory / "report-02a-three-year-mean-semi-major-axis.png",
    )
    save_one_day_mean_figure(
        example_day_rows, output_directory / "report-02b-one-day-raw-mean-semi-major-axis.png",
    )
    save_phase_time_figure(
        example_day_rows, output_directory / "report-02c-one-day-orbit-phase.png",
    )
    save_orbit_raise_chunk_figure(
        read_orbit_raise_rows(), output_directory / "report-03-orbit-raise-chunk-boundary.png",
    )
    save_h2h3_reconstruction_figure(
        reconstruction_rows, output_directory / "report-04a-h2-h3-harmonic-reconstruction.png",
    )
    save_h2h3_residual_figure(
        reconstruction_rows, output_directory / "report-04b-h2-h3-residual.png",
    )
    historical_directory = output_directory / "test"
    historical_directory.mkdir(parents=True, exist_ok=True)
    save_raw_ols_example_figure(
        ols_example_samples, historical_directory / "report-05a-raw-ols-three-orbit-example.png",
    )
    save_corrected_ols_example_figure(
        ols_example_samples, historical_directory / "report-05b-h2-h3-corrected-ols-three-orbit-example.png",
    )
    comparison_figures = (
        (("2024 年 5 月：原始模型（無 H2/H3）", "raw_b_l_local_ols",
          THREE_ORBIT_RAW_COLOR, FIVE_ORBIT_RAW_COLOR),
         "report-06a-may-2024-without-h2-h3.png"),
        (("2024 年 5 月：H2/H3 聯合模型", "joint_h2_h3_local_ols",
          THREE_ORBIT_RAW_COLOR, FIVE_ORBIT_RAW_COLOR),
         "report-06b-may-2024-with-h2-h3.png"),
    )
    for details, filename in comparison_figures:
        save_candidate_pair_figure(candidate_rate_rows, details, historical_directory / filename)


def main() -> None:
    """Input: database path and output image directory from command line.
    Output: report figures generated or an actionable usage error."""
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python -m phases.phase1.code.prep_report_figures DATABASE_PATH OUTPUT_DIRECTORY"
        )
    generate_figures(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
