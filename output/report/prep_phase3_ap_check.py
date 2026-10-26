"""Compare event-side ap windows and draw the three-year non-event ap series."""

import csv
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from satellite_orbit.data.geomagnetic.down_gfz_ap import validate_ap


AP_SOURCE = Path("data/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json")
EVENT_SOURCE = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_2_v2.sqlite")
IMAGE_FOLDER = Path("output/image/Phase3")
EVENT_CSV = Path("output/report/phase3_ap_pre_post_25.csv")
MINUTES_PER_DAY = 1440
MINUTES_PER_AP_SLOT = 180
MICROSECONDS_PER_MINUTE = 60_000_000
FIRST_DAY = date(2023, 7, 1)
LAST_DAY = date(2026, 6, 30)


def read_ap_minutes(path: Path) -> tuple[np.ndarray, datetime]:
    """Input: definitive GFZ JSON. Output: [one ap per minute], first UTC time."""
    payload = path.read_bytes()
    validate_ap(payload, FIRST_DAY, LAST_DAY)
    source = json.loads(payload)
    first_time = datetime.fromisoformat(source["datetime"][0].replace("Z", "+00:00"))
    values = np.asarray(source["ap"], dtype=float)
    return np.repeat(values, MINUTES_PER_AP_SLOT), first_time


def read_events(path: Path) -> list[tuple[str, int]]:
    """Input: frozen P2.2 SQLite. Output: [(storm_id, t0_time_us), ...]."""
    database_uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as database:
        events = database.execute(
            "SELECT storm_id, t0_time_us FROM storm_event_v2 ORDER BY t0_time_us"
        ).fetchall()
    if len(events) != 25:
        raise ValueError(f"Expected 25 Phase 2 storms, found {len(events)}.")
    return events


def event_minute(t0_time_us: int, first_time: datetime) -> int:
    """Input: event UTC microseconds, source start. Output: minute array index."""
    first_minute = int(first_time.timestamp() // 60)
    return t0_time_us // MICROSECONDS_PER_MINUTE - first_minute


def event_summary(ap_minutes: np.ndarray, events: list, first_time: datetime) -> list[dict]:
    """Input: minute ap, [(storm_id, t0_us)], start. Output: pre/post ap rows."""
    summaries = []
    for storm_id, t0_time_us in events:
        center = event_minute(t0_time_us, first_time)
        pre = ap_minutes[center - 3 * MINUTES_PER_DAY:center - 2 * MINUTES_PER_DAY]
        post = ap_minutes[center + 4 * MINUTES_PER_DAY:center + 5 * MINUTES_PER_DAY]
        if len(pre) != MINUTES_PER_DAY or len(post) != MINUTES_PER_DAY:
            raise ValueError(f"Incomplete pre/post ap window for {storm_id}.")
        pre_median = float(np.median(pre))
        post_median = float(np.median(post))
        summaries.append({
            "storm_id": storm_id,
            "t0_utc": datetime.fromtimestamp(t0_time_us / 1_000_000, timezone.utc).isoformat(),
            "pre_median_ap": pre_median,
            "post_median_ap": post_median,
            "post_minus_pre_ap": post_median - pre_median,
            "pre_mean_ap": float(np.mean(pre)),
            "post_mean_ap": float(np.mean(post)),
            "pre_max_ap": float(np.max(pre)),
            "post_max_ap": float(np.max(post)),
        })
    return summaries


def selected_minutes(total_minutes: int, events: list, first_time: datetime) -> np.ndarray:
    """Input: series length, events, start. Output: selected t0 [-2,+4) mask."""
    selected = np.zeros(total_minutes, dtype=bool)
    for storm_id, t0_time_us in events:
        center = event_minute(t0_time_us, first_time)
        start = center - 2 * MINUTES_PER_DAY
        end = center + 4 * MINUTES_PER_DAY
        if start < 0 or end > total_minutes:
            raise ValueError(f"Selected interval extends outside the source for {storm_id}.")
        selected[start:end] = True
    return selected


def write_event_csv(rows: list[dict], path: Path) -> None:
    """Input: event comparison rows and new CSV path. Output: saved CSV."""
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_event_comparison(rows: list[dict], path: Path) -> None:
    """Input: pre/post event rows and new PNG path. Output: comparison chart."""
    pre = [row["pre_median_ap"] for row in rows]
    post = [row["post_median_ap"] for row in rows]
    figure, axis = plt.subplots(figsize=(7.5, 7), constrained_layout=True)
    axis.scatter(pre, post, color="#2563eb", s=48, zorder=3)
    limit = max(pre + post) + 5
    axis.plot([0, limit], [0, limit], color="#64748b", linestyle="--", linewidth=1)
    for row in sorted(rows, key=lambda item: abs(item["post_minus_pre_ap"]), reverse=True)[:5]:
        axis.annotate(
            row["t0_utc"][:10],
            (row["pre_median_ap"], row["post_median_ap"]),
            xytext=(5, 5), textcoords="offset points", fontsize=8,
        )
    axis.set(xlim=(0, limit), ylim=(0, limit),
             xlabel="ap median: t0 - 3 to - 2 days",
             ylabel="ap median: t0 + 4 to + 5 days",
             title="Phase 2 storms: pre/post 24-hour ap medians (n=25)")
    axis.grid(alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def draw_unselected_ap(ap_minutes: np.ndarray, selected: np.ndarray, events: list) -> None:
    """Input: minute ap, event mask, events. Output: non-event PNG."""
    first_time = datetime(FIRST_DAY.year, FIRST_DAY.month, FIRST_DAY.day, tzinfo=timezone.utc)
    slot_indexes = np.arange(0, len(ap_minutes), MINUTES_PER_AP_SLOT)
    slot_times = [first_time + timedelta(minutes=int(index)) for index in slot_indexes]
    outside_values = np.where(selected[slot_indexes], np.nan, ap_minutes[slot_indexes])
    figure, axes = plt.subplots(3, 1, figsize=(15, 9), constrained_layout=True)
    for year_index, axis in enumerate(axes):
        year_start = datetime(FIRST_DAY.year + year_index, 7, 1, tzinfo=timezone.utc)
        year_end = datetime(FIRST_DAY.year + year_index + 1, 7, 1, tzinfo=timezone.utc)
        axis.plot(slot_times, outside_values, color="#2563eb", linewidth=0.65)
        for _, t0_time_us in events:
            t0 = datetime.fromtimestamp(t0_time_us / 1_000_000, timezone.utc)
            axis.axvspan(t0 - timedelta(days=2), t0 + timedelta(days=4),
                         color="#f59e0b", alpha=0.18)
        axis.set(xlim=(year_start, year_end), ylim=(0, 140), ylabel="ap")
        axis.set_title(f"{year_start:%Y-%m-%d} to {year_end:%Y-%m-%d}", loc="left")
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("GFZ ap outside 25 selected storm windows (orange = excluded)")
    axes[-1].set_xlabel("UTC; 3-hour source ap repeated on the minute grid")
    figure.savefig(IMAGE_FOLDER / "ap_outside_selected_3y.png", dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: frozen three-year sources. Output: CSV, two PNGs, summary counts."""
    ap_minutes, first_time = read_ap_minutes(AP_SOURCE)
    events = read_events(EVENT_SOURCE)
    rows = event_summary(ap_minutes, events, first_time)
    selected = selected_minutes(len(ap_minutes), events, first_time)
    expected_minutes = 25 * 6 * MINUTES_PER_DAY
    if int(np.count_nonzero(selected)) != expected_minutes:
        raise ValueError("Selected storm windows overlap or have unexpected coverage.")
    event_figure = IMAGE_FOLDER / "ap_pre_post_25.png"
    outside_figure = IMAGE_FOLDER / "ap_outside_selected_3y.png"
    for path in (EVENT_CSV, event_figure, outside_figure):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}.")
    IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    write_event_csv(rows, EVENT_CSV)
    draw_event_comparison(rows, event_figure)
    draw_unselected_ap(ap_minutes, selected, events)
    differences = [abs(row["post_minus_pre_ap"]) for row in rows]
    outside = ap_minutes[~selected]
    print({
        "events": len(rows),
        "pre_post_median_abs_difference_ap": float(np.median(differences)),
        "events_with_abs_difference_at_most_5": sum(value <= 5 for value in differences),
        "outside_minutes": len(outside),
        "outside_median_ap": float(np.median(outside)),
        "outside_max_ap": float(np.max(outside)),
        "event_csv": str(EVENT_CSV),
        "figures": [str(event_figure), str(outside_figure)],
    })


if __name__ == "__main__":
    main()
