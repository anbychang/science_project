"""Draw twelve-year orbit report figures from the read-only working database."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


DATABASE_PATH = Path("research_workspace/phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite")
IMAGE_DIRECTORY = Path("research_workspace/phases/phase1r/figures")
MEAN_TABLE = "swarm_a_mean_orbit_elements_v1"
RAW_TABLE = "swarm_a_phase_harmonic_decay_raw_b_l_sets_v2"
JOINT_TABLE = "swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2"
MICROSECONDS_PER_DAY = 86_400_000_000
SECONDS_PER_DAY = 86_400
REPORT_START_TIME_US = int(datetime(2014, 7, 1, tzinfo=timezone.utc).timestamp() * 1_000_000)
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


def generate_twelve_year_figures() -> None:
    """Input: fixed twelve-year SQLite database. Output: three report PNGs."""
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(DATABASE_PATH)
    IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False
    with sqlite3.connect(f"file:{DATABASE_PATH.as_posix()}?mode=ro", uri=True) as connection:
        daily_rows = read_daily_mean_rows(connection)
        raw_rows = read_candidate_day_rows(connection, RAW_TABLE)
        joint_rows = read_candidate_day_rows(connection, JOINT_TABLE)
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
