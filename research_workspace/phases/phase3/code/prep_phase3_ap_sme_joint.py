"""Check whether low observed ap also identifies low SME in the three-year pilot."""

import numpy as np

from research_workspace.phases.phase3.code.prep_phase3_ap_check import AP_SOURCE, read_ap_minutes
from research_workspace.phases.phase3.code.prep_phase3_sme_check import (
    FIRST_TIME,
    MINUTES_PER_DAY,
    SOURCE,
    event_center,
    read_source,
)


def sme_distribution(selection: np.ndarray, sme: np.ndarray) -> dict:
    """Input: [selected minutes], [SME nT]. Output: conditional SME summary."""
    values = sme[selection & np.isfinite(sme)]
    quantiles = np.quantile(values, [0.25, 0.5, 0.75, 0.9])
    return {
        "valid_minutes": len(values),
        "sme_q25_median_q75_p90_nT": quantiles.round(1).tolist(),
        "fraction_sme_above_100_nT": round(float(np.mean(values > 100)), 3),
    }


def pre_event_coverage(
    selection: np.ndarray, sme: np.ndarray, events: list[tuple[str, int]]
) -> dict:
    """Input: [selected minutes], [SME], [events]. Output: pre-window counts."""
    counts = []
    medians = []
    for _, time_us in events:
        center = event_center(time_us)
        pre_window = slice(center - 5 * MINUTES_PER_DAY, center - 2 * MINUTES_PER_DAY)
        eligible = selection[pre_window] & np.isfinite(sme[pre_window])
        counts.append(int(eligible.sum()))
        if eligible.any():
            medians.append(float(np.median(sme[pre_window][eligible])))
    return {
        "candidate_window": "t0 - 5 to - 2 days",
        "events_without_eligible_minutes": counts.count(0),
        "eligible_minutes_min_median_max": [
            min(counts), float(np.median(counts)), max(counts)
        ],
        "event_sme_medians_min_median_max_nT": [
            round(min(medians), 1), round(float(np.median(medians)), 1),
            round(max(medians), 1)
        ],
    }


def longest_pre_event_runs(
    selection: np.ndarray, events: list[tuple[str, int]]
) -> dict:
    """Input: [selected minutes], [events]. Output: consecutive pre-window counts."""
    longest_runs = []
    for _, time_us in events:
        center = event_center(time_us)
        pre_window = selection[
            center - 5 * MINUTES_PER_DAY:center - 2 * MINUTES_PER_DAY
        ]
        current_run = 0
        longest_run = 0
        for eligible in pre_window:
            current_run = current_run + 1 if eligible else 0
            longest_run = max(longest_run, current_run)
        longest_runs.append(longest_run)
    return {
        "events_with_12h_continuous": sum(run >= 720 for run in longest_runs),
        "longest_run_minutes_min_median_max": [
            min(longest_runs), float(np.median(longest_runs)), max(longest_runs)
        ],
    }


def main() -> None:
    """Input: frozen ap and SME sources. Output: conditional summaries on stdout."""
    ap, first_time = read_ap_minutes(AP_SOURCE)
    sme, events = read_source(SOURCE)
    if len(ap) != len(sme) or first_time != FIRST_TIME:
        raise ValueError("ap and SME minute grids are not aligned.")
    for label, selection in (("ap = 4", ap == 4), ("ap <= 4", ap <= 4)):
        print({"ap_condition": label, **sme_distribution(selection, sme)})
        print({"ap_condition": label, **pre_event_coverage(selection, sme, events),
               **longest_pre_event_runs(selection, events)})
    for sme_limit in (40, 100):
        selection = (ap <= 4) & np.isfinite(sme) & (sme <= sme_limit)
        print({
            "condition": f"ap <= 4 and SME <= {sme_limit} nT",
            **sme_distribution(selection, sme),
            **pre_event_coverage(selection, sme, events),
            **longest_pre_event_runs(selection, events),
        })


if __name__ == "__main__":
    main()
