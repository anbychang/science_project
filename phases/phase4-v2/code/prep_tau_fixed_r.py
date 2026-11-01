"""Save the Phase 4 v2 fixed-tau event R values under an explicit name."""

import sqlite3
from contextlib import closing
from pathlib import Path


SOURCE = Path("phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite")
ALGORITHM_VERSION = "phase4_v2_tau_fixed_r_475_v1"
EXPECTED_EVENTS = 25
EXPECTED_MINUTES = 214_907
TAU_FIXED_HOURS = 4.75


def save_tau_fixed_r() -> None:
    """Input: existing v2 event/minute tables. Output: keyed tau-fixed R table in v2 SQLite."""
    with closing(sqlite3.connect(SOURCE)) as database:
        if database.execute("""
            SELECT 1 FROM sqlite_master WHERE type='table'
            AND name='phase4_v2_tau_fixed_r_v1'
        """).fetchone():
            raise FileExistsError("Fixed-tau R table already exists; refusing to replace it.")
        events = database.execute("""
            SELECT storm_id,r_fit,tau_hours
            FROM phase4_v2_events ORDER BY storm_id
        """).fetchall()
        minute_count, mismatches = database.execute("""
            SELECT count(*),sum(CASE WHEN m.r_fit!=e.r_fit OR
                m.tau_hours!=e.tau_hours OR m.gain_per_nt!=e.gain_per_nt
                THEN 1 ELSE 0 END)
            FROM phase4_v2_minute AS m
            JOIN phase4_v2_events AS e USING (storm_id)
        """).fetchone()
        if (len(events) != EXPECTED_EVENTS or minute_count != EXPECTED_MINUTES
                or mismatches or any(tau != TAU_FIXED_HOURS or not 0 < r_fit < 2
                                  for _, r_fit, tau in events)):
            raise ValueError("Phase 4 v2 event parameters do not match the minute output.")
        with database:
            database.execute("""
                CREATE TABLE phase4_v2_tau_fixed_r_v1 (
                    storm_id TEXT PRIMARY KEY,
                    r_k_tau_fixed REAL NOT NULL CHECK(r_k_tau_fixed>0 AND r_k_tau_fixed<2),
                    algorithm_version TEXT NOT NULL
                )
            """)
            database.executemany("""
                INSERT INTO phase4_v2_tau_fixed_r_v1 VALUES (?,?,?)
            """, ((storm_id, r_fit, ALGORITHM_VERSION)
                  for storm_id, r_fit, _ in events))
            database.execute("""
                INSERT OR REPLACE INTO phase4_v2_metadata VALUES (?,?)
            """, ("tau_fixed_hours", str(TAU_FIXED_HOURS)))
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Phase 4 v2 SQLite integrity check failed.")
    print(f"Saved {len(events)} fixed-tau R values in {SOURCE}")


if __name__ == "__main__":
    save_tau_fixed_r()
