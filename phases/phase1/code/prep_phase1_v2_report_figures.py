"""Render Phase 1 candidate figures from the current 10-second v2 tables."""

import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from math import cos, sin
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from phases.phase1.code.prep_14_phase_harmonic_decay_candidates import (
    JOINT_H2_H3_SET_TABLE,
    RAW_B_L_SET_TABLE,
)
from phases.phase1.code.prep_15_phase_harmonic_features_v2 import FEATURE_TABLE
from phases.phase1.code.prep_report_figures import configure_chinese_font


DATABASE = Path("phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite")
FIGURES = Path("phases/phase1/figures")
MEAN_TABLE = "swarm_a_mean_orbit_elements_v1"
SECONDS_PER_DAY = 86_400
MICROSECONDS_PER_SECOND = 1_000_000
MAY_START_US = 1714521600000000
MAY_STOP_US = 1717200000000000
STORM_START_US = 1715212800000000
STORM_STOP_US = 1715558400000000
EXAMPLE_US = 1714732102000000


def as_utc(time_us):
    """Input: Unix time in microseconds. Output: UTC datetime."""
    return datetime.fromtimestamp(time_us / MICROSECONDS_PER_SECOND, timezone.utc)


def save_figure(figure, path):
    """Input: Matplotlib figure and PNG path. Output: saved, closed figure."""
    figure.savefig(path, dpi=180)
    plt.close(figure)


def plot_ols_examples(connection):
    """Input: read-only v2 database. Output: two actual v2 OLS window PNGs."""
    fit = connection.execute(f"""
        SELECT raw.time_us, raw.orbit_3_window_start_time_us,
               raw.orbit_3_decay_rate_m_s,
               joint.orbit_3_decay_rate_m_s,
               joint.orbit_3_h2_cos_m, joint.orbit_3_h2_sin_m,
               joint.orbit_3_h3_cos_m, joint.orbit_3_h3_sin_m
        FROM {RAW_B_L_SET_TABLE} raw
        JOIN {JOINT_H2_H3_SET_TABLE} joint USING (time_us)
        WHERE raw.time_us >= ? AND raw.orbit_3_decay_rate_m_s IS NOT NULL
          AND joint.orbit_3_decay_rate_m_s IS NOT NULL
        ORDER BY raw.time_us LIMIT 1
    """, (EXAMPLE_US,)).fetchone()
    if fit is None:
        raise ValueError("No valid v2 three-orbit window for the report example.")
    end_us, start_us, raw_slope, joint_slope, h2c, h2s, h3c, h3s = fit
    samples = list(connection.execute(f"""
        SELECT time_us, mean_semi_major_axis_m,
               mean_argument_of_perigee_rad + mean_anomaly_rad
        FROM {MEAN_TABLE} WHERE time_us BETWEEN ? AND ? ORDER BY time_us
    """, (start_us, end_us)))
    if len(samples) < 7:
        raise ValueError("The selected v2 OLS window has too few source samples.")
    times = [as_utc(row[0]) for row in samples]
    relative_seconds = np.array([(row[0] - samples[0][0]) / MICROSECONDS_PER_SECOND for row in samples])
    raw_values = np.array([row[1] for row in samples])
    correction = np.array([
        h2c * cos(2 * row[2]) + h2s * sin(2 * row[2])
        + h3c * cos(3 * row[2]) + h3s * sin(3 * row[2])
        for row in samples
    ])
    for values, slope, title, filename, color, value_label in (
        (raw_values, raw_slope, "v2 原始模型：三圈視窗", "report-05a-v2-raw-ols-three-orbit-example.png", "#0072BD", "10 秒平均元素"),
        (raw_values - correction, joint_slope, "v2 H2/H3 聯合模型：三圈視窗", "report-05b-v2-h2-h3-ols-three-orbit-example.png", "#77AC30", "10 秒扣除 H2/H3 後"),
    ):
        trend = values.mean() + slope * (relative_seconds - relative_seconds.mean())
        figure, axis = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
        axis.plot(times, values, color=color, linewidth=0.7, label=value_label)
        axis.plot(times, trend, color="#1f2937", linewidth=1.8,
                  label=f"資料表斜率：{slope * SECONDS_PER_DAY:.1f} m/day")
        axis.set(title=title, xlabel="UTC", ylabel="半長軸（m）")
        axis.ticklabel_format(axis="y", style="plain", useOffset=True)
        axis.legend()
        axis.grid(alpha=0.2)
        save_figure(figure, FIGURES / filename)
    return start_us, end_us, raw_slope * SECONDS_PER_DAY, joint_slope * SECONDS_PER_DAY


def hourly_candidates(connection, start_us, stop_us):
    """Input: read-only v2 database and [start, stop) microseconds. Output: hourly median rate rows."""
    hours = defaultdict(lambda: [[], [], [], [], [], []])
    for time_us, raw3, raw5, joint3, joint5, sym_h, ap in connection.execute(f"""
        SELECT raw.time_us, raw.orbit_3_decay_rate_m_s, raw.orbit_5_decay_rate_m_s,
               joint.orbit_3_decay_rate_m_s, joint.orbit_5_decay_rate_m_s,
               feature.sym_h_nt, feature.ap_now
        FROM {RAW_B_L_SET_TABLE} raw
        JOIN {JOINT_H2_H3_SET_TABLE} joint USING (time_us)
        JOIN {FEATURE_TABLE} feature USING (time_us)
        WHERE raw.time_us >= ? AND raw.time_us < ? ORDER BY raw.time_us
    """, (start_us, stop_us)):
        bucket = hours[time_us // 3_600_000_000]
        for index, value in enumerate((raw3, raw5, joint3, joint5, sym_h, ap)):
            if value is not None:
                bucket[index].append(value * SECONDS_PER_DAY if index < 4 else value)
    return [
        (as_utc(hour * 3_600_000_000), *(median(values) if values else None for values in columns))
        for hour, columns in sorted(hours.items())
    ]


def plot_may_candidates(rows):
    """Input: May 2024 hourly median v2 rows. Output: raw and joint comparison PNGs."""
    all_rates = np.array([value for row in rows for value in row[1:5] if value is not None])
    lower, upper = np.quantile(all_rates, [0.01, 0.99])
    for columns, title, filename in (
        ((1, 2), "v2 原始模型：2024 年 5 月", "report-06a-v2-may-2024-without-h2-h3.png"),
        ((3, 4), "v2 H2/H3 聯合模型：2024 年 5 月", "report-06b-v2-may-2024-with-h2-h3.png"),
    ):
        figure, axis = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
        for column, label, color in zip(columns, ("3 圈", "5 圈"), ("#0072BD", "#D95319")):
            axis.plot([row[0] for row in rows], [row[column] for row in rows],
                      label=label, color=color, linewidth=0.9)
        axis.set(title=title, xlabel="UTC", ylabel="每小時候選斜率中位數（m/day）")
        axis.set_ylim(lower, upper)
        axis.axhline(0, color="#333333", linewidth=0.7)
        axis.legend()
        axis.grid(alpha=0.2)
        save_figure(figure, FIGURES / filename)


def plot_quality_sample(connection):
    """Input: read-only v2 database. Output: systematic 1-in-100 quality sample PNG."""
    rows = list(connection.execute(f"""
        SELECT orbit_3_decay_rate_m_s, orbit_5_decay_rate_m_s,
               orbit_3_decay_rate_1sigma_m_s, orbit_5_decay_rate_1sigma_m_s,
               orbit_3_fit_residual_std_m, orbit_5_fit_residual_std_m,
               orbit_3_sample_count, orbit_5_sample_count
        FROM {RAW_B_L_SET_TABLE}
        WHERE ((time_us / 10000000) % 100) = 0
    """))
    figure, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    for axis, columns, title, multiplier in (
        (axes[0, 0], (0, 1), "斜率候選（m/day）", SECONDS_PER_DAY),
        (axes[0, 1], (2, 3), "斜率 1σ（m/day）", SECONDS_PER_DAY),
        (axes[1, 0], (4, 5), "擬合殘差標準差（m）", 1),
        (axes[1, 1], (6, 7), "視窗樣本數", 1),
    ):
        for column, label, color in zip(columns, ("3 圈", "5 圈"), ("#0072BD", "#D95319")):
            values = np.array([row[column] * multiplier for row in rows if row[column] is not None])
            if not len(values):
                raise ValueError(f"No sampled values for {title}, {label}.")
            lower, upper = np.quantile(values, [0.01, 0.99])
            if lower == upper:
                lower -= 0.5
                upper += 0.5
            axis.hist(values[(values >= lower) & (values <= upper)], bins=55,
                      alpha=0.5, label=label, color=color)
        axis.set_title(title)
        axis.legend()
        axis.grid(alpha=0.15)
    figure.suptitle(f"v2 原始模型品質分布：每 100 個時間點取 1 點（{len(rows):,} 列）；各圖顯示 1–99% 範圍")
    save_figure(figure, FIGURES / "report-09-v2-candidate-quality-sample.png")
    return len(rows)


def plot_storm_case(rows):
    """Input: event-hour v2 candidate and weather rows. Output: descriptive case PNG."""
    times = [row[0] for row in rows]
    figure, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    axes[0].plot(times, [row[4] for row in rows], color="#77AC30", label="H2/H3 5 圈")
    axes[0].set_ylabel("候選斜率（m/day）")
    axes[1].plot(times, [row[5] for row in rows], color="#364fc7", label="SYM-H")
    axes[1].set_ylabel("SYM-H（nT）")
    axes[2].plot(times, [row[6] for row in rows], color="#d9480f", label="Ap")
    axes[2].set_ylabel("Ap")
    axes[2].set_xlabel("UTC")
    for axis in axes:
        axis.legend(loc="upper right")
        axis.grid(alpha=0.2)
    axes[0].set_title("2024 年 5 月擾動個案：每小時中位數，僅供描述")
    locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
    axes[2].xaxis.set_major_locator(locator)
    axes[2].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    save_figure(figure, FIGURES / "report-10-v2-may-2024-storm-case.png")


def main():
    """Input: optional SQLite path. Output: Phase 1 v2 report PNGs and source counts."""
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python -m phases.phase1.code.prep_phase1_v2_report_figures [DATABASE]")
    database = Path(sys.argv[1]) if len(sys.argv) == 2 else DATABASE
    FIGURES.mkdir(parents=True, exist_ok=True)
    configure_chinese_font()
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        example = plot_ols_examples(connection)
        may_rows = hourly_candidates(connection, MAY_START_US, MAY_STOP_US)
        plot_may_candidates(may_rows)
        sampled_rows = plot_quality_sample(connection)
        storm_rows = hourly_candidates(connection, STORM_START_US, STORM_STOP_US)
        plot_storm_case(storm_rows)
    print(f"v2 example: {example}")
    print(f"May hourly bins: {len(may_rows)}; quality sample: {sampled_rows}; storm bins: {len(storm_rows)}")


if __name__ == "__main__":
    main()
