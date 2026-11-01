"""Compare Ridge-R density with Phase 4 V1, Phase 4 V2, and L2."""

import math
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np


ROOT = Path("phases/phase5-v2")
RIDGE = ROOT / "data/sqlite/storm_r_ridge_v21.sqlite"
V1 = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
V2 = Path("phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite")
OUTPUT = ROOT / "data/sqlite/storm_r_ridge_density_v1.sqlite"
ALGORITHM_VERSION = "storm_r_ridge_density_v1"
EXPECTED_MINUTES = 214_907


def read_only(path: Path) -> sqlite3.Connection:
    """Input: SQLite path. Output: read-only database connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def calculate_event(v1_rows: list[tuple], v2_rows: list[tuple],
                    prediction: dict) -> tuple[list[tuple], tuple]:
    """Input: aligned V1/V2 minute rows and Ridge R. Output: density rows, event log RMSE."""
    storm_id = prediction["storm_id"]
    if not v1_rows or len(v1_rows) != len(v2_rows):
        raise ValueError(f"V1/V2 minute count differs: {storm_id}")
    minute_rows = []
    squared_errors = [[], [], []]
    for v1_row, v2_row in zip(v1_rows, v2_rows, strict=True):
        time_us, l2_v1, quiet_v1, rho_v1 = v1_row
        v2_time_us, l2_v2, quiet_v2, rho_v2, h_phase_nt, gain_per_nt, r_fit = v2_row
        if (time_us != v2_time_us or l2_v1 != l2_v2 or quiet_v1 != quiet_v2
                or r_fit != prediction["r_fit"]):
            raise ValueError(f"V1/V2/Ridge minute mismatch: {storm_id}, {time_us}")
        rho_ridge = quiet_v2 * prediction["r_pred"] * math.exp(gain_per_nt * h_phase_nt)
        if not all(math.isfinite(value) and value > 0
                   for value in (l2_v2, rho_v1, rho_v2, rho_ridge)):
            raise ValueError(f"Invalid density: {storm_id}, {time_us}")
        minute_rows.append((storm_id, time_us, prediction["t0_time_us"], l2_v2,
                            rho_v1, rho_v2, rho_ridge, prediction["r_pred"],
                            ALGORITHM_VERSION))
        for errors, density in zip(squared_errors, (rho_v1, rho_v2, rho_ridge),
                                   strict=True):
            errors.append(math.log(l2_v2 / density) ** 2)
    score = (storm_id, prediction["fold_index"], len(minute_rows),
             *(math.sqrt(float(np.mean(errors))) for errors in squared_errors),
             ALGORITHM_VERSION)
    return minute_rows, score


def save_results() -> None:
    """Input: read-only V1/V2/Ridge SQLite. Output: new minute comparison SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with (closing(read_only(RIDGE)) as ridge,
          closing(read_only(V1)) as v1,
          closing(read_only(V2)) as v2,
          sqlite3.connect(OUTPUT) as database):
        predictions = {row[0]: {"storm_id": row[0], "fold_index": row[1],
                                "r_fit": row[2], "r_pred": row[3],
                                "t0_time_us": row[4]}
                       for row in ridge.execute("""
                           SELECT p.storm_id,p.fold_index,p.r_fit,p.r_pred,e.t0_time_us
                           FROM heldout_prediction p JOIN event_input e USING(storm_id)
                       """)}
        if len(predictions) != 25:
            raise ValueError("Expected 25 Ridge event predictions.")
        database.executescript("""
            CREATE TABLE density_comparison (
                storm_id TEXT NOT NULL, time_us INTEGER NOT NULL,
                t0_time_us INTEGER NOT NULL,
                rho_l2_phase_kg_m3 REAL NOT NULL,
                rho_phase4_v1_phase_kg_m3 REAL NOT NULL,
                rho_phase4_v2_phase_kg_m3 REAL NOT NULL,
                rho_ridge_phase_kg_m3 REAL NOT NULL,
                r_ridge REAL NOT NULL, algorithm_version TEXT NOT NULL,
                PRIMARY KEY(storm_id,time_us)
            );
            CREATE TABLE event_density_score (
                storm_id TEXT PRIMARY KEY, fold_index INTEGER NOT NULL,
                minute_count INTEGER NOT NULL, v1_rmse_log_density REAL NOT NULL,
                v2_rmse_log_density REAL NOT NULL,
                ridge_rmse_log_density REAL NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        for storm_id, prediction in sorted(predictions.items()):
            v1_rows = v1.execute("""
                SELECT time_us,rho_l2_phase_kg_m3,rho_msis_quiet_phase_kg_m3,
                       rho_trial4_joint_phase_kg_m3
                FROM trial4_joint_fit_minute WHERE storm_id=? ORDER BY time_us
            """, (storm_id,)).fetchall()
            v2_rows = v2.execute("""
                SELECT time_us,rho_l2_phase_kg_m3,rho_msis_quiet_phase_kg_m3,
                       rho_phase4_v2_phase_kg_m3,h_phase_nt,gain_per_nt,r_fit
                FROM phase4_v2_minute WHERE storm_id=? ORDER BY time_us
            """, (storm_id,)).fetchall()
            minutes, score = calculate_event(v1_rows, v2_rows, prediction)
            database.executemany("INSERT INTO density_comparison VALUES (?,?,?,?,?,?,?,?,?)",
                                 minutes)
            database.execute("INSERT INTO event_density_score VALUES (?,?,?,?,?,?,?)", score)
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("ridge_source", str(RIDGE)),
            ("phase4_v1_source", str(V1)),
            ("phase4_v2_source", str(V2)),
            ("ridge_density", "V2 quiet density * held-out Ridge R * exp(V2 G * V2 H)"),
            ("alignment", "exact storm_id,time_us; exact L2 and quiet density across V1/V2"),
            ("score", "per-event RMSE of log(L2/model density)"),
            ("algorithm_version", ALGORITHM_VERSION),
        ])
        counts = database.execute("""
            SELECT (SELECT count(*) FROM event_density_score),
                   (SELECT count(*) FROM density_comparison),
                   (SELECT sum(minute_count) FROM event_density_score)
        """).fetchone()
        if counts != (25, EXPECTED_MINUTES, EXPECTED_MINUTES):
            raise ValueError(f"Density comparison row count differs: {counts}")
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Density comparison SQLite integrity check failed.")


def main() -> None:
    """Input: V1/V2 minute density and held-out Ridge R. Output: comparison SQLite."""
    save_results()
    with closing(read_only(OUTPUT)) as database:
        scores = database.execute("""
            SELECT avg(v1_rmse_log_density*v1_rmse_log_density),
                   avg(v2_rmse_log_density*v2_rmse_log_density),
                   avg(ridge_rmse_log_density*ridge_rmse_log_density)
            FROM event_density_score
        """).fetchone()
    print("25 events, 214907 minutes; event-equal log-density RMSE "
          + ", ".join(f"{math.sqrt(value):.6f}" for value in scores))


if __name__ == "__main__":
    main()
