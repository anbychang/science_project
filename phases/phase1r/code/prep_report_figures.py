"""Draw twelve-year orbit report figures from the read-only working database."""

import sqlite3
from datetime import datetime, timezone
from math import cos, sin
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from phases.phase1.code.prep_phase1_v2_report_figures import hourly_candidates


DATABASE_PATH = Path("phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite")
IMAGE_DIRECTORY = Path("phases/phase1r/figures")
MEAN_TABLE = "swarm_a_mean_orbit_elements_v1"
RAW_TABLE = "swarm_a_phase_harmonic_decay_raw_b_l_sets_v2"
JOINT_TABLE = "swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2"
MICROSECONDS_PER_DAY = 86_400_000_000
SECONDS_PER_DAY = 86_400
REPORT_START_TIME_US = int(datetime(2014, 7, 1, tzinfo=timezone.utc).timestamp() * 1_000_000)
REPORT_STOP_TIME_US = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1_000_000)
HARMONIC_EXAMPLE_US = int(datetime(2018, 1, 15, tzinfo=timezone.utc).timestamp() * 1_000_000)
STORM_START_US = int(datetime(2024, 5, 9, tzinfo=timezone.utc).timestamp() * 1_000_000)
STORM_STOP_US = int(datetime(2024, 5, 13, tzinfo=timezone.utc).timestamp() * 1_000_000)
DAY_START_US = 1_714_694_400_000_000
DAY_STOP_US = DAY_START_US + MICROSECONDS_PER_DAY
THREE_ORBIT_COLOR = "#0072BD"
FIVE_ORBIT_COLOR = "#D95319"
FIGURE_DPI = 180


def utc_datetime(time_us: int) -> datetime:
    """Input: Unix microseconds. Output: timezone-aware UTC datetime."""
    return datetime.fromtimestamp(time_us / 1_000_000, timezone.utc)


def read_daily_mean_rows(connection: sqlite3.Connection) -> list[tuple[int, float]]:
    """Input: read-only working database. Output: [(UTC day, mean a in m), ...]."""
    cursor = connection.execute(f"""
        SELECT time_us, mean_semi_major_axis_m
        FROM {MEAN_TABLE}
        WHERE time_us >= ?
          AND rejection_reason IS NULL
          AND mean_semi_major_axis_m IS NOT NULL
        ORDER BY time_us
    """, (REPORT_START_TIME_US,))
    daily_rows = []
    current_day = None
    daily_total_m = 0.0
    daily_count = 0
    for time_us, semi_major_axis_m in cursor:
        day = time_us // MICROSECONDS_PER_DAY
        if current_day is not None and day != current_day:
            daily_rows.append((current_day * MICROSECONDS_PER_DAY,
                               daily_total_m / daily_count))
            daily_total_m = 0.0
            daily_count = 0
        current_day = day
        daily_total_m += semi_major_axis_m
        daily_count += 1
    if current_day is not None:
        daily_rows.append((current_day * MICROSECONDS_PER_DAY,
                           daily_total_m / daily_count))
    return daily_rows


def read_candidate_day_rows(
    connection: sqlite3.Connection, table_name: str,
) -> dict[int, list[tuple[datetime, float]]]:
    """Input: database and one known v2 table. Output: {3/5: [(UTC, m/day), ...]}."""
    rows = {3: [], 5: []}
    for time_us, three_rate_m_s, five_rate_m_s in connection.execute(f"""
        SELECT time_us, orbit_3_decay_rate_m_s, orbit_5_decay_rate_m_s
        FROM {table_name}
        WHERE time_us >= ? AND time_us < ?
        ORDER BY time_us
    """, (DAY_START_US, DAY_STOP_US)):
        time_utc = utc_datetime(time_us)
        if three_rate_m_s is not None:
            rows[3].append((time_utc, three_rate_m_s * SECONDS_PER_DAY))
        if five_rate_m_s is not None:
            rows[5].append((time_utc, five_rate_m_s * SECONDS_PER_DAY))
    return rows


def save_daily_mean_figure(
    daily_rows: list[tuple[int, float]], output_path: Path,
) -> None:
    """Input: daily mean rows and PNG path. Output: long-span mean-element plot."""
    if not daily_rows:
        raise ValueError("No twelve-year mean-element rows were found.")
    dates = [utc_datetime(time_us) for time_us, _ in daily_rows]
    values_m = [value_m for _, value_m in daily_rows]
    figure, axis = plt.subplots(figsize=(13, 4.8), constrained_layout=True)
    axis.plot(dates, values_m, color=THREE_ORBIT_COLOR, linewidth=0.85)
    axis.set_title("2014-07–2026-06 平均半長軸：每日平均")
    axis.set_ylabel("平均半長軸（m）")
    axis.set_xlabel("UTC 年份")
    axis.set_xlim(dates[0], dates[-1])
    axis.ticklabel_format(axis="y", style="plain", useOffset=False)
    axis.grid(alpha=0.22)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_candidate_pair_figure(
    rows: dict[int, list[tuple[datetime, float]]],
    figure_details: tuple[str, Path], vertical_limits: tuple[float, float],
) -> None:
    """Input: two candidate series, (title, PNG path), and shared y limits.
    Output: one model's raw 10-second 3/5-orbit candidate plot."""
    title, output_path = figure_details
    if not rows[3] or not rows[5]:
        raise ValueError(f"Missing 3/5-orbit candidates for {title}.")
    figure, axis = plt.subplots(figsize=(13, 4.8), constrained_layout=True)
    for orbit_count, color in ((3, THREE_ORBIT_COLOR), (5, FIVE_ORBIT_COLOR)):
        axis.plot(
            [time_utc for time_utc, _ in rows[orbit_count]],
            [rate_m_day for _, rate_m_day in rows[orbit_count]],
            color=color, linewidth=0.9, label=f"{orbit_count} 圈",
        )
    axis.axhline(0.0, color="#0f172a", linewidth=0.8)
    axis.set_ylim(*vertical_limits)
    axis.set_title(title)
    axis.set_ylabel("局部斜率候選（m/day）")
    axis.set_xlabel("2024-05-03 UTC")
    axis.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))
    axis.legend(loc="lower left", ncol=2)
    axis.grid(alpha=0.22)
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def read_yearly_coverage(connection: sqlite3.Connection) -> list[tuple[int, int, int, int, int]]:
    """Input: read-only v2 database. Output: [(year, expected, source, valid3, valid5), ...]."""
    coverage = []
    for year in range(2014, 2027):
        year_start = max(
            REPORT_START_TIME_US,
            int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1_000_000),
        )
        year_stop = min(
            REPORT_STOP_TIME_US,
            int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1_000_000),
        )
        expected = (year_stop - year_start) // 10_000_000
        source, valid3, valid5 = connection.execute(f"""
            SELECT count(*),
                   sum(orbit_3_decay_rate_m_s IS NOT NULL AND orbit_3_window_start_time_us >= ?),
                   sum(orbit_5_decay_rate_m_s IS NOT NULL AND orbit_5_window_start_time_us >= ?)
            FROM {RAW_TABLE} WHERE time_us >= ? AND time_us < ?
        """, (REPORT_START_TIME_US, REPORT_START_TIME_US, year_start, year_stop)).fetchone()
        coverage.append((year, expected, source, valid3 or 0, valid5 or 0))
    return coverage


def save_yearly_coverage_figure(coverage: list[tuple[int, int, int, int, int]]) -> None:
    """Input: yearly scope counts. Output: coverage and valid-rate PNG."""
    years = [row[0] for row in coverage]
    observed_fraction = [row[2] / row[1] for row in coverage]
    valid3_fraction = [row[3] / row[2] if row[2] else 0 for row in coverage]
    valid5_fraction = [row[4] / row[2] if row[2] else 0 for row in coverage]
    figure, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, constrained_layout=True)
    axes[0].bar(years, observed_fraction, color="#0072BD")
    axes[0].set_ylabel("可用點 / 10 秒網格")
    axes[0].set_ylim(0, 1.05)
    axes[1].plot(years, valid3_fraction, "o-", label="3 圈", color="#0072BD")
    axes[1].plot(years, valid5_fraction, "o-", label="5 圈", color="#D95319")
    axes[1].set_ylabel("有效斜率 / 可用點")
    axes[1].set_ylim(max(0, min(valid3_fraction + valid5_fraction) - 0.005), 1.001)
    axes[1].set_xticks(years)
    axes[1].set_xlabel("UTC 年份；2014 與 2026 為半年")
    axes[1].legend()
    for axis in axes:
        axis.grid(axis="y", alpha=0.2)
    figure.suptitle("Phase 1R：2014-07 至 2026-06 逐年涵蓋與候選有效比例")
    figure.savefig(IMAGE_DIRECTORY / "report-12y-05-yearly-coverage.png", dpi=FIGURE_DPI)
    plt.close(figure)


def save_harmonic_example_figure(connection: sqlite3.Connection) -> None:
    """Input: read-only v2 database. Output: a 2018 H2/H3 fit and residual PNG."""
    fit = connection.execute(f"""
        SELECT time_us, orbit_3_window_start_time_us, orbit_3_decay_rate_m_s,
               orbit_3_h2_cos_m, orbit_3_h2_sin_m, orbit_3_h3_cos_m, orbit_3_h3_sin_m
        FROM {JOINT_TABLE}
        WHERE time_us >= ? AND orbit_3_decay_rate_m_s IS NOT NULL
        ORDER BY time_us LIMIT 1
    """, (HARMONIC_EXAMPLE_US,)).fetchone()
    if fit is None:
        raise ValueError("No 2018 v2 H2/H3 example exists.")
    end_us, start_us, slope_m_s, h2c, h2s, h3c, h3s = fit
    rows = list(connection.execute(f"""
        SELECT time_us, mean_semi_major_axis_m,
               mean_argument_of_perigee_rad + mean_anomaly_rad
        FROM {MEAN_TABLE} WHERE time_us BETWEEN ? AND ? ORDER BY time_us
    """, (start_us, end_us)))
    if not rows:
        raise ValueError("No mean-element samples exist for the 2018 v2 example.")
    times = [utc_datetime(row[0]) for row in rows]
    elapsed_s = [(row[0] - rows[0][0]) / 1_000_000 for row in rows]
    harmonics_m = [
        h2c * cos(2 * row[2]) + h2s * sin(2 * row[2])
        + h3c * cos(3 * row[2]) + h3s * sin(3 * row[2])
        for row in rows
    ]
    corrected_m = [row[1] - harmonic for row, harmonic in zip(rows, harmonics_m)]
    intercept_m = mean(corrected_m) - slope_m_s * mean(elapsed_s)
    raw_detrended_m = [row[1] - intercept_m - slope_m_s * elapsed
                       for row, elapsed in zip(rows, elapsed_s)]
    residual_m = [raw - harmonic for raw, harmonic in zip(raw_detrended_m, harmonics_m)]
    figure, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, constrained_layout=True)
    axes[0].plot(times, raw_detrended_m, linewidth=0.8, label="去除線性趨勢後")
    axes[0].plot(times, harmonics_m, linewidth=1.2, label="v2 H2/H3 項")
    axes[0].set_ylabel("半長軸偏差（m）")
    axes[0].legend()
    axes[1].plot(times, residual_m, color="#77AC30", linewidth=0.8)
    axes[1].set_ylabel("扣除 H2/H3 後殘差（m）")
    axes[1].set_xlabel("UTC")
    for axis in axes:
        axis.grid(alpha=0.2)
    figure.suptitle("2018-01-15：十二年庫 v2 三圈視窗 H2/H3 擬合示例")
    figure.savefig(IMAGE_DIRECTORY / "report-12y-04-h2h3-example-2018.png", dpi=FIGURE_DPI)
    plt.close(figure)


def save_storm_case_figure(rows: list[tuple]) -> None:
    """Input: hourly v2 rate and feature medians. Output: storm-case PNG."""
    if not rows:
        raise ValueError("No 2024 storm-case rows exist in the twelve-year database.")
    dates = [row[0] for row in rows]
    figure, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for axis, column, label, color in (
        (axes[0], 4, "H2/H3 五圈（m/day）", "#77AC30"),
        (axes[1], 5, "SYM-H（nT）", "#364fc7"),
        (axes[2], 6, "Ap", "#d9480f"),
    ):
        axis.plot(dates, [row[column] for row in rows], color=color, linewidth=1.2)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[2].set_xlabel("UTC")
    locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
    axes[2].xaxis.set_major_locator(locator)
    axes[2].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    figure.suptitle("2024 年 5 月擾動個案：十二年庫的每小時中位數，僅供描述")
    figure.savefig(IMAGE_DIRECTORY / "report-12y-06-may-2024-storm-case.png", dpi=FIGURE_DPI)
    plt.close(figure)


def generate_twelve_year_figures() -> None:
    """Input: fixed twelve-year SQLite database. Output: six report PNGs."""
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(DATABASE_PATH)
    IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False
    with sqlite3.connect(f"file:{DATABASE_PATH.as_posix()}?mode=ro", uri=True) as connection:
        daily_rows = read_daily_mean_rows(connection)
        raw_rows = read_candidate_day_rows(connection, RAW_TABLE)
        joint_rows = read_candidate_day_rows(connection, JOINT_TABLE)
        coverage = read_yearly_coverage(connection)
        save_harmonic_example_figure(connection)
        storm_rows = hourly_candidates(connection, STORM_START_US, STORM_STOP_US)
    save_yearly_coverage_figure(coverage)
    save_storm_case_figure(storm_rows)
    save_daily_mean_figure(
        daily_rows, IMAGE_DIRECTORY / "report-12y-01-daily-mean-semi-major-axis.png",
    )
    all_rates = [
        rate_m_day
        for model_rows in (raw_rows, joint_rows)
        for orbit_rows in model_rows.values()
        for _, rate_m_day in orbit_rows
    ]
    if not all_rates:
        raise ValueError("No twelve-year example candidates were found.")
    rate_range = max(all_rates) - min(all_rates)
    vertical_limits = (
        min(all_rates) - 0.05 * rate_range,
        max(all_rates) + 0.05 * rate_range,
    )
    save_candidate_pair_figure(
        raw_rows,
        ("2024-05-03：原始模型（無 H2/H3）",
         IMAGE_DIRECTORY / "report-12y-03a-raw-candidates-2024-05-03.png"),
        vertical_limits,
    )
    save_candidate_pair_figure(
        joint_rows,
        ("2024-05-03：H2/H3 聯合模型",
         IMAGE_DIRECTORY / "report-12y-03b-h2-h3-candidates-2024-05-03.png"),
        vertical_limits,
    )


if __name__ == "__main__":
    generate_twelve_year_figures()
