"""Save Phase 5 orbit GPR data as one derived SQLite database."""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE phase5_orbit_anchor (
    storm_id TEXT NOT NULL,
    time_us INTEGER NOT NULL,
    u_rel_rad REAL NOT NULL,
    rho_l2_phase_kg_m3 REAL NOT NULL CHECK (rho_l2_phase_kg_m3 > 0),
    rho_trial4_phase_kg_m3 REAL NOT NULL CHECK (rho_trial4_phase_kg_m3 > 0),
    residual_log_density REAL NOT NULL,
    algorithm_version TEXT NOT NULL,
    PRIMARY KEY (storm_id, time_us)
);
CREATE TABLE phase5_fold (
    fold_index INTEGER PRIMARY KEY,
    train_pair_count INTEGER NOT NULL,
    test_pair_count INTEGER NOT NULL,
    orbit_count INTEGER NOT NULL,
    trial4_log_rmse REAL NOT NULL,
    previous_orbit_log_rmse REAL NOT NULL,
    pooled_gpr_log_rmse REAL NOT NULL,
    algorithm_version TEXT NOT NULL
);
CREATE TABLE phase5_fold_storm (
    fold_index INTEGER NOT NULL REFERENCES phase5_fold(fold_index),
    storm_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('train', 'test')),
    algorithm_version TEXT NOT NULL,
    PRIMARY KEY (fold_index, storm_id)
);
CREATE TABLE phase5_orbit_prediction (
    storm_id TEXT NOT NULL,
    time_us INTEGER NOT NULL,
    previous_time_us INTEGER NOT NULL CHECK (previous_time_us < time_us),
    fold_index INTEGER NOT NULL REFERENCES phase5_fold(fold_index),
    comparable_2115 INTEGER NOT NULL CHECK (comparable_2115 IN (0, 1)),
    rho_l2_phase_kg_m3 REAL NOT NULL,
    rho_trial4_phase_kg_m3 REAL NOT NULL,
    actual_log_residual REAL NOT NULL,
    previous_log_residual REAL NOT NULL,
    pooled_gpr_log_residual REAL NOT NULL,
    pooled_gpr_log_std REAL NOT NULL,
    rho_pooled_gpr_kg_m3 REAL NOT NULL,
    algorithm_version TEXT NOT NULL,
    PRIMARY KEY (storm_id, time_us),
    FOREIGN KEY (storm_id, time_us)
        REFERENCES phase5_orbit_anchor(storm_id, time_us),
    FOREIGN KEY (storm_id, previous_time_us)
        REFERENCES phase5_orbit_anchor(storm_id, time_us)
);
CREATE TABLE phase5_event_metric (
    storm_id TEXT PRIMARY KEY,
    orbit_count INTEGER NOT NULL,
    trial4_log_rmse REAL NOT NULL,
    previous_orbit_log_rmse REAL NOT NULL,
    pooled_gpr_log_rmse REAL NOT NULL,
    algorithm_version TEXT NOT NULL
);
CREATE TABLE phase5_summary_metric (
    scope TEXT PRIMARY KEY,
    orbit_count INTEGER NOT NULL,
    trial4_log_rmse REAL NOT NULL,
    previous_orbit_log_rmse REAL NOT NULL,
    pooled_gpr_log_rmse REAL NOT NULL,
    algorithm_version TEXT NOT NULL
);
CREATE TABLE phase5_metadata (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def write_sqlite(path: Path, result: dict) -> None:
    """Input: new SQLite path, {events,predictions,metrics,folds,metadata}. Output: derived SQLite file."""
    if path.exists():
        raise FileExistsError(f"Phase 5 SQLite already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix="phase5_gpr_", suffix=".building", dir=path.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript(SCHEMA)
            version = result["metadata"]["algorithm_version"]
            anchors = [row for rows in result["events"].values() for row in rows]
            database.executemany("INSERT INTO phase5_orbit_anchor VALUES (?,?,?,?,?,?,?)", (
                (row["storm_id"], row["time_us"], row["u_rel_rad"],
                 row["rho_l2_phase_kg_m3"], row["rho_trial4_phase_kg_m3"],
                 row["residual_log_density"], version) for row in anchors))
            database.executemany("INSERT INTO phase5_fold VALUES (?,?,?,?,?,?,?,?)", (
                (fold["fold_index"], fold["train_pair_count"], fold["test_pair_count"],
                 fold["orbit_count"], fold["trial4_log_rmse"],
                 fold["previous_orbit_log_rmse"], fold["pooled_gpr_log_rmse"], version)
                for fold in result["folds"]))
            database.executemany("INSERT INTO phase5_fold_storm VALUES (?,?,?,?)", (
                (fold["fold_index"], storm_id, role, version)
                for fold in result["folds"]
                for role, ids in (("train", fold["train_storm_ids"]),
                                  ("test", fold["test_storm_ids"]))
                for storm_id in ids))
            database.executemany("INSERT INTO phase5_orbit_prediction VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                (row["storm_id"], row["time_us"], row["previous_time_us"],
                 row["fold_index"], row["comparable_2115"],
                 row["rho_l2_phase_kg_m3"], row["rho_trial4_phase_kg_m3"],
                 row["actual_log_residual"], row["previous_log_residual"],
                 row["pooled_gpr_log_residual"], row["pooled_gpr_log_std"],
                 row["rho_pooled_gpr_kg_m3"], version) for row in result["predictions"]))
            database.executemany("INSERT INTO phase5_event_metric VALUES (?,?,?,?,?,?)", (
                (row["storm_id"], row["orbit_count"], row["trial4_log_rmse"],
                 row["previous_orbit_log_rmse"], row["pooled_gpr_log_rmse"], version)
                for row in result["event_metrics"]))
            database.executemany("INSERT INTO phase5_summary_metric VALUES (?,?,?,?,?,?)", (
                (scope, row["orbit_count"], row["trial4_log_rmse"],
                 row["previous_orbit_log_rmse"], row["pooled_gpr_log_rmse"], version)
                for scope, row in result["summary_metrics"].items()))
            database.executemany("INSERT INTO phase5_metadata VALUES (?,?)",
                                 result["metadata"].items())
            if (database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                    or database.execute("PRAGMA foreign_key_check").fetchone() is not None):
                raise ValueError("Phase 5 SQLite integrity check failed.")
            counts = [database.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                      for table in ("phase5_orbit_anchor", "phase5_orbit_prediction",
                                    "phase5_event_metric", "phase5_fold")]
            if counts != [2295, 2265, 25, 5]:
                raise ValueError(f"Phase 5 SQLite row counts differ: {counts}")
            database.commit()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
