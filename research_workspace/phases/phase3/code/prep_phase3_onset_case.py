"""Show SME forcing and uninterrupted response around one storm."""

from datetime import timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from research_workspace.phases.phase3.code.prep_phase3_anytime_quiet_pairs import source_symh_and_extrema
from research_workspace.phases.phase3.code.prep_phase3_h10_quiet_pairs import filtered_sme_history
from research_workspace.phases.phase3.code.prep_phase3_sme_check import (
    FIRST_TIME, MINUTES_PER_DAY, SOURCE, event_center, read_source,
)


STORM_ID = "S20260120T1152"
REPORT = Path("research_workspace/phases/phase3/figures/onset_case_20260120.png")


def main() -> None:
    """Input: frozen 3-year SME and SYM-H. Output: one onset inspection PNG."""
    sme, events = read_source(SOURCE)
    symh, extrema = source_symh_and_extrema(events, len(sme))
    filtered_response = filtered_sme_history(sme)
    t0_us = dict(events)[STORM_ID]
    center = event_center(t0_us)
    start = center - 3 * MINUTES_PER_DAY
    end = center + MINUTES_PER_DAY
    times = [FIRST_TIME + timedelta(minutes=index) for index in range(start, end)]
    t0 = FIRST_TIME + timedelta(minutes=center)
    first_minimum = FIRST_TIME + timedelta(minutes=extrema[STORM_ID][0])

    figure, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True,
                                     constrained_layout=True)
    axes[0].plot(times, sme[start:end], linewidth=0.6, color="#2563eb")
    axes[0].axhline(65, color="#64748b", linestyle="--", linewidth=1)
    axes[0].set(ylabel="SME (nT)", title="2026-01-20: inspect first sustained driver")
    axes[1].plot(times, filtered_response[start:end], linewidth=1,
                 color="#d97706")
    axes[1].axhline(0, color="#64748b", linestyle="--", linewidth=1)
    axes[1].set(ylabel="H, tau=10 h (nT)")
    axes[2].plot(times, symh[start:end], linewidth=0.9, color="#7c3aed")
    axes[2].set(ylabel="SYM-H (nT)", xlabel="UTC")
    for axis in axes:
        axis.axvline(first_minimum, color="#dc2626", linestyle=":",
                     linewidth=1.2, label="first strong SYM-H minimum")
        axis.axvline(t0, color="#111827", linestyle="--", linewidth=1.2,
                     label="event t0")
        axis.grid(alpha=0.2)
    axes[0].legend(loc="upper left", fontsize=8)
    axes[2].xaxis.set_major_locator(mdates.HourLocator(interval=12))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    figure.autofmt_xdate()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(REPORT, dpi=170)
    plt.close(figure)
    print(REPORT)


if __name__ == "__main__":
    main()
