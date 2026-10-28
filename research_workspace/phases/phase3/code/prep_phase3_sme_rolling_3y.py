"""Compare past-only 30-day and 90-day SME means across the three-year record."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from research_workspace.phases.phase3.code.prep_phase3_sme_check import FIRST_TIME, SOURCE, read_source
from research_workspace.phases.phase3.code.prep_phase3_sme_full_3y import hourly_sme_median


FIGURE = Path("research_workspace/phases/phase3/figures/sme_rolling_30d_90d_3y.png")
MINUTES_PER_DAY = 1440
MINIMUM_COVERAGE = 0.95


def past_mean(minute_sme: np.ndarray, days: int) -> np.ndarray:
    """Input: [1-minute SME nT], past-day span. Output: [past-only mean nT or NaN]."""
    window = days * MINUTES_PER_DAY
    valid = np.isfinite(minute_sme)
    values = np.where(valid, minute_sme, 0.0)
    sums = np.concatenate(([0.0], np.cumsum(values)))
    counts = np.concatenate(([0], np.cumsum(valid)))
    result = np.full(len(minute_sme), np.nan)
    window_sums = sums[window:] - sums[:-window]
    window_counts = counts[window:] - counts[:-window]
    enough = window_counts >= MINIMUM_COVERAGE * window
    valid_end_indices = np.flatnonzero(enough) + window - 1
    result[valid_end_indices] = window_sums[enough] / window_counts[enough]
    return result


def draw_comparison(series: dict, events: list[tuple[str, int]]) -> None:
    """Input: {hourly series}, [(storm_id, t0_us)]. Output: saved comparison PNG."""
    hours = [FIRST_TIME + timedelta(hours=index) for index in range(len(series["SME"]))]
    last_valid = int(np.flatnonzero(np.isfinite(series["SME"]))[-1])
    data_end = hours[last_valid] + timedelta(hours=1)
    figure, axes = plt.subplots(3, 1, figsize=(17, 10), constrained_layout=True)

    for year_index, axis in enumerate(axes):
        start = datetime(2023 + year_index, 7, 1, tzinfo=timezone.utc)
        end = datetime(2024 + year_index, 7, 1, tzinfo=timezone.utc)
        axis.plot(hours, series["SME"], color="#8aa8ce", linewidth=0.55,
                  label="SME hourly median")
        axis.plot(hours, series["30 d"], color="#c66b16", linewidth=1.5,
                  label="Past 30 d mean")
        axis.plot(hours, series["90 d"], color="#522693", linewidth=1.7,
                  label="Past 90 d mean")
        for _, time_us in events:
            t0 = datetime.fromtimestamp(time_us / 1_000_000, timezone.utc)
            if start <= t0 < end:
                axis.axvspan(t0 - timedelta(days=2), t0 + timedelta(days=4),
                            color="#f4b650", alpha=0.15, linewidth=0)
        if data_end < end:
            axis.axvspan(data_end, end, color="#a5acb6", alpha=0.25, linewidth=0)
        axis.set(xlim=(start, end), ylim=(0, 3500), ylabel="SME (nT)")
        axis.set_yscale("symlog", linthresh=50)
        axis.set_yticks([0, 50, 100, 200, 500, 1000, 2000, 3500])
        axis.yaxis.set_major_formatter(mticker.ScalarFormatter())
        axis.set_title(f"{start:%Y-%m-%d} to {end:%Y-%m-%d}", loc="left", fontsize=11)
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m", tz=timezone.utc))
        axis.grid(axis="y", alpha=0.25)

    axes[0].legend(loc="upper right", ncol=3, frameon=False)
    figure.suptitle("SuperMAG SME and past-only rolling means", fontsize=14)
    axes[-1].set_xlabel(
        "UTC | means update hourly in this display | orange bands: selected storm windows | gray: no SME data"
    )
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=190)
    plt.close(figure)


def main() -> None:
    """Input: frozen P2.2 SQLite. Output: rolling-mean comparison PNG and counts."""
    if FIGURE.exists():
        raise FileExistsError(f"Refusing to overwrite {FIGURE}.")
    minute_sme, events = read_source(SOURCE)
    series = {
        "SME": hourly_sme_median(minute_sme),
        "30 d": past_mean(minute_sme, 30)[59::60],
        "90 d": past_mean(minute_sme, 90)[59::60],
    }
    for span in ("30 d", "90 d"):
        series[span][~np.isfinite(series["SME"])] = np.nan
    draw_comparison(series, events)
    print({
        "figure": str(FIGURE),
        "valid_30d_hours": int(np.isfinite(series["30 d"]).sum()),
        "valid_90d_hours": int(np.isfinite(series["90 d"]).sum()),
        "median_30d_nT": float(np.nanmedian(series["30 d"])),
        "median_90d_nT": float(np.nanmedian(series["90 d"])),
    })


if __name__ == "__main__":
    main()
