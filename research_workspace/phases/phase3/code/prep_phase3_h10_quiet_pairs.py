"""Repeat retrospective matching with low ten-hour SME response history."""

import csv
import math
from pathlib import Path

import numpy as np

from research_workspace.phases.phase3.code.prep_phase3_anytime_quiet_pairs import (
    SLOT_REPORT, paired_event_rows, save_rows, source_symh_and_extrema,
)
from research_workspace.phases.phase3.code.prep_phase3_sme_check import SOURCE, read_source


TAU_HOURS = 10
SME_REFERENCE_NT = 65
MAX_ABS_H_NT = 25
REPORT = Path("research_workspace/phases/phase3/data/analysis/phase3_anytime_quiet_pairs_h10_le25.csv")


def filtered_sme_history(sme: np.ndarray) -> np.ndarray:
    """Input: [one-minute SME]. Output: [ten-hour filtered SME anomaly, nT]."""
    alpha = math.exp(-1 / (60 * TAU_HOURS))
    state = float(sme[0] - SME_REFERENCE_NT)
    history = np.empty(len(sme))
    for index, value in enumerate(sme):
        if np.isfinite(value):
            state = alpha * state + (1 - alpha) * (float(value) - SME_REFERENCE_NT)
        history[index] = state
    return history


def load_quiet_slots(history: np.ndarray) -> list[dict]:
    """Input: [filtered SME anomaly]. Output: low-activity slots with small H."""
    with SLOT_REPORT.open(encoding="utf-8-sig", newline="") as source:
        slots = list(csv.DictReader(source))
    selected = []
    for slot in slots:
        start = int(slot["start_index"])
        end = int(slot["end_index"])
        slot["mean_h10_nt"] = float(np.mean(history[start:end]))
        if abs(slot["mean_h10_nt"]) <= MAX_ABS_H_NT:
            for field in ("start_index", "end_index"):
                slot[field] = int(slot[field])
            for field in ("observed_ap", "mean_sme_nt", "mean_log_density_ratio",
                          "density_ratio"):
                slot[field] = float(slot[field])
            selected.append(slot)
    return selected


def main() -> None:
    """Input: frozen SME and paired quiet slots. Output: H-screened event pairs."""
    sme, events = read_source(SOURCE)
    slots = load_quiet_slots(filtered_sme_history(sme))
    _, extrema = source_symh_and_extrema(events, len(sme))
    rows = paired_event_rows(events, extrema, slots)
    slot_by_time = {slot["start_utc"]: slot for slot in slots}
    for row in rows:
        row["pre_mean_h10_nt"] = slot_by_time[row["pre_start_utc"]]["mean_h10_nt"]
        row["post_mean_h10_nt"] = slot_by_time[row["post_start_utc"]]["mean_h10_nt"]
    save_rows(rows, REPORT)
    print(f"Saved {len(rows)} pairs from {len(slots)} low-H slots to {REPORT}")


if __name__ == "__main__":
    main()
