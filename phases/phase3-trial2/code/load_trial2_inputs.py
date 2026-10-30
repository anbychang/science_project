"""Read frozen Phase 2 SME and Phase 3 M1 pairs for Trial 2."""

import math
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from phases.phase3.code.calc_h_tau import phase_support
from phases.phase3.code.prep_h_tau_phase import load_sme


PHASE2 = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
PHASE3_RESPONSE = Path("phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite")
PHASE3_PREDICTION = Path(
    "phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite"
)
MINUTE_US = 60_000_000
MAX_DELAY_MINUTES = 360


def load_continuous_sme() -> tuple[np.ndarray, np.ndarray]:
    """Input: frozen P2.6 SQLite. Output: [minute time_us], [SME nT]."""
    uri = f"file:{PHASE2.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        sme_nt, first_time_us = load_sme(database)
        last_valid_time_us = database.execute(
            "SELECT max(time_us) FROM geomag_1min_v2 WHERE sme_valid=1"
        ).fetchone()[0]
    if first_time_us + MINUTE_US * (len(sme_nt) - 1) != last_valid_time_us:
        raise ValueError("Continuous SME minute epochs have a time gap")
    minute_times = first_time_us + MINUTE_US * np.arange(len(sme_nt), dtype=np.int64)
    return minute_times, sme_nt


def load_events(minute_times: np.ndarray) -> list[dict]:
    """Input: [SME minute epochs]. Output: [25 M1-aligned event arrays]."""
    response_uri = f"file:{PHASE3_RESPONSE.resolve().as_posix()}?mode=ro"
    prediction_uri = f"file:{PHASE3_PREDICTION.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(response_uri, uri=True)) as database:
        database.execute("ATTACH DATABASE ? AS prediction", (prediction_uri,))
        r_by_storm = dict(database.execute(
            "SELECT storm_id,r_candidate FROM prediction.phase3_25storm_overview"
        ))
        events = []
        for storm_id, r_value in sorted(r_by_storm.items()):
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
            phase = np.array([row[1] for row in rows], dtype=float)
            pairs = np.array([row[2] for row in rows], dtype=np.int16)
            support = phase_support(phase, pairs)
            source_valid = np.array([row[3] == 1 for row in rows])
            if not np.array_equal(support["valid"], source_valid):
                raise ValueError(f"Changed phase support: {storm_id}")
            indexes = (times - minute_times[0]) // MINUTE_US
            if (np.any(indexes < MAX_DELAY_MINUTES)
                    or np.any(indexes >= len(minute_times))
                    or not np.array_equal(minute_times[indexes], times)):
                raise ValueError(f"Missing six-hour SME history: {storm_id}")
            l2 = np.array([row[5] for row in rows if row[3] == 1], dtype=float)
            quiet = np.array([row[6] for row in rows if row[3] == 1], dtype=float)
            original_h = np.array([row[4] for row in rows if row[3] == 1], dtype=float)
            if (r_value <= 0 or np.any(l2 <= 0) or np.any(quiet <= 0)
                    or not np.isfinite(original_h).all()):
                raise ValueError(f"Invalid M1 density pair: {storm_id}")
            anomaly = np.log(l2 / quiet) - math.log(r_value)
            events.append({
                "storm_id": storm_id,
                "r": float(r_value),
                "times": times,
                "u_rel_rad": phase,
                "minute_index": indexes,
                "pairs": pairs,
                "support": support,
                "anomaly": anomaly,
                "anomaly_squared": float(anomaly @ anomaly),
                "count": len(anomaly),
                "original_h": original_h,
                "rho_l2": l2,
                "rho_quiet": quiet,
            })
    if len(events) != 25:
        raise ValueError(f"Expected 25 events, found {len(events)}")
    return events
