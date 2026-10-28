"""Compare definitive ap inside and outside the 25 Phase 2 storm windows."""

import csv
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from research_workspace.phases.phase3.code.prep_phase3_ap_check import (
    AP_SOURCE,
    EVENT_SOURCE,
    FIRST_DAY,
    IMAGE_FOLDER,
    MICROSECONDS_PER_MINUTE,
    MINUTES_PER_AP_SLOT,
    read_ap_minutes,
    read_events,
    selected_minutes,
)


STATS_CSV = Path("research_workspace/phases/phase3/data/analysis/phase3_ap_storm_vs_outside_25.csv")
TIMELINE_PNG = IMAGE_FOLDER / "ap_storm_vs_outside_3y.png"
DISTRIBUTION_PNG = IMAGE_FOLDER / "ap_storm_vs_outside_distribution.png"


def read_storm_core(total_minutes: int, selected: np.ndarray, first_time: datetime) -> np.ndarray:
    """Input: minute length, event mask, UTC start. Output: selected SYM-H core mask."""
    first_minute = int(first_time.timestamp() // 60)
    core = np.zeros(total_minutes, dtype=bool)
    database_uri = f"file:{EVENT_SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as database:
        rows = database.execute(
            "SELECT time_us FROM geomag_1min_v2 WHERE symh_nt < -100"
        )
        for (time_us,) in rows:
            minute = time_us // MICROSECONDS_PER_MINUTE - first_minute
            if 0 <= minute < total_minutes and selected[minute]:
                core[minute] = True
    return core


def group_stats(ap_minutes: np.ndarray, selected: np.ndarray, core: np.ndarray) -> list[dict]:
    """Input: minute ap and two masks. Output: three minute-weighted summaries."""
    rows = []
    for label, mask in (
        ("Outside 25 windows", ~selected),
        ("Inside 25 six-day windows", selected),
        ("SYM-H < -100 nT inside windows", core),
    ):
        values = ap_minutes[mask]
        rows.append({
            "group": label,
            "minute_count": len(values),
            "median_ap": float(np.median(values)),
            "mean_ap": float(np.mean(values)),
            "p90_ap": float(np.percentile(values, 90)),
            "p95_ap": float(np.percentile(values, 95)),
            "max_ap": float(np.max(values)),
            "percent_ap_at_least_50": float(np.mean(values >= 50) * 100),
        })
    return rows


def write_stats(rows: list[dict]) -> None:
    """Input: three summary rows. Output: new Phase 3 CSV."""
    with STATS_CSV.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_timeline(ap_minutes: np.ndarray, selected: np.ndarray, first_time: datetime) -> None:
    """Input: minute ap, event mask, UTC start. Output: three-year PNG."""
    slot_indexes = np.arange(0, len(ap_minutes), MINUTES_PER_AP_SLOT)
    slot_times = [first_time + timedelta(minutes=int(index)) for index in slot_indexes]
    values = ap_minutes[slot_indexes]
    outside = np.where(selected[slot_indexes], np.nan, values)
    inside = np.where(selected[slot_indexes], values, np.nan)
    figure, axes = plt.subplots(3, 1, figsize=(15, 9), constrained_layout=True)
    for year_index, axis in enumerate(axes):
        year_start = datetime(FIRST_DAY.year + year_index, 7, 1, tzinfo=timezone.utc)
        year_end = datetime(FIRST_DAY.year + year_index + 1, 7, 1, tzinfo=timezone.utc)
        axis.plot(slot_times, outside, color="#2563eb", linewidth=0.6, label="Outside")
        axis.plot(slot_times, inside, color="#dc2626", linewidth=0.8,
                  label="Inside 25 six-day windows")
        axis.axhline(4, color="#475569", linestyle="--", linewidth=0.9,
                     label="Illustrative fixed ap = 4")
        axis.set(xlim=(year_start, year_end), ylim=(0, 410), ylabel="ap")
        axis.set_title(f"{year_start:%Y-%m-%d} to {year_end:%Y-%m-%d}", loc="left")
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        axis.grid(axis="y", alpha=0.25)
    axes[0].legend(loc="upper right", ncol=3)
    axes[-1].set_xlabel("UTC; plotted at the original 3-hour ap cadence")
    figure.suptitle("Actual GFZ ap: selected storm windows versus the remaining three-year record")
    figure.savefig(TIMELINE_PNG, dpi=180)
    plt.close(figure)


def draw_distribution(rows: list[dict]) -> None:
    """Input: three minute-weighted summaries. Output: comparison PNG."""
    labels = ["Outside", "Six-day windows", "SYM-H core"]
    positions = np.arange(len(rows))
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    width = 0.36
    axes[0].bar(positions - width / 2, [row["median_ap"] for row in rows],
                width, color="#2563eb", label="Median")
    axes[0].bar(positions + width / 2, [row["p90_ap"] for row in rows],
                width, color="#f59e0b", label="90th percentile")
    axes[0].set(ylabel="ap", title="ap level", xticks=positions, xticklabels=labels)
    axes[0].legend()
    axes[1].bar(positions, [row["percent_ap_at_least_50"] for row in rows],
                color=["#2563eb", "#f59e0b", "#dc2626"])
    axes[1].set(ylabel="Percent of minutes", title="Minutes with ap >= 50",
                xticks=positions, xticklabels=labels, ylim=(0, 100))
    for index, row in enumerate(rows):
        axes[1].text(index, row["percent_ap_at_least_50"] + 2,
                     f"{row['percent_ap_at_least_50']:.1f}%", ha="center")
    for axis in axes:
        axis.grid(axis="y", alpha=0.2)
        axis.set_axisbelow(True)
    figure.suptitle("Phase 2 25-event ap comparison; 3-hour values weighted by minute duration")
    figure.savefig(DISTRIBUTION_PNG, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: frozen GFZ and Phase 2 sources. Output: CSV and two PNGs."""
    for path in (STATS_CSV, TIMELINE_PNG, DISTRIBUTION_PNG):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}.")
    ap_minutes, first_time = read_ap_minutes(AP_SOURCE)
    events = read_events(EVENT_SOURCE)
    selected = selected_minutes(len(ap_minutes), events, first_time)
    core = read_storm_core(len(ap_minutes), selected, first_time)
    if not np.any(core) or np.any(core & ~selected):
        raise ValueError("The selected SYM-H storm core is invalid.")
    rows = group_stats(ap_minutes, selected, core)
    IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    write_stats(rows)
    draw_timeline(ap_minutes, selected, first_time)
    draw_distribution(rows)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
