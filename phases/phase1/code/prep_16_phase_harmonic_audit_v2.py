"""Audit P1.5.6 v2 rate tables and the shared P1.6 feature table."""

import json
import sqlite3
import sys
import time
from pathlib import Path

from phases.phase1.code.prep_14_phase_harmonic_decay_candidates import (
    JOINT_H2_H3_SET_TABLE,
    RAW_B_L_SET_TABLE,
)
from phases.phase1.code.prep_15_phase_harmonic_features_v2 import FEATURE_TABLE


DEFAULT_DATABASE = Path("phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite")
AUDIT_TABLE = "swarm_a_phase_harmonic_audit_v2"
ALGORITHM_VERSION = "phase_harmonic_audit_v2"
MAXIMUM_SYM_H_FUTURE_US = 120_000_000
MAXIMUM_FINITE_FLOAT = 1.7976931348623157e308


def create_audit_table(connection):
    """Input: SQLite connection. Output: versioned P1.7 audit table exists."""
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
            audit_name TEXT PRIMARY KEY,
            violation_count INTEGER NOT NULL,
            scope_start_time_us INTEGER NOT NULL,
            scope_stop_time_us INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        )
    """)


def scalar(connection, query):
    """Input: SQLite connection and scalar query. Output: integer query result."""
    return connection.execute(query).fetchone()[0]


def count_violations(connection, name, query):
    """Input: SQLite connection, audit name, query. Output: violation count."""
    print(f"checking {name}", flush=True)
    count = scalar(connection, query)
    print(f"{name}: {count}", flush=True)
    return count


def audit_counts(connection):
    """Input: SQLite connection with v2 rate and feature tables. Output: audit counts."""
    raw_count = scalar(connection, f"SELECT count(*) FROM {RAW_B_L_SET_TABLE}")
    coverage = connection.execute(
        f"SELECT min(time_us), max(time_us) FROM {RAW_B_L_SET_TABLE}"
    ).fetchone()
    if coverage[0] is None:
        raise ValueError("P1.7 v2 audit requires non-empty raw rate table.")
    counts = {}
    counts["raw_joint_time_key_identity"] = count_violations(connection, "raw_joint_time_key_identity", f"""
            SELECT count(*) FROM {RAW_B_L_SET_TABLE} raw
            LEFT JOIN {JOINT_H2_H3_SET_TABLE} joint USING(time_us)
            WHERE joint.time_us IS NULL
        """) + count_violations(connection, "joint_raw_time_key_identity", f"""
            SELECT count(*) FROM {JOINT_H2_H3_SET_TABLE} joint
            LEFT JOIN {RAW_B_L_SET_TABLE} raw USING(time_us)
            WHERE raw.time_us IS NULL
        """)
    feature_count = scalar(connection, f"SELECT count(*) FROM {FEATURE_TABLE}")
    counts["raw_feature_time_key_identity"] = raw_count + feature_count - 2 * count_violations(
        connection, "raw_feature_matched_keys", f"""
            SELECT count(*) FROM {RAW_B_L_SET_TABLE} raw
            JOIN {FEATURE_TABLE} feature USING(time_us)
        """)
    counts["rate_validity_parity"] = count_violations(connection, "rate_validity_parity", f"""
            SELECT count(*) FROM {RAW_B_L_SET_TABLE} raw
            JOIN {JOINT_H2_H3_SET_TABLE} joint USING(time_us)
            WHERE (raw.orbit_3_decay_rate_m_s IS NULL) != (joint.orbit_3_decay_rate_m_s IS NULL)
               OR (raw.orbit_5_decay_rate_m_s IS NULL) != (joint.orbit_5_decay_rate_m_s IS NULL)
        """)
    counts["feature_future_reference"] = count_violations(connection, "feature_future_reference", f"""
            SELECT count(*) FROM {FEATURE_TABLE}
            WHERE ap_source_time_us > time_us OR f107_source_time_us > time_us
               OR f107a_source_time_us > time_us
               OR sym_h_left_time_us > time_us
               OR sym_h_right_time_us > time_us + {MAXIMUM_SYM_H_FUTURE_US}
        """)
    counts["non_finite_rate"] = sum(count_violations(connection, f"non_finite_rate_{table}", f"""
        SELECT count(*) FROM {table}
        WHERE abs(orbit_3_decay_rate_m_s) > {MAXIMUM_FINITE_FLOAT}
           OR abs(orbit_5_decay_rate_m_s) > {MAXIMUM_FINITE_FLOAT}
    """) for table in (RAW_B_L_SET_TABLE, JOINT_H2_H3_SET_TABLE))
    return coverage, counts


def write_phase_harmonic_audit_v2(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5.6/P1.6 v2 tables. Output: P1.7 audit manifest."""
    connection = sqlite3.connect(Path(database_path))
    last_report_time = time.monotonic()

    def report_progress():
        """Input: SQLite VM callback. Output: continue and periodic elapsed-time log."""
        nonlocal last_report_time
        current_time = time.monotonic()
        if current_time - last_report_time >= 30:
            print("P1.7 v2 SQLite scan still running", flush=True)
            last_report_time = current_time
        return 0

    connection.set_progress_handler(report_progress, 100_000)
    try:
        create_audit_table(connection)
        coverage, counts = audit_counts(connection)
        integrity = {}
        for table in (RAW_B_L_SET_TABLE, JOINT_H2_H3_SET_TABLE, FEATURE_TABLE):
            print(f"checking integrity: {table}", flush=True)
            integrity[table] = connection.execute(f"PRAGMA integrity_check({table})").fetchone()[0]
            print(f"integrity {table}: {integrity[table]}", flush=True)
        counts["sqlite_integrity"] = sum(result != "ok" for result in integrity.values())
        connection.execute(f"DELETE FROM {AUDIT_TABLE}")
        connection.executemany(
            f"INSERT INTO {AUDIT_TABLE} VALUES (?, ?, ?, ?, ?)",
            [(name, count, coverage[0], coverage[1], ALGORITHM_VERSION) for name, count in counts.items()],
        )
        outcome = "pass" if not any(counts.values()) else "failed"
        manifest = {"audit_version": ALGORITHM_VERSION, "audit_outcome": outcome,
                    "scope_start_time_us": coverage[0], "scope_stop_time_us": coverage[1],
                    "violations": counts, "integrity": integrity}
        connection.executemany("INSERT OR REPLACE INTO metadata VALUES (?, ?)", [
            ("p1_7_phase_harmonic_v2_status", outcome),
            ("p1_7_phase_harmonic_v2_manifest", json.dumps(manifest, sort_keys=True)),
        ])
        connection.commit()
    finally:
        connection.close()
    return manifest


def main():
    """Input: python -m ...prep_16_phase_harmonic_audit_v2 [DATABASE]. Output: audit status."""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise ValueError("Usage: [DATABASE]")
    manifest = write_phase_harmonic_audit_v2(Path(arguments[0]) if arguments else DEFAULT_DATABASE)
    print(f"P1.7 v2 audit: {manifest['audit_outcome']}")


if __name__ == "__main__":
    main()
