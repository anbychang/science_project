"""Make retrospective Phase 3 density predictions at fixed tau=4.65 hours."""

import csv
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from satellite_orbit.phase3.calc_h_tau import filtered_sme, phase_weighted_mean
from satellite_orbit.phase3.prep_exploratory_fit import (
    QUIET_DENSITY, load_r_candidates,
)
from satellite_orbit.phase3.prep_h_tau_phase import SOURCE, load_event, load_sme
from satellite_orbit.phase3.prep_tau_refinement import REPORT as FINE_GRID


OUTPUT = Path("data/sqlite/2023/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
REPORT = Path("output/report/phase3_prediction_tau465_exploratory.csv")
FIGURE = Path("output/image/Phase3/prediction_tau465_examples.png")
TAU_HOURS = 4.65
SME_REFERENCE_NT = 65.0


def load_global_gain() -> float:
    """Input: saved 0.05-hour grid CSV. Output: pooled G at tau=4.65 h."""
    with FINE_GRID.open(encoding="utf-8-sig", newline="") as source:
        matches = [float(row["gain_per_nt"]) for row in csv.DictReader(source)
                   if math.isclose(float(row["tau_hours"]), TAU_HOURS)]
    if len(matches) != 1 or matches[0] <= 0:
        raise ValueError("Expected one positive pooled gain at tau=4.65 hours.")
    return matches[0]


def load_events() -> tuple[np.ndarray, list[dict]]:
    """Input: read-only Phase 2 source. Output: [SME] and 25 phase supports."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        sme, first_time_us = load_sme(database)
        storm_ids = [row[0] for row in database.execute(
            "SELECT storm_id FROM storm_event_t0_phase_v5 ORDER BY t0_time_us")]
        events = [load_event(database, storm_id, first_time_us)
                  for storm_id in storm_ids]
    return sme, events


def attach_density(events: list[dict], r_by_storm: dict) -> None:
    """Input: phase supports and {storm: R}. Output: paired density arrays on events."""
    uri = f"file:{QUIET_DENSITY.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        for event in events:
            rows = database.execute("""
                SELECT time_us,rho_l2_phase_kg_m3,
                       rho_msis_quiet_phase_kg_m3,rho_msis_full_phase_kg_m3,
                       phase_is_valid_80pct
                FROM phase3_quiet_density_minute
                WHERE storm_id=? ORDER BY time_us
            """, (event["storm_id"],)).fetchall()
            times = np.fromiter((row[0] for row in rows), dtype=np.int64)
            valid = np.fromiter((row[4] for row in rows), dtype=bool)
            if not np.array_equal(times, event["time_us"]) or not np.array_equal(
                valid, event["support"]["valid"]
            ):
                raise ValueError(f"Density and phase support differ: {event['storm_id']}")
            paired = [row for row in rows if row[4]]
            event["valid_time_us"] = times[valid]
            event["l2"] = np.array([row[1] for row in paired], dtype=float)
            event["quiet"] = np.array([row[2] for row in paired], dtype=float)
            event["full"] = np.array([row[3] for row in paired], dtype=float)
            event["r"] = r_by_storm[event["storm_id"]]
            if not all(np.isfinite(event[name]).all()
                       and np.all(event[name] > 0)
                       for name in ("l2", "quiet", "full")):
                raise ValueError(f"Nonpositive or missing paired density: {event['storm_id']}")
            event["z"] = np.log(event["l2"] / event["quiet"]) - math.log(event["r"])


def attach_response(events: list[dict], sme: np.ndarray) -> None:
    """Input: event supports and continuous SME. Output: phase H at tau=4.65 h."""
    response = filtered_sme(sme, TAU_HOURS) - SME_REFERENCE_NT
    for event in events:
        phase = phase_weighted_mean(response[event["minute_index"]],
                                    event["pair_count"], event["support"])
        event["h"] = phase[event["support"]["valid"]]
        event["cross"] = float(event["h"] @ event["z"])
        event["h_squared"] = float(event["h"] @ event["h"])


def predict_events(events: list[dict], pooled_gain: float) -> list[dict]:
    """Input: aligned events and pooled gain. Output: event scores and predictions."""
    total_cross = sum(event["cross"] for event in events)
    total_h_squared = sum(event["h_squared"] for event in events)
    if not math.isclose(total_cross / total_h_squared, pooled_gain,
                        rel_tol=1e-9, abs_tol=1e-10):
        raise ValueError("Fixed-tau gain differs from the saved fine grid.")
    rows = []
    for event in events:
        held_out_gain = ((total_cross - event["cross"])
                         / (total_h_squared - event["h_squared"]))
        if held_out_gain <= 0:
            raise ValueError(f"Nonpositive held-out gain: {event['storm_id']}")
        event["gain_held_out"] = held_out_gain
        event["m1_all"] = (event["quiet"] * event["r"]
                           * np.exp(pooled_gain * event["h"]))
        event["m1_held_out"] = (event["quiet"] * event["r"]
                                * np.exp(held_out_gain * event["h"]))
        scores = {}
        for name in ("m1_all", "m1_held_out", "full"):
            error = np.log(event["l2"] / event[name])
            scores[f"{name}_rmse_log_density"] = float(np.sqrt(np.mean(error ** 2)))
        rows.append({"storm_id": event["storm_id"],
                     "valid_minutes": len(event["h"]),
                     "tau_hours": TAU_HOURS,
                     "r_candidate": event["r"],
                     "gain_pooled_per_nt": pooled_gain,
                     "gain_held_out_per_nt": held_out_gain,
                     **scores,
                     "status": "retrospective_provisional_R"})
    return rows


def save_predictions(events: list[dict]) -> None:
    """Input: events with densities and predictions. Output: keyed Phase 3 SQLite."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="phase3_prediction_tau465.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE phase3_prediction_minute (
                    storm_id TEXT NOT NULL,
                    time_us INTEGER NOT NULL,
                    h_phase_nt REAL NOT NULL,
                    rho_l2_phase_kg_m3 REAL NOT NULL,
                    rho_msis_quiet_phase_kg_m3 REAL NOT NULL,
                    rho_msis_full_phase_kg_m3 REAL NOT NULL,
                    rho_m1_pooled_phase_kg_m3 REAL NOT NULL,
                    rho_m1_held_out_phase_kg_m3 REAL NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id,time_us)
                );
                CREATE TABLE phase3_prediction_metadata (
                    name TEXT PRIMARY KEY,value TEXT NOT NULL
                );
            """)
            database.executemany("INSERT INTO phase3_prediction_metadata VALUES (?,?)", (
                ("tau_hours", str(TAU_HOURS)),
                ("sme_reference_nt", str(SME_REFERENCE_NT)),
                ("evaluation", "retrospective; provisional R; centered phase; centered F10.7A"),
            ))
            for event in events:
                data = zip(event["valid_time_us"], event["h"], event["l2"],
                           event["quiet"], event["full"], event["m1_all"],
                           event["m1_held_out"], strict=True)
                with database:
                    database.executemany(
                        "INSERT INTO phase3_prediction_minute VALUES (?,?,?,?,?,?,?,?,?)",
                        ((event["storm_id"], int(time_us),
                          *(float(value) for value in values),
                          "phase3_prediction_tau465_exploratory_v1")
                         for time_us, *values in data),
                    )
            expected = sum(len(event["h"]) for event in events)
            actual = database.execute(
                "SELECT count(*) FROM phase3_prediction_minute").fetchone()[0]
            if actual != expected or database.execute(
                "PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Phase 3 prediction output failed integrity checks.")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def draw_examples(events: list[dict]) -> None:
    """Input: predicted event arrays. Output: two retrospective example panels."""
    chosen = ("S20240511T0214", "S20260120T1152")
    figure, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    for axis, storm_id in zip(axes, chosen, strict=True):
        event = next(row for row in events if row["storm_id"] == storm_id)
        selected = slice(None, None, 30)
        times = [datetime.fromtimestamp(value / 1_000_000, timezone.utc)
                 for value in event["valid_time_us"][selected]]
        for name, label, color in (
            ("l2", "Swarm L2", "#111827"),
            ("full", "M0 raw", "#64748b"),
            ("m1_held_out", "M1 held-out G", "#2563eb"),
        ):
            axis.plot(times, event[name][selected] * 1e12,
                      color=color, label=label, linewidth=1)
        axis.set(ylabel="Density (1e-12 kg/m3)",
                 title=f"{storm_id[1:9]}: retrospective phase means")
        axis.grid(alpha=0.2)
    axes[0].legend()
    axes[-1].set_xlabel("UTC time")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: existing Phase 2/3 data. Output: retrospective predictions and QC."""
    if OUTPUT.exists() or REPORT.exists() or FIGURE.exists():
        raise FileExistsError("Tau=4.65 prediction output already exists.")
    sme, events = load_events()
    attach_density(events, load_r_candidates())
    attach_response(events, sme)
    rows = predict_events(events, load_global_gain())
    save_predictions(events)
    with REPORT.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    draw_examples(events)
    print(f"Saved retrospective predictions for {len(events)} storms and "
          f"{sum(row['valid_minutes'] for row in rows)} valid phase minutes")


if __name__ == "__main__":
    main()
