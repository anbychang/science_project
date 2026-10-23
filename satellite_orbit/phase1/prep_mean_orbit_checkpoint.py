"""Checkpoint a completed P1.5 database before rebuilding downstream products."""

import sqlite3
import sys
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import connect_database
from satellite_orbit.data.pod.prep_04_mean_orbit import MEAN_ORBIT_ELEMENTS_TABLE
from satellite_orbit.data.pod.prep_06_orbit_10min import write_orbit_10min
from satellite_orbit.data.pod.prep_07_decay_rate import write_decay_rates
from satellite_orbit.phase1.prep_08_analysis_10min import write_analysis_10min
from satellite_orbit.phase1.prep_09_release_audit import write_scoped_v1_release_metadata

CHECKPOINT_STAGE = "p1_5_mean_orbit"
CHECKPOINT_STAGE_METADATA = "phase1_checkpoint_stage"


def checkpoint_mean_orbit_database(source_database_path, checkpoint_database_path):
    """Input: completed P1.5 SQLite path and absent checkpoint path
    Output: {checkpoint_database_path, mean_orbit_rows}"""
    source_database_path = Path(source_database_path)
    checkpoint_database_path = Path(checkpoint_database_path)
    require_new_checkpoint_path(source_database_path, checkpoint_database_path)
    require_complete_mean_orbit_rows(source_database_path)
    copy_sqlite_database(source_database_path, checkpoint_database_path)
    with connect_database(checkpoint_database_path) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
            (CHECKPOINT_STAGE_METADATA, CHECKPOINT_STAGE),
        )
        mean_orbit_rows = connection.execute(
            f"SELECT count(*) FROM {MEAN_ORBIT_ELEMENTS_TABLE}"
        ).fetchone()[0]
    return {
        "checkpoint_database_path": checkpoint_database_path,
        "mean_orbit_rows": mean_orbit_rows,
    }


def write_downstream_from_mean_orbit(baseline_database_path, database_path):
    """Input: completed P1.5 baseline or checkpoint, absent output SQLite path
    Output: {database_path, orbit_10min, decay, analysis, audit}"""
    baseline_database_path = Path(baseline_database_path)
    database_path = Path(database_path)
    require_new_checkpoint_path(baseline_database_path, database_path)
    start_time_us, stop_time_us = require_p1_5_mean_orbit(baseline_database_path)
    copy_sqlite_database(baseline_database_path, database_path)
    return {
        "database_path": database_path,
        "orbit_10min": write_orbit_10min(
            database_path,
            MEAN_ORBIT_ELEMENTS_TABLE,
            start_time_us,
            stop_time_us,
        ),
        "decay": write_decay_rates(database_path),
        "analysis": write_analysis_10min(database_path),
        "audit": write_scoped_v1_release_metadata(
            database_path, start_time_us, stop_time_us
        ),
    }


def require_new_checkpoint_path(source_database_path, target_database_path):
    """Input: existing source path and requested target path
    Output: target is safe to create"""
    if not source_database_path.is_file():
        raise ValueError(f"Source database does not exist: {source_database_path}")
    if target_database_path.exists():
        raise ValueError(f"Checkpoint target already exists: {target_database_path}")


def require_complete_mean_orbit_rows(database_path):
    """Input: P1.5 SQLite path
    Output: verified [start_time_us, stop_time_us) for complete v1 mean orbit"""
    with connect_database(database_path) as connection:
        metadata = dict(
            connection.execute(
                "SELECT name, value FROM metadata WHERE name IN "
                "('mean_orbit_elements_table', 'mean_orbit_elements_start_time_us', "
                "'mean_orbit_elements_stop_time_us')"
            )
        )
        if metadata.get("mean_orbit_elements_table") != MEAN_ORBIT_ELEMENTS_TABLE:
            raise ValueError("P1.5 v1 mean-orbit metadata is missing or mismatched.")
        try:
            start_time_us = int(metadata["mean_orbit_elements_start_time_us"])
            stop_time_us = int(metadata["mean_orbit_elements_stop_time_us"])
        except (KeyError, ValueError) as error:
            raise ValueError("P1.5 v1 mean-orbit time scope is missing or invalid.") from error
        if start_time_us >= stop_time_us:
            raise ValueError("P1.5 v1 mean-orbit time scope is empty.")
        if connection.execute(
            f"SELECT 1 FROM {MEAN_ORBIT_ELEMENTS_TABLE} LIMIT 1"
        ).fetchone() is None:
            raise ValueError("P1.5 v1 mean-orbit table is empty.")
        missing_rows = connection.execute(
            f"""
            SELECT count(*)
            FROM swarm_a_pod_quality AS quality
            LEFT JOIN {MEAN_ORBIT_ELEMENTS_TABLE} AS mean
                ON mean.time_us = quality.time_us
            WHERE quality.is_usable = 1
              AND quality.time_us >= ? AND quality.time_us < ?
              AND (mean.time_us IS NULL OR mean.mean_semi_major_axis_m IS NULL
                   OR mean.rejection_reason IS NOT NULL)
            """,
            (start_time_us, stop_time_us),
        ).fetchone()[0]
    if missing_rows:
        raise ValueError(
            f"P1.5 has {missing_rows} missing or rejected v1 mean-orbit rows."
        )
    return start_time_us, stop_time_us


def require_p1_5_mean_orbit(database_path):
    """Input: P1.5 SQLite baseline or checkpoint path
    Output: verified [start_time_us, stop_time_us)"""
    with connect_database(database_path) as connection:
        checkpoint_stage = connection.execute(
            "SELECT value FROM metadata WHERE name = ?",
            (CHECKPOINT_STAGE_METADATA,),
        ).fetchone()
    if checkpoint_stage is not None and checkpoint_stage != (CHECKPOINT_STAGE,):
        raise ValueError(f"Not a P1.5 mean-orbit checkpoint: {database_path}")
    return require_complete_mean_orbit_rows(database_path)


def copy_sqlite_database(source_database_path, target_database_path):
    """Input: existing SQLite source and absent target path
    Output: independent SQLite copy with a consistent transaction"""
    with sqlite3.connect(source_database_path) as source_connection:
        with sqlite3.connect(target_database_path) as target_connection:
            source_connection.backup(target_connection)


def main():
    """Input: checkpoint SOURCE TARGET, or downstream P1_5_BASELINE TARGET
    Output: one P1.5 checkpoint or its downstream rebuild summary"""
    arguments = sys.argv[1:]
    if len(arguments) != 3:
        raise ValueError("Usage: checkpoint SOURCE TARGET | downstream P1_5_BASELINE TARGET")
    action, source_database_path, target_database_path = arguments
    if action == "checkpoint":
        result = checkpoint_mean_orbit_database(source_database_path, target_database_path)
    elif action == "downstream":
        result = write_downstream_from_mean_orbit(
            source_database_path,
            target_database_path,
        )
    else:
        raise ValueError("Action must be checkpoint or downstream.")
    print(result)


if __name__ == "__main__":
    main()
