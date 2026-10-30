"""Read the frozen M1 density pairs and constants for a variable-tau trial."""

import csv
import math
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from load_m2_orbit_inputs import MINUTE_US
from phases.phase3.code.calc_h_tau import phase_support


PREDICTION = Path("phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
H_TAU = Path("phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite")
GRID = Path("phases/phase3/data/analysis/phase3_tau_grid_005h_exploratory.csv")
M1_TAU_HOURS = 4.65


def read_m1_gain() -> float:
    """Input: frozen M1 tau grid CSV. Output: gain at tau=4.65 h in 1/nT."""
    with GRID.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if float(row["tau_hours"]) == M1_TAU_HOURS:
                return float(row["gain_per_nt"])
    raise ValueError("M1 gain at tau=4.65 h is missing")


def read_m1_events(minute_times: np.ndarray) -> tuple[list[dict], float]:
    """Input: [continuous SME minute epochs]. Output: [M1 event inputs], gain."""
    uri = f"file:{H_TAU.resolve().as_posix()}?mode=ro"
    prediction_uri = f"file:{PREDICTION.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        database.execute("ATTACH DATABASE ? AS prediction", (prediction_uri,))
        fixed_r = dict(database.execute(
            "SELECT storm_id,r_candidate FROM prediction.phase3_25storm_overview"
        ))
        events = []
        for storm_id, r_value in fixed_r.items():
            rows = database.execute("""
                SELECT h.time_us,h.u_rel_rad,h.paired_sample_count,
                       h.phase_is_valid_80pct,p.h_phase_nt,
                       p.rho_l2_phase_kg_m3,p.rho_msis_quiet_phase_kg_m3
                FROM phase3_h_tau_minute AS h
                LEFT JOIN prediction.phase3_prediction_minute AS p
                  ON h.storm_id=p.storm_id AND h.time_us=p.time_us
                WHERE h.storm_id=? ORDER BY h.time_us
            """, (storm_id,)).fetchall()
            times = np.array([row[0] for row in rows], dtype=np.int64)
            phases = np.array([row[1] for row in rows])
            pairs = np.array([row[2] for row in rows], dtype=np.int8)
            support = phase_support(phases, pairs)
            valid = np.array([row[3] == 1 for row in rows])
            if not np.array_equal(valid, support["valid"]):
                raise ValueError(f"Phase validity changed for {storm_id}")
            indexes = (times - minute_times[0]) // MINUTE_US
            if (np.any(indexes < 0) or np.any(indexes >= len(minute_times))
                    or not np.array_equal(minute_times[indexes], times)):
                raise ValueError(f"SME minute time mismatch for {storm_id}")
            l2 = np.array([row[5] for row in rows if row[3] == 1])
            quiet = np.array([row[6] for row in rows if row[3] == 1])
            original_h = np.array([row[4] for row in rows if row[3] == 1])
            if (r_value <= 0 or np.any(l2 <= 0) or np.any(quiet <= 0)
                    or not np.isfinite(original_h).all()):
                raise ValueError(f"Invalid M1 input for {storm_id}")
            events.append({
                "storm_id": storm_id,
                "r": r_value,
                "times": times,
                "u_rel_rad": phases,
                "minute_index": indexes,
                "pairs": pairs,
                "support": support,
                "anomaly": np.log(l2 / quiet) - math.log(r_value),
                "rho_quiet": quiet,
                "rho_l2": l2,
                "original_h": original_h,
            })
    if len(events) != 25:
        raise ValueError(f"Expected 25 events, found {len(events)}")
    return events, read_m1_gain()
