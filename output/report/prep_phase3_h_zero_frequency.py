"""Measure how often the continuous SME response approaches zero."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from output.report.prep_phase3_ap_check import AP_SOURCE, read_ap_minutes
from output.report.prep_phase3_anytime_quiet_pairs import source_symh_and_extrema
from output.report.prep_phase3_sme_check import SOURCE, read_source
from satellite_orbit.phase3.calc_h_tau import filtered_sme


REFERENCES_NT = (65.0, 80.0, 250.0)
TAU_HOURS = (0.0, 1.0, 4.0, 10.0)
NEAR_ZERO_NT = 25.0
WARMUP_MINUTES = 3 * 1440
REPORT = Path("output/report/phase3_h_zero_frequency.csv")
EVENT_REPORT = Path("output/report/phase3_h_zero_before_events.csv")
IMAGE = Path("output/image/Phase3/h_zero_frequency.png")


def sustained_runs(near_zero: np.ndarray) -> tuple[int, int]:
    """Input: [near-zero minute mask]. Output: (runs at least 90 min, longest min)."""
    edges = np.diff(np.r_[False, near_zero, False].astype(int))
    lengths = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
    return int(np.count_nonzero(lengths >= 90)), int(lengths.max(initial=0))


def summarize(sme: np.ndarray, ap: np.ndarray) -> list[dict]:
    """Input: [valid SME], [ap] same length. Output: [frequency diagnostics]."""
    after_warmup = np.arange(len(sme)) >= WARMUP_MINUTES
    cohorts = {
        "all_valid": after_warmup,
        "low_current_activity": after_warmup & (ap <= 4) & (sme <= 100),
    }
    rows = []
    for tau_hours in TAU_HOURS:
        filtered = filtered_sme(sme, tau_hours)
        for reference_nt in REFERENCES_NT:
            response = filtered - reference_nt
            for name, mask in cohorts.items():
                selected = response[mask]
                near_zero = abs(selected) <= NEAR_ZERO_NT
                row = {
                    "tau_hours": tau_hours,
                    "sme_reference_nt": reference_nt,
                    "cohort": name,
                    "minutes": len(selected),
                    "median_h_nt": float(np.median(selected)),
                    "fraction_h_negative": float(np.mean(selected < 0)),
                    "fraction_abs_h_le_10nt": float(np.mean(abs(selected) <= 10)),
                    "fraction_abs_h_le_25nt": float(np.mean(near_zero)),
                    "fraction_abs_h_le_50nt": float(np.mean(abs(selected) <= 50)),
                }
                if name == "all_valid":
                    valid_response = response[after_warmup]
                    row["zero_crossings"] = int(np.count_nonzero(
                        np.signbit(valid_response[1:])
                        != np.signbit(valid_response[:-1])))
                    row["runs_abs_h_le_25nt_at_least_90min"], row[
                        "longest_abs_h_le_25nt_run_minutes"] = sustained_runs(
                            abs(valid_response) <= NEAR_ZERO_NT)
                else:
                    row["zero_crossings"] = ""
                    row["runs_abs_h_le_25nt_at_least_90min"] = ""
                    row["longest_abs_h_le_25nt_run_minutes"] = ""
                rows.append(row)
    return rows


def draw(rows: list[dict]) -> None:
    """Input: [frequency diagnostics]. Output: saved two-panel PNG."""
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4), sharey=True,
                                     constrained_layout=True)
    for axis, cohort in zip(axes, ("all_valid", "low_current_activity"),
                            strict=True):
        for reference_nt in REFERENCES_NT:
            subset = [row for row in rows if row["cohort"] == cohort
                      and row["sme_reference_nt"] == reference_nt]
            axis.plot([row["tau_hours"] for row in subset],
                      [100 * row["fraction_abs_h_le_25nt"] for row in subset],
                      marker="o", label=f"reference {reference_nt:g} nT")
        axis.set(title=("All valid minutes" if cohort == "all_valid"
                        else "Current ap <= 4 and SME <= 100 nT"),
                 xlabel="tau (hours)", xticks=TAU_HOURS, ylim=(0, 100))
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Minutes with |H| <= 25 nT (%)")
    axes[0].legend(fontsize=8)
    IMAGE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(IMAGE, dpi=180)
    plt.close(figure)


def event_lookback_rows(sme: np.ndarray, ap: np.ndarray,
                        events: list[tuple[str, int]]) -> list[dict]:
    """Input: [SME], [ap], [events]. Output: pre-minimum near-zero run QC."""
    _, extrema = source_symh_and_extrema(events, len(sme))
    response = filtered_sme(sme, 10) - 65
    low_response = abs(response) <= NEAR_ZERO_NT
    low_activity = low_response & (ap <= 4) & (sme <= 100)
    rows = []
    for storm_id, _ in events:
        first_minimum = extrema[storm_id][0]
        for lookback_days in (2, 7, 14):
            start = first_minimum - lookback_days * 1440
            if start < WARMUP_MINUTES:
                raise ValueError(f"Incomplete lookback for {storm_id}.")
            response_runs, response_longest = sustained_runs(
                low_response[start:first_minimum])
            activity_runs, activity_longest = sustained_runs(
                low_activity[start:first_minimum])
            rows.append({
                "storm_id": storm_id,
                "lookback_days_before_first_strong_minimum": lookback_days,
                "any_h10_near_zero_run_at_least_90min": response_runs > 0,
                "longest_h10_near_zero_run_minutes": response_longest,
                "any_h10_and_low_current_activity_run_at_least_90min": (
                    activity_runs > 0),
                "longest_h10_and_low_current_activity_run_minutes": (
                    activity_longest),
            })
    return rows


def main() -> None:
    """Input: frozen 3-year SME and ap. Output: diagnostic CSVs and PNG."""
    source_sme, events = read_source(SOURCE)
    source_ap, _ = read_ap_minutes(AP_SOURCE)
    valid_indices = np.flatnonzero(np.isfinite(source_sme))
    last_valid = int(valid_indices[-1]) + 1
    if len(valid_indices) != last_valid:
        raise ValueError("SME has an internal gap; continuous filter needs review.")
    if last_valid <= WARMUP_MINUTES:
        raise ValueError("Not enough valid SME for three-day warmup.")
    sme = source_sme[:last_valid]
    ap = source_ap[:last_valid]
    rows = summarize(sme, ap)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    event_rows = event_lookback_rows(sme, ap, events)
    with EVENT_REPORT.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(event_rows[0]))
        writer.writeheader()
        writer.writerows(event_rows)
    draw(rows)
    print(f"Saved {len(rows)} summary rows, {len(event_rows)} event rows and {IMAGE}")


if __name__ == "__main__":
    main()
