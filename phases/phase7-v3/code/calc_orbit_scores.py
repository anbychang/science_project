"""Score each complete POD orbit interval against fixed decay curves."""

import math
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from phases.phase1.code.prep_10_phase_orbit_mean import phase_orbit_rows
from phases.phase7.code.load_phase7_two_storms import PHASE1R, read_only


ROOT = Path(os.environ.get("PHASE7_SCORE_ROOT", "phases/phase7-v3")) / "data/sqlite"
SOURCE = ROOT / "swarm_a_phase7_decay_v1.sqlite"
OUTPUT = ROOT / "swarm_a_orbit_scores_v1.sqlite"
MINUTE_US = 60_000_000
VERSION = "phase7_complete_orbit_interval_score_v1"


def orbit_rows(connection, start_us, end_us):
    """Input: Phase 1R connection and UTC bounds. Output: [complete POD orbit rows]."""
    rows = connection.execute("""
        SELECT q.chunk_id,m.time_us,m.mean_semi_major_axis_m,
               m.mean_argument_of_perigee_rad,m.mean_anomaly_rad
        FROM swarm_a_mean_orbit_elements_v1 m
        JOIN swarm_a_pod_quality q ON q.time_us=m.time_us
        WHERE m.time_us>=? AND m.time_us<=? AND q.is_usable=1
          AND q.chunk_id IS NOT NULL AND m.rejection_reason IS NULL
        ORDER BY q.chunk_id,m.time_us
    """, (start_us - 6 * 3_600_000_000, end_us)).fetchall()
    return [row for row in phase_orbit_rows(rows) if start_us <= row[0] <= end_us]


def score_event(storm_id, decay, pod):
    """Input: event ID, minute decay rows, POD connection. Output: [orbit scores]."""
    first, last = decay[0][0], decay[-1][0]
    orbits = orbit_rows(pod, first, last)
    by_time = {row[0]: row for row in decay}
    scored = []
    for earlier, later in zip(orbits, orbits[1:]):
        start_us = ((earlier[0] + 30_000_000) // MINUTE_US) * MINUTE_US
        end_us = ((later[0] + 30_000_000) // MINUTE_US) * MINUTE_US
        start, end = by_time.get(start_us), by_time.get(end_us)
        if start is None or end is None or start[1] != end[1] or earlier[12] != later[12]:
            continue
        if end[2] - start[2] != (end_us - start_us) // MINUTE_US:
            continue
        observed = later[2] - earlier[2]
        m0 = end[3] - start[3]
        ridge = end[4] - start[4]
        scored.append((storm_id, earlier[0], later[0], start_us, end_us,
                       observed, m0, ridge, m0 - observed, ridge - observed,
                       VERSION))
    return scored


def write_scores():
    """Input: Phase 1R and decay SQLite. Output: new orbit score SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    with closing(read_only(SOURCE)) as decay_db, closing(read_only(PHASE1R)) as pod:
        events = [row[0] for row in decay_db.execute(
            "SELECT storm_id FROM phase7_decay_event_v1 ORDER BY storm_id")]
        scores = []
        for storm_id in events:
            minutes = decay_db.execute("""
                SELECT time_us,block_id,(time_us / 60000000),
                       predicted_m0_covered_delta_a_m,
                       predicted_ridge_covered_delta_a_m
                FROM phase7_decay_minute_v1 WHERE storm_id=? ORDER BY time_us
            """, (storm_id,)).fetchall()
            scores.extend(score_event(storm_id, minutes, pod))
    with closing(sqlite3.connect(OUTPUT)) as result:
        result.execute("""CREATE TABLE orbit_score_v1 (
            storm_id TEXT NOT NULL, pod_start_time_us INTEGER NOT NULL,
            pod_end_time_us INTEGER NOT NULL, model_start_time_us INTEGER NOT NULL,
            model_end_time_us INTEGER NOT NULL, observed_delta_a_m REAL NOT NULL,
            m0_delta_a_m REAL NOT NULL, ridge_delta_a_m REAL NOT NULL,
            m0_error_m REAL NOT NULL, ridge_error_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY(storm_id,pod_end_time_us))""")
        result.executemany("INSERT INTO orbit_score_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?)", scores)
        result.execute("""CREATE TABLE orbit_event_score_v1 (
            storm_id TEXT PRIMARY KEY, orbit_count INTEGER NOT NULL,
            m0_mae_m REAL NOT NULL, ridge_mae_m REAL NOT NULL,
            m0_rmse_m REAL NOT NULL, ridge_rmse_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL)""")
        for storm_id in events:
            rows = [row for row in scores if row[0] == storm_id]
            if not rows:
                raise ValueError(f"No complete orbit intervals: {storm_id}")
            m0_errors = [row[8] for row in rows]
            ridge_errors = [row[9] for row in rows]
            n = len(rows)
            result.execute("INSERT INTO orbit_event_score_v1 VALUES (?,?,?,?,?,?,?)", (
                storm_id, n, sum(map(abs, m0_errors)) / n,
                sum(map(abs, ridge_errors)) / n,
                math.sqrt(sum(x*x for x in m0_errors) / n),
                math.sqrt(sum(x*x for x in ridge_errors) / n), VERSION))
        if result.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Orbit score SQLite integrity check failed")
        result.commit()
    return OUTPUT


if __name__ == "__main__":
    print(write_scores())
