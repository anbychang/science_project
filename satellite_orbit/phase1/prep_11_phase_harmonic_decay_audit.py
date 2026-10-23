"""Audit the three-year phase-harmonic P1.5.6 to P1.6 branch."""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from satellite_orbit.data.pod.prep_14_phase_harmonic_decay_candidates import (
    DECAY_CANDIDATE_TABLE,
)
from satellite_orbit.phase1.prep_10_phase_harmonic_decay_analysis import (
    ANALYSIS_TABLE,
)


DEFAULT_DATABASE = Path(
    "data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
)
AUDIT_VERSION = "p1_7_phase_harmonic_candidate_audit_v1"
MICROSECONDS_PER_SECOND = 1_000_000
MAXIMUM_SYM_H_FUTURE_US = 120 * MICROSECONDS_PER_SECOND
MAXIMUM_ABSOLUTE_FLOAT = 1.7e308
SCOPE_START_TIME_US = 1_688_169_600_000_000
SCOPE_STOP_TIME_US = 1_782_864_000_000_000
EXPECTED_METHODS = ("joint_h2_h3_local_ols", "raw_b_l_local_ols")
EXPECTED_WINDOWS = (3, 5)


def utc_text(time_us):
    """Input: UTC Unix microseconds.
    Output: ISO-8601 UTC string."""
    return datetime.fromtimestamp(
        time_us / MICROSECONDS_PER_SECOND, timezone.utc,
    ).isoformat().replace("+00:00", "Z")


def require_candidate_tables(connection):
    """Input: SQLite connection.
    Output: P1.5.6 and P1.6 candidate tables are present."""
    table_names = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    required_tables = {DECAY_CANDIDATE_TABLE, ANALYSIS_TABLE}
    missing_tables = sorted(required_tables - table_names)
    if missing_tables:
        raise ValueError("P1.7 candidate audit requires tables: " + ", ".join(missing_tables))


def candidate_audit_counts(connection):
    """Input: SQLite connection with P1.5.6 and P1.6 candidate tables.
    Output: {row_counts, coverage_utc, missingness} audit evidence."""
    coverage = connection.execute(f"""
        SELECT min(time_us), max(time_us) FROM {ANALYSIS_TABLE}
    """).fetchone()
    if coverage[0] is None:
        raise ValueError("P1.7 candidate audit requires non-empty P1.6 output.")
    method_placeholders = ", ".join("?" for _ in EXPECTED_METHODS)
    window_placeholders = ", ".join("?" for _ in EXPECTED_WINDOWS)
    non_finite_columns = (
        "decay_rate_m_day",
        "decay_rate_1sigma_m_day",
        "fit_residual_std_m",
    )
    non_finite_condition = " OR ".join(
        f"NOT ({column} = {column} AND abs({column}) <= ?)"
        for column in non_finite_columns
    )
    missingness = connection.execute(f"""
        SELECT
            (SELECT count(*)
             FROM {DECAY_CANDIDATE_TABLE} AS candidate
             LEFT JOIN {ANALYSIS_TABLE} AS analysis
               ON analysis.time_us = candidate.time_us
              AND analysis.decay_method = candidate.decay_method
              AND analysis.orbit_window = candidate.orbit_window
             WHERE analysis.time_us IS NULL),
            (SELECT count(*)
             FROM {ANALYSIS_TABLE} AS analysis
             LEFT JOIN {DECAY_CANDIDATE_TABLE} AS candidate
               ON candidate.time_us = analysis.time_us
              AND candidate.decay_method = analysis.decay_method
              AND candidate.orbit_window = analysis.orbit_window
             WHERE candidate.time_us IS NULL),
            (SELECT count(*) FROM {ANALYSIS_TABLE}
             WHERE ap_source_time_us > time_us
                OR f107_source_time_us > time_us
                OR f107a_source_time_us > time_us
                OR sym_h_left_time_us > time_us
                OR sym_h_right_time_us > time_us + ?),
            (SELECT count(*) FROM {ANALYSIS_TABLE}
             WHERE {non_finite_condition}),
            (SELECT count(*) FROM {ANALYSIS_TABLE}
             WHERE decay_method NOT IN ({method_placeholders})
                OR orbit_window NOT IN ({window_placeholders})
                OR time_us < ? OR time_us >= ?),
            (SELECT count(*)
             FROM {ANALYSIS_TABLE} AS analysis
             JOIN {DECAY_CANDIDATE_TABLE} AS candidate
               ON candidate.time_us = analysis.time_us
              AND candidate.decay_method = analysis.decay_method
              AND candidate.orbit_window = analysis.orbit_window
             WHERE analysis.chunk_id != candidate.chunk_id
                OR analysis.decay_rate_m_day != candidate.decay_rate_m_day
                OR analysis.window_start_time_us != candidate.window_start_time_us)
    """, (
        MAXIMUM_SYM_H_FUTURE_US,
        *(MAXIMUM_ABSOLUTE_FLOAT for _ in non_finite_columns),
        *EXPECTED_METHODS,
        *EXPECTED_WINDOWS,
        SCOPE_START_TIME_US,
        SCOPE_STOP_TIME_US,
    )).fetchone()
    return {
        "row_counts": {
            "p1_5_6_candidates": connection.execute(
                f"SELECT count(*) FROM {DECAY_CANDIDATE_TABLE}"
            ).fetchone()[0],
            "p1_6_candidate_analysis": connection.execute(
                f"SELECT count(*) FROM {ANALYSIS_TABLE}"
            ).fetchone()[0],
        },
        "coverage_utc": {"start": utc_text(coverage[0]), "end": utc_text(coverage[1])},
        "missingness": {
            "candidate_rows_without_analysis": missingness[0],
            "analysis_rows_without_candidate": missingness[1],
            "future_feature_references": missingness[2],
            "non_finite_candidate_analysis_rows": missingness[3],
            "invalid_candidate_key_or_scope_rows": missingness[4],
            "candidate_analysis_mismatch_rows": missingness[5],
        },
    }


def audit_phase_harmonic_decay(connection):
    """Input: SQLite connection for the three-year phase candidate branch.
    Output: passing P1.7 audit manifest, or an explicit validation error."""
    require_candidate_tables(connection)
    integrity_checks = {
        table_name: connection.execute(
            f"PRAGMA integrity_check({table_name})"
        ).fetchone()[0]
        for table_name in (DECAY_CANDIDATE_TABLE, ANALYSIS_TABLE)
    }
    foreign_keys = connection.execute(
        f"PRAGMA foreign_key_check({ANALYSIS_TABLE})"
    ).fetchall()
    if any(result != "ok" for result in integrity_checks.values()) or foreign_keys:
        raise ValueError("P1.7 candidate audit failed SQLite integrity or foreign keys.")
    counts = candidate_audit_counts(connection)
    failures = [
        name for name, count in counts["missingness"].items() if count != 0
    ]
    if failures:
        raise ValueError("P1.7 candidate audit failed: " + ", ".join(failures))
    if counts["row_counts"]["p1_5_6_candidates"] != counts["row_counts"]["p1_6_candidate_analysis"]:
        raise ValueError("P1.7 candidate audit row counts differ.")
    return {
        "audit_version": AUDIT_VERSION,
        "audit_outcome": "pass",
        "scope_utc": {
            "start": utc_text(SCOPE_START_TIME_US),
            "stop": utc_text(SCOPE_STOP_TIME_US),
        },
        "sqlite_integrity_check": integrity_checks,
        "foreign_key_violation_count": len(foreign_keys),
        **counts,
    }


def write_phase_harmonic_decay_audit(database_path=DEFAULT_DATABASE):
    """Input: three-year SQLite path with P1.5.6 and P1.6 candidate tables.
    Output: P1.7 audit manifest stored after a passing audit."""
    connection = sqlite3.connect(Path(database_path))
    try:
        with connection:
            manifest = audit_phase_harmonic_decay(connection)
            connection.executemany(
                "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
                [
                    ("p1_7_phase_harmonic_audit_version", AUDIT_VERSION),
                    ("p1_7_phase_harmonic_audit_status", "working_audit_pass"),
                    ("p1_7_phase_harmonic_audit_manifest", json.dumps(manifest, sort_keys=True)),
                ],
            )
    finally:
        connection.close()
    return manifest


def main():
    """Input: python -m ...prep_11_phase_harmonic_decay_audit [DATABASE].
    Output: P1.7 three-year candidate-audit summary."""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise ValueError("Usage: [DATABASE]")
    database_path = Path(arguments[0]) if arguments else DEFAULT_DATABASE
    manifest = write_phase_harmonic_decay_audit(database_path)
    print(f"P1.7 candidate audit: {manifest['audit_outcome']}")
    print(f"P1.6 rows: {manifest['row_counts']['p1_6_candidate_analysis']}")


if __name__ == "__main__":
    main()
