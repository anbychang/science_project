"""Load Phase 2 SME and event phase support for the M2 orbit-tau trial."""

import math
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from phases.phase3.code.calc_h_tau import phase_support


PHASE2 = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
H_TAU = Path("phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite")
M2_RESIDUAL = Path("phases/phase3/data/sqlite/swarm_a_phase3_m2_residual_diagnostic_v1.sqlite")
FIXED_R = Path("phases/phase3-trial/data/sqlite/swarm_a_m2_alternating_v1.sqlite")
M0_SNAPSHOT = Path("phases/phase3-trial/data/sqlite/swarm_a_m2_r_grid_trial_v1.sqlite")
MINUTE_US = 60_000_000
TAU_CANDIDATES_HOURS = (0.5, 1.0, 2.0, 3.5, 5.0, 7.0, 10.0)


def read_minute_sme() -> tuple[np.ndarray, np.ndarray]:
    """Input: read-only P2.6 one-minute SME. Output: [minute time_us], [SME nT]."""
    uri = f"file:{PHASE2.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        total = database.execute("SELECT count(*) FROM geomag_1min_v2").fetchone()[0]
        source = np.fromiter(database.execute(
            "SELECT time_us,coalesce(sme_nt,0),sme_valid "
            "FROM geomag_1min_v2 ORDER BY time_us"
        ), dtype=[("time_us", "i8"), ("sme_nt", "f8"), ("valid", "i4")],
            count=total)
    valid_indexes = np.flatnonzero(source["valid"])
    if not len(valid_indexes):
        raise ValueError("SME has no valid observations")
    stop = int(valid_indexes[-1]) + 1
    if (not np.all(source["valid"][:stop])
            or not np.all(np.diff(source["time_us"][:stop]) == MINUTE_US)):
        raise ValueError("SME has a gap before the last usable event")
    return source["time_us"][:stop], source["sme_nt"][:stop]


def read_event_support(minute_times: np.ndarray) -> list[dict]:
    """Input: [continuous minute epochs]. Output: [Phase 2 event supports]."""
    uri = f"file:{H_TAU.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        database.execute("ATTACH DATABASE ? AS residual", (
            f"file:{M2_RESIDUAL.resolve().as_posix()}?mode=ro",))
        database.execute("ATTACH DATABASE ? AS trial", (
            f"file:{FIXED_R.resolve().as_posix()}?mode=ro",))
        fixed_r = dict(database.execute(
            "SELECT storm_id,final_r FROM trial.m2_alternation_storm"))
        events = []
        for storm_id, r_value in fixed_r.items():
            rows = database.execute("""
                SELECT h.time_us,h.u_rel_rad,h.paired_sample_count,
                       h.phase_is_valid_80pct,h.h_phase_tau_14_nt,
                       m.residual_log_density,
                       m.rho_m0_aligned_phase_kg_m3,
                       m.rho_l2_phase_kg_m3
                FROM phase3_h_tau_minute AS h
                LEFT JOIN residual.phase3_m2_residual_minute AS m
                  ON h.storm_id=m.storm_id AND h.time_us=m.time_us
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
            anomaly = np.array([row[5] for row in rows if row[3] == 1])
            old_response = np.array([row[4] for row in rows if row[3] == 1])
            rho_m0 = np.array([row[6] for row in rows if row[3] == 1])
            rho_l2 = np.array([row[7] for row in rows if row[3] == 1])
            if not np.isfinite(anomaly).all() or not np.isfinite(old_response).all():
                raise ValueError(f"Missing paired density or response for {storm_id}")
            events.append({"storm_id": storm_id, "r": r_value,
                           "times": times, "u_rel_rad": phases,
                           "minute_index": indexes, "pairs": pairs,
                           "support": support,
                           "anomaly": anomaly - math.log(r_value),
                           "rho_m0": rho_m0, "rho_l2": rho_l2,
                           "old_response": old_response})
    if len(events) != 25:
        raise ValueError(f"Expected 25 events, found {len(events)}")
    return events


def read_free_tau_events(minute_times: np.ndarray) -> tuple[list[dict], float]:
    """Input: [minute epochs]. Output: [events from trial M0 snapshot], fixed G."""
    uri = f"file:{H_TAU.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        database.execute("ATTACH DATABASE ? AS snapshot", (
            f"file:{M0_SNAPSHOT.resolve().as_posix()}?mode=ro",))
        database.execute("ATTACH DATABASE ? AS trial", (
            f"file:{FIXED_R.resolve().as_posix()}?mode=ro",))
        fixed_r = dict(database.execute(
            "SELECT storm_id,final_r FROM trial.m2_alternation_storm"))
        gain = database.execute(
            "SELECT gain_per_nt FROM trial.m2_alternation_global_grid "
            "ORDER BY rmse_log_density LIMIT 1"
        ).fetchone()[0]
        events = []
        for storm_id, r_value in fixed_r.items():
            rows = database.execute("""
                SELECT h.time_us,h.u_rel_rad,h.paired_sample_count,
                       h.phase_is_valid_80pct,h.h_phase_tau_14_nt,
                       s.rho_l2_phase_kg_m3,s.rho_m0_aligned_phase_kg_m3
                FROM phase3_h_tau_minute AS h
                LEFT JOIN snapshot.m2_r_trial_minute AS s
                  ON h.storm_id=s.storm_id AND h.time_us=s.time_us
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
            rho_l2 = np.array([row[5] for row in rows if row[3] == 1])
            rho_m0 = np.array([row[6] for row in rows if row[3] == 1])
            if np.any(rho_l2 <= 0) or np.any(rho_m0 <= 0):
                raise ValueError(f"Nonpositive density pair for {storm_id}")
            events.append({"storm_id": storm_id, "r": r_value,
                           "times": times, "u_rel_rad": phases,
                           "minute_index": indexes, "pairs": pairs,
                           "support": support,
                           "anomaly": np.log(rho_l2 / rho_m0) - math.log(r_value),
                           "rho_m0": rho_m0, "rho_l2": rho_l2,
                           "old_response": np.array(
                               [row[4] for row in rows if row[3] == 1])})
    if len(events) != 25:
        raise ValueError(f"Expected 25 events, found {len(events)}")
    return events, gain
