"""Compare three-year storm-side SME and show pre-storm candidate distributions."""

import csv
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


SOURCE = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_2_v2.sqlite")
REPORT = Path("output/report/phase3_sme_pre_post_25.csv")
IMAGE_FOLDER = Path("output/image/Phase3")
FIRST_TIME = datetime(2023, 7, 1, tzinfo=timezone.utc)
LAST_TIME = datetime(2026, 7, 1, tzinfo=timezone.utc)
MINUTE_US = 60_000_000
MINUTES_PER_DAY = 1440
EXPECTED_MINUTES = int((LAST_TIME - FIRST_TIME).total_seconds() // 60)


def read_source(path: Path) -> tuple[np.ndarray, list[tuple[str, int]]]:
    """Input: frozen P2.2 SQLite. Output: [1-minute SME], [(storm_id, t0_us)]."""
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        count, first, last = database.execute(
            "SELECT COUNT(*), MIN(time_us), MAX(time_us) FROM geomag_1min_v2"
        ).fetchone()
        if (count, first, last) != (
            EXPECTED_MINUTES,
            int(FIRST_TIME.timestamp() * 1_000_000),
            int((LAST_TIME - timedelta(minutes=1)).timestamp() * 1_000_000),
        ):
            raise ValueError("P2.2 SME minute grid is incomplete.")
        sme = np.fromiter(
            (float(value) if valid else np.nan for value, valid in database.execute(
                "SELECT sme_nt, sme_valid FROM geomag_1min_v2 ORDER BY time_us"
            )),
            dtype=float,
            count=EXPECTED_MINUTES,
        )
        events = database.execute(
            "SELECT storm_id, t0_time_us FROM storm_event_v2 ORDER BY t0_time_us"
        ).fetchall()
    if len(events) != 25:
        raise ValueError(f"Expected 25 events, found {len(events)}.")
    return sme, events


def event_center(t0_time_us: int) -> int:
    """Input: UTC event epoch. Output: minute index from study start."""
    return t0_time_us // MINUTE_US - int(FIRST_TIME.timestamp() // 60)


def window_summary(values: np.ndarray, prefix: str) -> dict:
    """Input: one 1,440-minute SME window and field prefix. Output: stats {name: value}."""
    if len(values) != MINUTES_PER_DAY:
        raise ValueError("SME window is outside the three-year source.")
    observed = values[np.isfinite(values)]
    if len(observed) < int(0.8 * MINUTES_PER_DAY):
        raise ValueError(f"Insufficient SME coverage in {prefix} window.")
    return {
        f"{prefix}_valid_minutes": len(observed),
        f"{prefix}_q1_sme_nt": float(np.quantile(observed, 0.25)),
        f"{prefix}_median_sme_nt": float(np.median(observed)),
        f"{prefix}_q3_sme_nt": float(np.quantile(observed, 0.75)),
        f"{prefix}_p90_sme_nt": float(np.quantile(observed, 0.90)),
        f"{prefix}_max_sme_nt": float(np.max(observed)),
    }


def summarize_events(sme: np.ndarray, events: list[tuple[str, int]]) -> list[dict]:
    """Input: [minute SME], [event]. Output: [pre/post 24-hour summary]."""
    rows = []
    for storm_id, t0_time_us in events:
        center = event_center(t0_time_us)
        pre = sme[center - 3 * MINUTES_PER_DAY:center - 2 * MINUTES_PER_DAY]
        post = sme[center + 4 * MINUTES_PER_DAY:center + 5 * MINUTES_PER_DAY]
        before = window_summary(pre, "pre")
        after = window_summary(post, "post")
        rows.append({
            "storm_id": storm_id,
            "t0_utc": datetime.fromtimestamp(t0_time_us / 1_000_000, timezone.utc).isoformat(),
            **before,
            **after,
            "post_minus_pre_median_sme_nt": (
                after["post_median_sme_nt"] - before["pre_median_sme_nt"]
            ),
        })
    return rows


def write_report(rows: list[dict], path: Path) -> None:
    """Input: [event summary], new CSV path. Output: saved CSV."""
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_pre_post(rows: list[dict], path: Path) -> None:
    """Input: [event summary], new PNG path. Output: pre/post median scatter."""
    pre = [row["pre_median_sme_nt"] for row in rows]
    post = [row["post_median_sme_nt"] for row in rows]
    limit = max(pre + post) * 1.1
    figure, axis = plt.subplots(figsize=(7.5, 7), constrained_layout=True)
    axis.scatter(pre, post, color="#2563eb", s=48, zorder=3)
    axis.plot([0, limit], [0, limit], color="#64748b", linestyle="--", linewidth=1)
    for row in sorted(
        rows, key=lambda item: abs(item["post_minus_pre_median_sme_nt"]), reverse=True
    )[:5]:
        axis.annotate(
            row["t0_utc"][:10],
            (row["pre_median_sme_nt"], row["post_median_sme_nt"]),
            xytext=(5, 5), textcoords="offset points", fontsize=8,
        )
    axis.set(
        xlim=(0, limit), ylim=(0, limit),
        xlabel="SME median (nT): t0 - 3 to - 2 days",
        ylabel="SME median (nT): t0 + 4 to + 5 days",
        title="Phase 2 storms: pre/post 24-hour SME medians (n=25)",
    )
    axis.grid(alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def draw_pre_distributions(rows: list[dict], path: Path) -> None:
    """Input: [event summary], new PNG path. Output: pre-window spread by event."""
    ordered = sorted(rows, key=lambda row: row["pre_median_sme_nt"])
    figure, axis = plt.subplots(figsize=(10, 9), constrained_layout=True)
    for index, row in enumerate(ordered):
        axis.plot(
            [row["pre_q1_sme_nt"], row["pre_q3_sme_nt"]], [index, index],
            color="#2563eb", linewidth=5, solid_capstyle="round",
        )
        axis.scatter(row["pre_median_sme_nt"], index, color="#0f172a", s=25, zorder=3)
        axis.scatter(row["pre_p90_sme_nt"], index, color="#d97706", marker="|", s=120)
        axis.scatter(row["pre_max_sme_nt"], index, color="#94a3b8", marker="x", s=24)
    axis.set_yticks(range(len(ordered)), [row["t0_utc"][:10] for row in ordered])
    axis.set_xscale("log")
    axis.set_xticks([20, 50, 100, 200, 500, 1000, 2000])
    axis.get_xaxis().set_major_formatter(mticker.ScalarFormatter())
    axis.set(
        xlim=(20, 2200),
        xlabel="SME (nT), log scale; blue = Q1-Q3, dot = median, orange = P90, x = max",
        ylabel="Storm t0 date (UTC)",
        title="SME during t0 - 3 to - 2 days: each 24-hour window",
    )
    axis.grid(axis="x", alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def draw_outside_events(sme: np.ndarray, events: list[tuple[str, int]], path: Path) -> None:
    """Input: [minute SME], [event], new PNG path. Output: outside-event time view."""
    selected = np.zeros(len(sme), dtype=bool)
    for _, t0_time_us in events:
        center = event_center(t0_time_us)
        selected[center - 2 * MINUTES_PER_DAY:center + 4 * MINUTES_PER_DAY] = True
    if np.count_nonzero(selected) != 25 * 6 * MINUTES_PER_DAY:
        raise ValueError("Storm windows overlap or extend outside source.")
    hourly = sme.reshape(-1, 60)
    hourly_median = np.full(len(hourly), np.nan)
    for index, hour in enumerate(hourly):
        observed = hour[np.isfinite(hour)]
        if len(observed) >= 45:
            hourly_median[index] = np.median(observed)
    hourly_median[selected.reshape(-1, 60).any(axis=1)] = np.nan
    hours = [FIRST_TIME + timedelta(hours=index) for index in range(len(hourly_median))]
    last_valid_index = int(np.flatnonzero(np.isfinite(sme))[-1])
    data_end = FIRST_TIME + timedelta(minutes=last_valid_index + 1)
    figure, axes = plt.subplots(3, 1, figsize=(15, 9), constrained_layout=True)
    for year_index, axis in enumerate(axes):
        start = datetime(2023 + year_index, 7, 1, tzinfo=timezone.utc)
        end = datetime(2024 + year_index, 7, 1, tzinfo=timezone.utc)
        axis.plot(hours, hourly_median, color="#2563eb", linewidth=0.65)
        for _, t0_time_us in events:
            t0 = datetime.fromtimestamp(t0_time_us / 1_000_000, timezone.utc)
            axis.axvspan(t0 - timedelta(days=2), t0 + timedelta(days=4),
                         color="#f59e0b", alpha=0.18)
        if data_end < end:
            axis.axvspan(max(data_end, start), end, color="#94a3b8", alpha=0.25)
            if data_end > start:
                axis.text(data_end + timedelta(days=2), 2400, "SME unavailable", fontsize=9)
        axis.set(xlim=(start, end), ylim=(0, 3500), ylabel="SME (nT)")
        axis.set_yscale("symlog", linthresh=50)
        axis.set_yticks([0, 50, 100, 200, 500, 1000, 2000, 3500])
        axis.get_yaxis().set_major_formatter(mticker.ScalarFormatter())
        axis.set_title(f"{start:%Y-%m-%d} to {end:%Y-%m-%d}", loc="left")
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("SuperMAG SME outside 25 selected storm windows (orange = excluded)")
    axes[-1].set_xlabel("UTC; hourly medians of 1-minute SME; symlog vertical scale")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: frozen three-year checkpoint. Output: CSV, three PNGs, summary stats."""
    sme, events = read_source(SOURCE)
    rows = summarize_events(sme, events)
    pre_post = IMAGE_FOLDER / "sme_pre_post_25.png"
    spread = IMAGE_FOLDER / "sme_pre_window_25.png"
    outside = IMAGE_FOLDER / "sme_outside_selected_3y.png"
    for path in (REPORT, pre_post, spread, outside):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}.")
    IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    write_report(rows, REPORT)
    draw_pre_post(rows, pre_post)
    draw_pre_distributions(rows, spread)
    draw_outside_events(sme, events, outside)
    medians = [row["pre_median_sme_nt"] for row in rows]
    print({
        "events": len(rows),
        "pre_median_min_nT": min(medians),
        "pre_median_median_nT": float(np.median(medians)),
        "pre_median_max_nT": max(medians),
        "events_with_pre_median_above_300_nT": sum(value > 300 for value in medians),
        "all_pre_post_windows_complete": all(
            row["pre_valid_minutes"] == row["post_valid_minutes"] == MINUTES_PER_DAY
            for row in rows
        ),
        "report": str(REPORT),
        "figures": [str(pre_post), str(spread), str(outside)],
    })


if __name__ == "__main__":
    main()
