"""Draw logarithmic ap views and compare yearly non-event baselines."""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from phases.phase3.code.prep_phase3_ap_check import (
    AP_SOURCE,
    EVENT_SOURCE,
    FIRST_DAY,
    IMAGE_FOLDER,
    MINUTES_PER_AP_SLOT,
    read_ap_minutes,
    read_events,
    selected_minutes,
)
from phases.phase3.code.prep_phase3_ap_storm_compare import read_storm_core


TIMELINE_PNG = IMAGE_FOLDER / "ap_log_storm_vs_outside_3y.png"
DISTRIBUTION_PNG = IMAGE_FOLDER / "ap_log_distributions_and_years.png"
YEAR_CSV = Path("phases/phase3/data/analysis/phase3_ap_outside_by_year.csv")
AP_TICKS = (0, 2, 4, 7, 10, 20, 50, 100, 200, 400)
LOG_BINS = np.linspace(0, np.log10(401), 43)


def outside_year_stats(ap_minutes: np.ndarray, selected: np.ndarray,
                       first_time: datetime) -> list[dict]:
    """Input: minute ap, event mask, UTC start. Output: annual outside-window rows."""
    rows = []
    for year_index in range(3):
        start = datetime(FIRST_DAY.year + year_index, 7, 1, tzinfo=timezone.utc)
        end = datetime(FIRST_DAY.year + year_index + 1, 7, 1, tzinfo=timezone.utc)
        first = int((start - first_time).total_seconds() // 60)
        last = int((end - first_time).total_seconds() // 60)
        values = ap_minutes[first:last][~selected[first:last]]
        rows.append({
            "research_year": year_index + 1,
            "start_utc": start.date().isoformat(),
            "end_utc_exclusive": end.date().isoformat(),
            "outside_minutes": len(values),
            "p25_ap": float(np.percentile(values, 25)),
            "median_ap": float(np.median(values)),
            "p75_ap": float(np.percentile(values, 75)),
            "p90_ap": float(np.percentile(values, 90)),
            "percent_ap_at_least_50": float(np.mean(values >= 50) * 100),
        })
    return rows


def draw_log_timeline(ap_minutes: np.ndarray, selected: np.ndarray,
                      first_time: datetime) -> None:
    """Input: minute ap, event mask, UTC start. Output: log timeline PNG."""
    slot_indexes = np.arange(0, len(ap_minutes), MINUTES_PER_AP_SLOT)
    slot_times = [first_time + timedelta(minutes=int(index)) for index in slot_indexes]
    transformed = np.log10(1 + ap_minutes[slot_indexes])
    outside = np.where(selected[slot_indexes], np.nan, transformed)
    inside = np.where(selected[slot_indexes], transformed, np.nan)
    figure, axes = plt.subplots(3, 1, figsize=(15, 9), constrained_layout=True)
    for year_index, axis in enumerate(axes):
        year_start = datetime(FIRST_DAY.year + year_index, 7, 1, tzinfo=timezone.utc)
        year_end = datetime(FIRST_DAY.year + year_index + 1, 7, 1, tzinfo=timezone.utc)
        axis.plot(slot_times, outside, color="#2563eb", linewidth=0.65, label="Outside")
        axis.plot(slot_times, inside, color="#dc2626", linewidth=0.85,
                  label="Inside 25 six-day windows")
        axis.axhline(np.log10(1 + 7), color="#475569", linestyle="--", linewidth=1,
                     label="Overall outside median ap = 7")
        axis.set(xlim=(year_start, year_end), ylim=(0, np.log10(401)),
                 ylabel="ap [log10(1+ap) scale]")
        axis.set_yticks(np.log10(1 + np.array(AP_TICKS)), labels=[str(value) for value in AP_TICKS])
        axis.set_title(f"{year_start:%Y-%m-%d} to {year_end:%Y-%m-%d}", loc="left")
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        axis.grid(axis="y", alpha=0.25)
    axes[0].legend(loc="upper right", ncol=3)
    axes[-1].set_xlabel("UTC; original 3-hour ap values, shown on a logarithmic scale")
    figure.suptitle("Three-year GFZ ap: selected events and the remaining record")
    figure.savefig(TIMELINE_PNG, dpi=180)
    plt.close(figure)


def draw_log_distributions(ap_minutes: np.ndarray, selected: np.ndarray,
                           core: np.ndarray) -> None:
    """Input: minute ap, event mask, core mask. Output: distribution PNG."""
    figure, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    groups = (
        ("Outside windows", ap_minutes[~selected], "#2563eb"),
        ("Inside six-day windows", ap_minutes[selected], "#f59e0b"),
        ("SYM-H storm core", ap_minutes[core], "#dc2626"),
    )
    for label, values, color in groups:
        density, edges = np.histogram(np.log10(1 + values), bins=LOG_BINS, density=True)
        axes[0].plot((edges[:-1] + edges[1:]) / 2, density, color=color, label=label)
    axes[0].set(title="Event classification", ylabel="Relative frequency density")
    first_time = datetime(FIRST_DAY.year, FIRST_DAY.month, FIRST_DAY.day, tzinfo=timezone.utc)
    for year_index, color in enumerate(("#2563eb", "#059669", "#7c3aed")):
        start = datetime(FIRST_DAY.year + year_index, 7, 1, tzinfo=timezone.utc)
        end = datetime(FIRST_DAY.year + year_index + 1, 7, 1, tzinfo=timezone.utc)
        first = int((start - first_time).total_seconds() // 60)
        last = int((end - first_time).total_seconds() // 60)
        values = ap_minutes[first:last][~selected[first:last]]
        density, edges = np.histogram(np.log10(1 + values), bins=LOG_BINS, density=True)
        axes[1].plot((edges[:-1] + edges[1:]) / 2, density, color=color,
                     label=f"Year {year_index + 1}")
    axes[1].axvline(np.log10(1 + 7), color="#475569", linestyle="--",
                    label="Overall outside median: ap = 7")
    axes[1].set(title="Outside-window ap by research year")
    for axis in axes:
        axis.set_xlabel("ap [log10(1+ap) scale]")
        axis.set_xticks(np.log10(1 + np.array(AP_TICKS)),
                        labels=[str(value) for value in AP_TICKS])
        axis.grid(axis="y", alpha=0.2)
        axis.legend()
    figure.suptitle("Minute-weighted distributions of the 3-hour GFZ ap values")
    figure.savefig(DISTRIBUTION_PNG, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: frozen three-year sources. Output: two log PNGs and year CSV."""
    for path in (TIMELINE_PNG, DISTRIBUTION_PNG, YEAR_CSV):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}.")
    ap_minutes, first_time = read_ap_minutes(AP_SOURCE)
    events = read_events(EVENT_SOURCE)
    selected = selected_minutes(len(ap_minutes), events, first_time)
    core = read_storm_core(len(ap_minutes), selected, first_time)
    rows = outside_year_stats(ap_minutes, selected, first_time)
    IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    with YEAR_CSV.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    draw_log_timeline(ap_minutes, selected, first_time)
    draw_log_distributions(ap_minutes, selected, core)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
