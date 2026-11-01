"""Combine the five selected orbit-score events in a separate SQLite."""

import sqlite3
from contextlib import closing
from pathlib import Path


SOURCES = (
    Path("phases/phase7/runs/three_storms/data/sqlite/swarm_a_orbit_scores_v1.sqlite"),
    Path("phases/phase7/runs/earlier_storms/data/sqlite/swarm_a_orbit_scores_v1.sqlite"),
)
OUTPUT = Path("phases/phase7/data/sqlite/swarm_a_five_storm_orbit_scores_v1.sqlite")
EXCLUDED_STORM_ID = "S20180826T0711"
VERSION = "phase7_five_storm_orbit_score_selection_v1"


def write_five_scores():
    """Input: two orbit-score SQLite files. Output: new five-event SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    with closing(sqlite3.connect(OUTPUT)) as result:
        result.execute("""CREATE TABLE orbit_score_v1 (
            storm_id TEXT NOT NULL, pod_start_time_us INTEGER NOT NULL,
            pod_end_time_us INTEGER NOT NULL, model_start_time_us INTEGER NOT NULL,
            model_end_time_us INTEGER NOT NULL, observed_delta_a_m REAL NOT NULL,
            m0_delta_a_m REAL NOT NULL, ridge_delta_a_m REAL NOT NULL,
            m0_error_m REAL NOT NULL, ridge_error_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY(storm_id,pod_end_time_us))""")
        for source in SOURCES:
            with closing(sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True)) as old:
                rows = old.execute("""
                    SELECT * FROM orbit_score_v1 WHERE storm_id!=?
                    ORDER BY storm_id,pod_end_time_us
                """, (EXCLUDED_STORM_ID,)).fetchall()
            result.executemany("INSERT INTO orbit_score_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        result.execute("""CREATE TABLE orbit_event_score_v1 (
            storm_id TEXT PRIMARY KEY, orbit_count INTEGER NOT NULL,
            m0_mae_m REAL NOT NULL, ridge_mae_m REAL NOT NULL,
            m0_rmse_m REAL NOT NULL, ridge_rmse_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL)""")
        result.execute("""INSERT INTO orbit_event_score_v1
            SELECT storm_id,COUNT(*),AVG(ABS(m0_error_m)),AVG(ABS(ridge_error_m)),
                   SQRT(AVG(m0_error_m*m0_error_m)),
                   SQRT(AVG(ridge_error_m*ridge_error_m)),?
            FROM orbit_score_v1 GROUP BY storm_id""", (VERSION,))
        result.execute("""CREATE TABLE orbit_score_metadata_v1 (
            name TEXT PRIMARY KEY,value TEXT NOT NULL)""")
        result.executemany("INSERT INTO orbit_score_metadata_v1 VALUES (?,?)", (
            ("algorithm_version", VERSION),
            ("excluded_storm_id", EXCLUDED_STORM_ID),
            ("source_v2", str(SOURCES[0])),
            ("source_v3", str(SOURCES[1])),
        ))
        if result.execute("SELECT COUNT(*) FROM orbit_event_score_v1").fetchone()[0] != 5:
            raise ValueError("Expected five events")
        if result.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Five-storm SQLite integrity check failed")
        result.commit()
    return OUTPUT


if __name__ == "__main__":
    print(write_five_scores())
