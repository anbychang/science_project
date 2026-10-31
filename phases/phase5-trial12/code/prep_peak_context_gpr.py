"""Test whole-event M1 peak-context features with the same held-out GP design."""

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path("phases/phase5-trial10/code").resolve()))
sys.path.insert(0, str(Path("phases/phase5-trial11/code").resolve()))

from calc_m1_shape_features import build_triplets
from prep_phase5_m1_shape_gpr import M1, load_anchors
from prep_temporal_shape_gpr import evaluate
from calc_peak_context_features import build_feature_rows


OUTPUT = Path("phases/phase5-trial12/data/sqlite/swarm_a_phase5_peak_context_gpr_v1.sqlite")
VERSION = "phase5_trial12_peak_context_gpr_v1"
FEATURE_NAMES = ("log_m1", "log_below_peak", "days_from_peak", "cumulative_excess")


def write_sqlite(result: dict) -> None:
    """Input: held-out peak-context GP result. Output: separate atomic SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE prediction (
                    storm_id TEXT NOT NULL,time_us INTEGER NOT NULL,grid_index INTEGER NOT NULL,
                    fold_index INTEGER NOT NULL,log_m1 REAL NOT NULL,
                    log_below_peak REAL NOT NULL,days_from_peak REAL NOT NULL,
                    cumulative_excess REAL NOT NULL,rho_m1_kg_m3 REAL NOT NULL,
                    rho_l2_kg_m3 REAL NOT NULL,actual_log_residual REAL NOT NULL,
                    predicted_shape_residual REAL NOT NULL,rho_gp_kg_m3 REAL NOT NULL,
                    algorithm_version TEXT NOT NULL,PRIMARY KEY(storm_id,time_us)
                );
                CREATE TABLE fold_metric (
                    fold_index INTEGER PRIMARY KEY,train_count INTEGER NOT NULL,
                    test_count INTEGER NOT NULL,m1_total_rmse REAL NOT NULL,
                    m1_shape_rmse REAL NOT NULL,m1_change_rmse REAL NOT NULL,
                    gp_total_rmse REAL NOT NULL,gp_shape_rmse REAL NOT NULL,
                    gp_change_rmse REAL NOT NULL,length_scale_log_m1 REAL NOT NULL,
                    length_scale_below_peak REAL NOT NULL,length_scale_time REAL NOT NULL,
                    length_scale_cumulative REAL NOT NULL,warning_count INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE event_metric (
                    storm_id TEXT PRIMARY KEY,test_count INTEGER NOT NULL,
                    m1_total_rmse REAL NOT NULL,m1_shape_rmse REAL NOT NULL,
                    m1_change_rmse REAL NOT NULL,gp_total_rmse REAL NOT NULL,
                    gp_shape_rmse REAL NOT NULL,gp_change_rmse REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE summary (
                    test_count INTEGER NOT NULL,m1_total_rmse REAL NOT NULL,
                    m1_shape_rmse REAL NOT NULL,m1_change_rmse REAL NOT NULL,
                    gp_total_rmse REAL NOT NULL,gp_shape_rmse REAL NOT NULL,
                    gp_change_rmse REAL NOT NULL,improved_shape_storms INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
                CREATE TABLE metadata (name TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            database.executemany("INSERT INTO prediction VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 result["predictions"])
            database.executemany("INSERT INTO fold_metric VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 result["folds"])
            database.executemany("INSERT INTO event_metric VALUES (?,?,?,?,?,?,?,?,?)",
                                 result["events"])
            database.execute("INSERT INTO summary VALUES (?,?,?,?,?,?,?,?,?)", result["summary"])
            database.executemany("INSERT INTO metadata VALUES (?,?)", {
                "feature_names": ",".join(FEATURE_NAMES),
                "training_target": "log(L2/M1) minus each training storm's mean",
                "test_correction": "predicted shape minus its test storm mean; no test L2",
                "split": "five whole-storm 20/5 folds, seed 20261030",
                "source": str(M1),
            }.items())
            if (database.execute("SELECT count(*) FROM prediction").fetchone()[0]
                    != result["summary"][0]
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Trial 12 SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: Phase 3 M1 and historical L2. Output: Trial 12 held-out SQLite."""
    rows = build_feature_rows(build_triplets(load_anchors()))
    if len(rows) != 2235 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Expected 2,235 valid centers across 25 storms.")
    result = evaluate(rows, VERSION)
    write_sqlite(result)
    print(f"Overall M1 shape {result['summary'][2]:.6f}, "
          f"GP shape {result['summary'][5]:.6f}, "
          f"improved storms {result['summary'][7]}/25")


if __name__ == "__main__":
    main()
