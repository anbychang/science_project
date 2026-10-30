"""Stress-test Trial6 at t0 and the strongest separate SYM-H variation."""

import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from calc_trial6_ridge import evaluate_block, load_rows, score, write_csv


ROOT = Path("phases/phase4-trial6")
SOURCE = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
PREDICTIONS = ROOT / "data/analysis/trial6_stress_predictions.csv"
METRICS = ROOT / "data/analysis/trial6_stress_metrics.csv"
HOUR_US = 3_600_000_000
MINUTE_US = 60_000_000
BLOCK_US = 6 * HOUR_US


def load_activity() -> dict[str, dict]:
    """Input: frozen P2.6 SQLite. Output: {storm: {t0_us, minute_us, symh_nt}}."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        storms = {storm_id: {"t0_us": t0_us, "minute_us": [], "symh_nt": []}
                  for storm_id, t0_us in database.execute(
                      "SELECT storm_id,t0_time_us FROM storm_event_t0_phase_v5"
                  )}
        minutes = database.execute("""
            SELECT storm_id,source_time_us,symh_nt FROM storm_minute_feature_v5
            ORDER BY storm_id,source_time_us
        """)
        for storm_id, time_us, symh_nt in minutes:
            storms[storm_id]["minute_us"].append(time_us)
            storms[storm_id]["symh_nt"].append(symh_nt)
    for storm_id, data in storms.items():
        data["minute_us"] = np.array(data["minute_us"], dtype=np.int64)
        data["symh_nt"] = np.array(data["symh_nt"], dtype=float)
        if not np.all(np.diff(data["minute_us"]) == MINUTE_US):
            raise ValueError(f"SYM-H minute series has gaps: {storm_id}")
        if not np.all(np.isfinite(data["symh_nt"])):
            raise ValueError(f"SYM-H series has missing values: {storm_id}")
    return storms


def most_variable_start(rows: list[dict], activity: dict) -> tuple[int, float]:
    """Input: [anchors], {t0_us, minute_us, symh_nt}. Output: (start_us, variation_nt)."""
    first_allowed = rows[0]["time_us"] + BLOCK_US
    last_allowed = rows[-1]["time_us"] - 2 * BLOCK_US
    t0_us = activity["t0_us"]
    minutes = activity["minute_us"]
    symh = activity["symh_nt"]
    best_start = None
    best_variation = -1.0
    for index in range(0, len(minutes) - 360 + 1, 60):
        start_us = int(minutes[index])
        if start_us < first_allowed or start_us > last_allowed:
            continue
        if start_us < t0_us + 3 * HOUR_US and start_us + BLOCK_US > t0_us - 3 * HOUR_US:
            continue
        half_hour_medians = np.median(symh[index:index + 360].reshape(12, 30), axis=1)
        variation = float(np.abs(np.diff(half_hour_medians)).sum())
        if variation > best_variation:
            best_start, best_variation = start_us, variation
    if best_start is None:
        raise ValueError(f"No separate six-hour SYM-H window: {rows[0]['storm_id']}")
    return best_start, best_variation


def run_stress(rows: list[dict], activity: dict) -> list[dict]:
    """Input: [anchors], {t0_us, minute_us, symh_nt}. Output: [two stress blocks]."""
    t0_start = activity["t0_us"] - 3 * HOUR_US
    variable_start, variation = most_variable_start(rows, activity)
    predictions = []
    for selection, start_us, variation_nt in (
        ("t0_centered", t0_start, None),
        ("symh_variation_outside_t0", variable_start, variation),
    ):
        elapsed_hours = (start_us - rows[0]["time_us"]) / HOUR_US
        block = evaluate_block(rows, elapsed_hours)
        if not block:
            raise ValueError(f"No valid {selection} block: {rows[0]['storm_id']}")
        for row in block:
            predictions.append({"selection": selection, "t0_time_us": activity["t0_us"],
                                "symh_variation_nt": variation_nt, **row})
    return predictions


def main() -> None:
    """Input: Trial6 features and P2.6 activity. Output: stress predictions/metrics CSVs."""
    if PREDICTIONS.exists() or METRICS.exists():
        raise FileExistsError("Trial6 stress output already exists.")
    anchors = load_rows()
    activity = load_activity()
    if set(anchors) != set(activity):
        raise ValueError("Activity and Trial6 anchor storms differ.")
    predictions = []
    metrics = []
    for storm_id, rows in anchors.items():
        storm_predictions = run_stress(rows, activity[storm_id])
        predictions.extend(storm_predictions)
        for selection in ("t0_centered", "symh_variation_outside_t0"):
            block = [row for row in storm_predictions if row["selection"] == selection]
            metrics.append({"selection": selection, "storm_id": storm_id,
                            "block_start_us": block[0]["block_start_us"],
                            "t0_time_us": activity[storm_id]["t0_us"],
                            "symh_variation_nt": block[0]["symh_variation_nt"],
                            **score(block)})
    for selection in ("t0_centered", "symh_variation_outside_t0"):
        selected = [row for row in predictions if row["selection"] == selection]
        metrics.append({"selection": selection, "storm_id": "all_storms",
                        "block_start_us": "", "t0_time_us": "", "symh_variation_nt": "",
                        **score(selected)})
    write_csv(PREDICTIONS, predictions)
    write_csv(METRICS, metrics)
    print(f"Scored {len(predictions)} anchors in 50 targeted blocks")


if __name__ == "__main__":
    main()
