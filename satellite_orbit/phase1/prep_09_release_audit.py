"""Audit the final 10-minute dataset and store a release manifest."""

import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from satellite_orbit.data.pod.prep_06_orbit_10min import BIN_DURATION_US
from satellite_orbit.data.pod.prep_07_decay_rate import (
    BACKWARD_INTERVALS,
    BACKWARD_INTERVAL_SAMPLES,
    BACKWARD_INTERVAL_SECONDS,
    SECONDS_PER_DAY,
)


DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
AUDIT_VERSION = "p1_7_release_audit_v4"
MAXIMUM_ABSOLUTE_FLOAT = 1.7e308
REBUILD_STATUS = "not_executed"
SEMI_MAJOR_AXIS_TOLERANCE_M = 1e-6
DERIVATIVE_TOLERANCE_M_S = 1e-12
DA_DT_PER_DAY_TOLERANCE_M_DAY = 1e-8
P1_4_POLICY = (
    "chunk splits on product stream, SP3 frame, cadence, or time discontinuity; "
    "Q3 unavailable; published Swarm-A orbit events excluded by date; "
    "other Q4 candidates residual audit-only"
)
P1_3_METADATA_NAMES = (
    "orbital_element_algorithm",
    "orbital_element_mu_m3_s2",
)
P1_4_METADATA_NAMES = (
    "p1_4_quality_policy_version",
    "p1_4_official_orbit_events",
)
P1_5_METADATA_NAMES = (
    "mean_orbit_algorithm",
    "mean_orbit_input_policy",
    "mean_orbit_input_frame",
    "mean_orbit_input_transform",
    "mean_orbit_gravity_field_degree_order",
    "mean_orbit_m2",
    "mean_orbit_implementation_fingerprint",
    "orbit_10min_algorithm",
    "orbit_10min_bin_contract",
    "orbit_decay_algorithm",
    "orbit_decay_interval_hours",
    "orbit_decay_interval_samples",
    "orbit_decay_interval_seconds",
    "orbit_decay_time_convention",
    "orbit_decay_edge_exclusion",
    "orbit_decay_run_contract",
    "orbit_decay_rate_definition",
)
P1_6_METADATA_NAMES = (
    "analysis_10min_algorithm",
    "analysis_10min_feature_contract",
)
REBUILD_COMMANDS = (
    "python -m satellite_orbit.phase1.prep_phase1_rebuild NEW_DATABASE [MEAN_CACHE]",
)
PHASE_ONE_IMPLEMENTATION_FILES = (
    "satellite_orbit/calculation/analysis/calc_feature_alignment.py",
    "satellite_orbit/calculation/pod/calc_coordinates.py",
    "satellite_orbit/calculation/pod/calc_mean_orbit.py",
    "satellite_orbit/calculation/pod/calc_orbital_response.py",
    "satellite_orbit/data/database/prep_raw_database.py",
    "satellite_orbit/data/database/prep_raw_identifiers.py",
    "satellite_orbit/data/database/prep_raw_schema.py",
    "satellite_orbit/data/density/load_swarm_density.py",
    "satellite_orbit/data/density/prep_raw_density.py",
    "satellite_orbit/data/geomagnetic/prep_raw_geomagnetic.py",
    "satellite_orbit/data/pod/load_sp3_inventory.py",
    "satellite_orbit/data/pod/load_swarm_pod.py",
    "satellite_orbit/data/pod/prep_01_raw_pod.py",
    "satellite_orbit/data/pod/prep_02_source_provenance.py",
    "satellite_orbit/data/pod/prep_03_orbital_elements.py",
    "satellite_orbit/data/pod/prep_04_mean_orbit.py",
    "satellite_orbit/data/pod/prep_05_pod_quality.py",
    "satellite_orbit/data/pod/prep_06_orbit_10min.py",
    "satellite_orbit/data/pod/prep_07_decay_rate.py",
    "satellite_orbit/data/pod/prep_mean_orbit_cache.py",
    "satellite_orbit/data/space_weather/prep_raw_weather.py",
    "satellite_orbit/phase1/prep_08_analysis_10min.py",
    "satellite_orbit/phase1/prep_09_release_audit.py",
    "satellite_orbit/phase1/prep_phase1_rebuild.py",
)
REQUIRED_TABLES = (
    "source_files",
    "space_weather",
    "geomagnetic",
    "swarm_a_density",
    "swarm_a_states",
    "swarm_a_orbital_elements",
    "swarm_a_pod_quality",
    "swarm_a_mean_orbital_elements",
    "swarm_a_orbit_10min",
    "swarm_a_orbit_decay_10min",
    "swarm_a_analysis_10min",
)
ANALYSIS_COLUMNS = (
    "time_us", "semi_major_axis_orbit_mean_m", "da_dt_3h_backward_m_s",
    "da_dt_3h_backward_m_day", "da_dt_6h_backward_m_s",
    "da_dt_6h_backward_m_day", "da_dt_12h_backward_m_s",
    "da_dt_12h_backward_m_day", "pod_count", "max_pod_gap_s", "chunk_id",
    "sym_h_nt", "sym_h_left_time_us", "sym_h_right_time_us", "ap_now",
    "ap_source_time_us", "f107_sfu", "f107_source_time_us", "f107a_sfu",
    "f107a_source_time_us", "f107_data_type", "quality_flags", "algorithm_version",
)
ANALYSIS_FLOAT_COLUMNS = (
    "semi_major_axis_orbit_mean_m", "da_dt_3h_backward_m_s",
    "da_dt_3h_backward_m_day", "da_dt_6h_backward_m_s",
    "da_dt_6h_backward_m_day", "da_dt_12h_backward_m_s",
    "max_pod_gap_s", "sym_h_nt", "ap_now", "f107_sfu", "f107a_sfu",
)
REQUIRED_ANALYSIS_COLUMNS = (
    "time_us", "semi_major_axis_orbit_mean_m", "da_dt_3h_backward_m_s",
    "da_dt_3h_backward_m_day", "da_dt_6h_backward_m_s",
    "da_dt_6h_backward_m_day", "da_dt_12h_backward_m_s",
    "da_dt_12h_backward_m_day", "pod_count", "max_pod_gap_s", "chunk_id",
    "quality_flags", "algorithm_version",
)


def stable_sha256(value):
    """Input: JSON-compatible value
    Output: deterministic SHA-256 hex digest"""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def git_revision():
    """Input: current repository
    Output: {git_head, git_dirty}, or unavailable when Git cannot run"""
    project_root = Path(__file__).resolve().parents[2]
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"git_head": "unavailable", "git_dirty": None}
    return {"git_head": head, "git_dirty": dirty}


def phase_one_code_content():
    """Input: checked-out Phase 1 implementation files
    Output: deterministic file hashes and aggregate SHA-256 digest"""
    project_root = Path(__file__).resolve().parents[2]
    file_hashes = {
        relative_path: hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        for relative_path in PHASE_ONE_IMPLEMENTATION_FILES
    }
    return {
        "algorithm": "sha256",
        "files": file_hashes,
        "digest": stable_sha256(file_hashes),
    }


def require_tables(connection):
    """Input: SQLite connection
    Output: all P1 release tables are present"""
    present_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    missing_tables = sorted(set(REQUIRED_TABLES) - present_tables)
    if missing_tables:
        raise ValueError(f"P1.7 requires tables: {', '.join(missing_tables)}")


def metadata_values(connection, names):
    """Input: SQLite connection and required metadata names
    Output: {name: value} for every requested name"""
    placeholders = ", ".join("?" for _ in names)
    values = dict(
        connection.execute(
            f"SELECT name, value FROM metadata WHERE name IN ({placeholders})", names
        )
    )
    missing_names = sorted(set(names) - set(values))
    if missing_names:
        raise ValueError(f"P1.7 requires metadata: {', '.join(missing_names)}")
    return values


def utc_text(time_us):
    """Input: Unix microseconds
    Output: ISO-8601 UTC string"""
    return datetime.fromtimestamp(time_us / 1_000_000, timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def raw_input_manifest(connection):
    """Input: SQLite connection with raw source records
    Output: deterministic raw-source provenance summary"""
    source_records = [
        {"source_id": row[0], "file_name": row[1], "signature": row[2]}
        for row in connection.execute(
            "SELECT source_id, file_name, signature FROM source_files ORDER BY source_id"
        )
    ]
    weather_metadata = metadata_values(
        connection, ("weather_signature", "weather_preparation_version")
    )
    counts = {
        table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("geomagnetic", "swarm_a_density", "space_weather", "source_files")
    }
    if not source_records or any(count == 0 for count in counts.values()):
        raise ValueError("P1.7 requires non-empty raw source tables.")
    return {
        "source_files_count": counts["source_files"],
        "source_signature_sha256": stable_sha256(source_records),
        "weather_metadata": weather_metadata,
        "weather_metadata_sha256": stable_sha256(weather_metadata),
        "geomagnetic_rows": counts["geomagnetic"],
        "density_rows": counts["swarm_a_density"],
        "space_weather_rows": counts["space_weather"],
    }


def release_counts(connection):
    """Input: SQLite connection with P1.5 and P1.6 output
    Output: row-count, coverage, and missingness evidence"""
    row_counts = {
        table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in (
            "swarm_a_states",
            "swarm_a_orbital_elements",
            "swarm_a_pod_quality",
            "swarm_a_mean_orbital_elements",
            "swarm_a_orbit_10min",
            "swarm_a_orbit_decay_10min",
            "swarm_a_analysis_10min",
        )
    }
    coverage = connection.execute(
        "SELECT min(time_us), max(time_us) FROM swarm_a_analysis_10min"
    ).fetchone()
    if coverage[0] is None:
        raise ValueError("P1.7 requires non-empty analysis output.")
    null_condition = " OR ".join(
        f"{column} IS NULL" for column in REQUIRED_ANALYSIS_COLUMNS
    )
    non_finite_condition = " OR ".join(
        f"NOT ({column} = {column} AND abs({column}) <= ?)"
        for column in ANALYSIS_FLOAT_COLUMNS
    )
    missingness = connection.execute(
        """
        SELECT
            (SELECT count(*) FROM swarm_a_states AS state
             LEFT JOIN swarm_a_orbital_elements AS orbital
             ON orbital.time_us = state.time_us
             WHERE orbital.time_us IS NULL),
            (SELECT count(*) FROM swarm_a_orbital_elements AS orbital
             LEFT JOIN swarm_a_pod_quality AS quality
             ON quality.time_us = orbital.time_us
             WHERE quality.time_us IS NULL),
            (SELECT count(*) FROM swarm_a_pod_quality AS quality
             LEFT JOIN swarm_a_mean_orbital_elements AS mean
             ON mean.time_us = quality.time_us
             WHERE quality.is_usable = 1
               AND mean.time_us IS NULL),
            (SELECT count(*) FROM swarm_a_orbit_decay_10min AS decay
             LEFT JOIN swarm_a_analysis_10min AS analysis
             ON analysis.time_us = decay.time_us
             WHERE analysis.time_us IS NULL),
            (SELECT count(*) FROM swarm_a_analysis_10min AS analysis
             LEFT JOIN swarm_a_orbit_decay_10min AS decay
             ON decay.time_us = analysis.time_us
             WHERE decay.time_us IS NULL),
            (SELECT count(*) FROM swarm_a_analysis_10min
             WHERE ap_source_time_us > time_us
                OR f107_source_time_us > time_us
                OR f107a_source_time_us > time_us
                OR sym_h_left_time_us > time_us
                OR sym_h_right_time_us > time_us + 120000000),
            (SELECT count(*) FROM swarm_a_analysis_10min
             WHERE pod_count < 56 OR max_pod_gap_s > 10.0),
            (SELECT count(*) FROM swarm_a_analysis_10min
             WHERE """
        + null_condition
        + """),
            (SELECT count(*) FROM swarm_a_analysis_10min
             WHERE """
        + non_finite_condition
        + """),
            (SELECT count(*) FROM swarm_a_analysis_10min
             WHERE quality_flags NOT IN (
                    'ok', 'missing_sym_h', 'missing_space_weather',
                    'missing_sym_h|missing_space_weather'
                 )
                OR (
                    (sym_h_nt IS NULL OR sym_h_left_time_us IS NULL OR sym_h_right_time_us IS NULL)
                    AND NOT (
                        sym_h_nt IS NULL AND sym_h_left_time_us IS NULL AND sym_h_right_time_us IS NULL
                        AND instr(quality_flags, 'missing_sym_h') > 0
                    )
                )
                OR (
                    sym_h_nt IS NOT NULL AND sym_h_left_time_us IS NOT NULL
                    AND sym_h_right_time_us IS NOT NULL
                    AND instr(quality_flags, 'missing_sym_h') > 0
                )
                OR (
                    (
                        ap_now IS NULL OR ap_source_time_us IS NULL OR f107_sfu IS NULL
                        OR f107_source_time_us IS NULL OR f107a_sfu IS NULL
                        OR f107a_source_time_us IS NULL OR f107_data_type IS NULL
                    )
                    AND NOT (
                        ap_now IS NULL AND ap_source_time_us IS NULL AND f107_sfu IS NULL
                        AND f107_source_time_us IS NULL AND f107a_sfu IS NULL
                        AND f107a_source_time_us IS NULL AND f107_data_type IS NULL
                        AND instr(quality_flags, 'missing_space_weather') > 0
                    )
                )
                OR (
                    ap_now IS NOT NULL AND ap_source_time_us IS NOT NULL AND f107_sfu IS NOT NULL
                    AND f107_source_time_us IS NOT NULL AND f107a_sfu IS NOT NULL
                    AND f107a_source_time_us IS NOT NULL AND f107_data_type IS NOT NULL
                    AND instr(quality_flags, 'missing_space_weather') > 0
                )),
            (SELECT count(*)
             FROM swarm_a_analysis_10min AS analysis
             JOIN swarm_a_orbit_decay_10min AS decay
                 ON decay.time_us = analysis.time_us
             JOIN swarm_a_orbit_10min AS orbit
                 ON orbit.time_us = analysis.time_us
             WHERE analysis.chunk_id != decay.chunk_id
                OR analysis.chunk_id != orbit.chunk_id),
            (SELECT count(*)
             FROM (
                 SELECT
                     time_us,
                     LAG(time_us) OVER (
                         PARTITION BY chunk_id
                         ORDER BY time_us
                     ) AS previous_time_us
                 FROM swarm_a_analysis_10min
             )
             WHERE previous_time_us IS NOT NULL
               AND time_us - previous_time_us != ?),
            (SELECT count(*)
             FROM swarm_a_orbit_decay_10min AS decay
             LEFT JOIN swarm_a_orbit_10min AS current_orbit
                 ON current_orbit.time_us = decay.time_us
             LEFT JOIN swarm_a_orbit_10min AS past_orbit
                 ON past_orbit.time_us = decay.time_us - ?
             LEFT JOIN swarm_a_orbit_10min AS past_orbit_3h
                 ON past_orbit_3h.time_us = decay.time_us - ?
             LEFT JOIN swarm_a_orbit_10min AS past_orbit_6h
                 ON past_orbit_6h.time_us = decay.time_us - ?
             WHERE current_orbit.time_us IS NULL
                OR past_orbit.time_us IS NULL
                OR current_orbit.chunk_id != decay.chunk_id
                OR past_orbit.chunk_id != decay.chunk_id
                OR past_orbit_3h.time_us IS NULL
                OR past_orbit_3h.chunk_id != decay.chunk_id
                OR past_orbit_6h.time_us IS NULL
                OR past_orbit_6h.chunk_id != decay.chunk_id
                OR abs(
                    decay.semi_major_axis_orbit_mean_m
                    - current_orbit.semi_major_axis_orbit_mean_m
                ) > ?
                OR abs(
                    decay.da_dt_3h_backward_m_s
                    - (
                        current_orbit.semi_major_axis_orbit_mean_m
                        - past_orbit_3h.semi_major_axis_orbit_mean_m
                    ) / ?
                ) > ?
                OR abs(
                    decay.da_dt_3h_backward_m_day
                    - decay.da_dt_3h_backward_m_s * ?
                ) > ?
                OR abs(
                    decay.da_dt_6h_backward_m_s
                    - (
                        current_orbit.semi_major_axis_orbit_mean_m
                        - past_orbit_6h.semi_major_axis_orbit_mean_m
                    ) / ?
                ) > ?
                OR abs(
                    decay.da_dt_6h_backward_m_day
                    - decay.da_dt_6h_backward_m_s * ?
                ) > ?
                OR abs(
                    decay.da_dt_12h_backward_m_s
                    - (
                        current_orbit.semi_major_axis_orbit_mean_m
                        - past_orbit.semi_major_axis_orbit_mean_m
                    ) / ?
                ) > ?
                OR abs(
                    decay.da_dt_12h_backward_m_day
                    - decay.da_dt_12h_backward_m_s * ?
                ) > ?)
        """,
        (MAXIMUM_ABSOLUTE_FLOAT,) * len(ANALYSIS_FLOAT_COLUMNS)
        + (
            BIN_DURATION_US,
            BACKWARD_INTERVAL_SAMPLES * BIN_DURATION_US,
            BACKWARD_INTERVALS[0][1] * BIN_DURATION_US,
            BACKWARD_INTERVALS[1][1] * BIN_DURATION_US,
            SEMI_MAJOR_AXIS_TOLERANCE_M,
            BACKWARD_INTERVALS[0][1] * BIN_DURATION_US / 1_000_000,
            DERIVATIVE_TOLERANCE_M_S,
            SECONDS_PER_DAY,
            DA_DT_PER_DAY_TOLERANCE_M_DAY,
            BACKWARD_INTERVALS[1][1] * BIN_DURATION_US / 1_000_000,
            DERIVATIVE_TOLERANCE_M_S,
            SECONDS_PER_DAY,
            DA_DT_PER_DAY_TOLERANCE_M_DAY,
            BACKWARD_INTERVAL_SECONDS,
            DERIVATIVE_TOLERANCE_M_S,
            SECONDS_PER_DAY,
            DA_DT_PER_DAY_TOLERANCE_M_DAY,
        ),
    ).fetchone()
    return {
        "row_counts": row_counts,
        "coverage_utc": {"start": utc_text(coverage[0]), "end": utc_text(coverage[1])},
        "missingness": {
            "raw_states_without_orbital_elements": missingness[0],
            "orbital_elements_without_quality": missingness[1],
            "usable_quality_without_mean_orbit": missingness[2],
            "decay_rows_without_analysis": missingness[3],
            "analysis_rows_without_decay": missingness[4],
            "future_feature_references": missingness[5],
            "invalid_pod_quality_rows": missingness[6],
            "null_analysis_values": missingness[7],
            "non_finite_analysis_rows": missingness[8],
            "invalid_optional_feature_missingness": missingness[9],
            "chunk_mismatch_rows": missingness[10],
            "non_continuous_chunk_rows": missingness[11],
            "invalid_decay_contract_rows": missingness[12],
        },
    }


def audit_release(connection, code_revision, clean_rebuild_evidence=None):
    """Input: SQLite connection, Git revision, and optional rebuild evidence
    Output: verified P1.7 release manifest"""
    if clean_rebuild_evidence is not None and not clean_rebuild_evidence:
        raise ValueError("Frozen release requires non-empty clean rebuild evidence.")

    require_tables(connection)
    integrity_check = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    if integrity_check != "ok" or foreign_key_rows:
        raise ValueError("P1.7 SQLite integrity or foreign-key check failed.")

    counts = release_counts(connection)
    failures = [
        name for name, count in counts["missingness"].items() if count != 0
    ]
    if failures:
        raise ValueError(f"P1.7 release audit failed: {', '.join(failures)}")
    if counts["row_counts"]["swarm_a_orbit_decay_10min"] != counts["row_counts"]["swarm_a_analysis_10min"]:
        raise ValueError("P1.7 analysis row count differs from decay row count.")

    used_mean_orbit_cache = (
        clean_rebuild_evidence is not None
        and "mean_orbit_cache_database" in clean_rebuild_evidence
    )
    rebuild_status = (
        "verified_mean_orbit_cache_reuse"
        if used_mean_orbit_cache
        else "clean_rebuild_verified"
        if clean_rebuild_evidence is not None
        else REBUILD_STATUS
    )
    return {
        "audit_version": AUDIT_VERSION,
        "audit_outcome": "pass",
        "sqlite_integrity_check": integrity_check,
        "foreign_key_violation_count": len(foreign_key_rows),
        "raw_inputs": raw_input_manifest(connection),
        "code_revision": code_revision,
        "code_content": phase_one_code_content(),
        "rebuild": {
            "status": rebuild_status,
            "clean_rebuild_executed": clean_rebuild_evidence is not None and not used_mean_orbit_cache,
            "evidence": clean_rebuild_evidence,
            "commands": list(REBUILD_COMMANDS),
        },
        "policies": {
            "p1_3": metadata_values(connection, P1_3_METADATA_NAMES),
            "p1_4": {
                "policy": P1_4_POLICY,
                **metadata_values(connection, P1_4_METADATA_NAMES),
            },
            "p1_5": metadata_values(connection, P1_5_METADATA_NAMES),
            "p1_6": metadata_values(connection, P1_6_METADATA_NAMES),
        },
        **counts,
    }


def write_release_metadata(
    database_path=DEFAULT_DATABASE,
    code_revision=None,
    clean_rebuild_evidence=None,
):
    """Input: SQLite path, optional Git revision, and explicit rebuild evidence
    Output: P1.7 release manifest written only after a passing audit"""
    database_path = Path(database_path)
    revision = git_revision() if code_revision is None else code_revision
    connection = sqlite3.connect(database_path)
    try:
        with connection:
            manifest = audit_release(connection, revision, clean_rebuild_evidence)
            release_status = "frozen" if clean_rebuild_evidence is not None else "working_audit_pass"
            connection.executemany(
                "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
                [
                    ("p1_7_release_audit_version", AUDIT_VERSION),
                    ("p1_7_release_status", release_status),
                    ("p1_7_release_manifest", json.dumps(manifest, sort_keys=True)),
                    ("p1_7_rebuild_commands", json.dumps(REBUILD_COMMANDS)),
                    ("p1_7_rebuild_status", manifest["rebuild"]["status"]),
                ],
            )
    finally:
        connection.close()
    return manifest


def main():
    """Input: python -m satellite_orbit.phase1.prep_09_release_audit
    Output: P1.7 release audit summary"""
    if sys.argv[1:]:
        raise ValueError("Usage: no arguments")
    manifest = write_release_metadata()
    print(f"Release audit: {manifest['audit_outcome']}")
    print(f"Analysis rows: {manifest['row_counts']['swarm_a_analysis_10min']}")
    print(f"Coverage: {manifest['coverage_utc']['start']} to {manifest['coverage_utc']['end']}")


if __name__ == "__main__":
    main()
