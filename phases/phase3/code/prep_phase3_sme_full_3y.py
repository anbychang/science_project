"""Plot the full three-year SME series with the selected storm events."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from phases.phase3.code.prep_phase3_sme_check import FIRST_TIME, SOURCE, read_source


FIGURE = Path("phases/phase3/figures/sme_full_3y_storms.png")
MIN_VALID_MINUTES_PER_HOUR = 45


def hourly_sme_median(minute_sme: np.ndarray) -> np.ndarray:
    """Input: [1-minute SME nT]. Output: [hourly median SME nT or NaN]."""
    hours = minute_sme.reshape(-1, 60)
    medians = np.full(len(hours), np.nan)
    for index, values in enumerate(hours):
        valid = values[np.isfinite(values)]
        if len(valid) >= MIN_VALID_MINUTES_PER_HOUR:
            medians[index] = np.median(valid)
    return medians


def draw_three_years(
    hourly_sme: np.ndarray, events: list[tuple[str, int]], path: Path
) -> None:
    """Input: [hourly SME], [(storm_id, t0_us)], PNG path. Output: saved figure."""
    hours = [FIRST_TIME + timedelta(hours=index) for index in range(len(hourly_sme))]
    valid_hours = np.flatnonzero(np.isfinite(hourly_sme))
    data_end = hours[int(valid_hours[-1])] + timedelta(hours=1)
    figure, axes = plt.subplots(3, 1, figsize=(17, 10), constrained_layout=True)

    for year_index, axis in enumerate(axes):
        start = datetime(2023 + year_index, 7, 1, tzinfo=timezone.utc)
        end = datetime(2024 + year_index, 7, 1, tzinfo=timezone.utc)
        axis.plot(hours, hourly_sme, color="#195ca8", linewidth=0.65)
        for number, (_, time_us) in enumerate(events, start=1):
            t0 = datetime.fromtimestamp(time_us / 1_000_000, timezone.utc)
            if start <= t0 < end:
                axis.axvspan(t0 - timedelta(days=2), t0 + timedelta(days=4),
                            color="#e8a13a", alpha=0.19, linewidth=0)
                axis.axvline(t0, color="#a4540b", linewidth=0.8)
                axis.text(t0, 1.01, str(number), transform=axis.get_xaxis_transform(),
                          ha="center", va="bottom", fontsize=7, color="#783a08")
        if data_end < end:
            axis.axvspan(data_end, end, color="#a5acb6", alpha=0.25, linewidth=0)
            axis.text(data_end + timedelta(days=5), 1800, "SME unavailable",
                      color="#525a65", fontsize=9)
        axis.set(xlim=(start, end), ylim=(0, 3500), ylabel="SME (nT)")
        axis.set_yscale("symlog", linthresh=50)
        axis.set_yticks([0, 50, 100, 200, 500, 1000, 2000, 3500])
        axis.yaxis.set_major_formatter(mticker.ScalarFormatter())
        axis.set_title(f"{start:%Y-%m-%d} to {end:%Y-%m-%d}", loc="left", fontsize=11)
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m", tz=timezone.utc))
        axis.grid(axis="y", alpha=0.25)

    figure.suptitle("SuperMAG SME, full three-year series and 25 selected storms", fontsize=14)
    axes[-1].set_xlabel(
        "UTC | hourly median of 1-minute SME | orange band: t0 - 2 to + 4 days | line: t0 | number: storm order"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=190)
    plt.close(figure)


def main() -> None:
    """Input: frozen P2.2 SQLite. Output: three-year SME PNG and counts."""
    minute_sme, events = read_source(SOURCE)
    if FIGURE.exists():
        raise FileExistsError(f"Refusing to overwrite {FIGURE}.")
    hourly_sme = hourly_sme_median(minute_sme)
    draw_three_years(hourly_sme, events, FIGURE)
    print({"figure": str(FIGURE), "storms": len(events),
           "valid_hourly_points": int(np.isfinite(hourly_sme).sum())})


if __name__ == "__main__":
    main()
