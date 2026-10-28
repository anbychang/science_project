"""Write P1.5.6 rolling raw and joint-H2/H3 decay tables."""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from phases.phase1.code.calc_rolling_phase_decay import (
    PhaseSeries,
    RESULT_H2_COS_M, RESULT_H2_SIN_M, RESULT_H3_COS_M, RESULT_H3_SIN_M,
    RESULT_JOINT_RATE, RESULT_JOINT_RESIDUAL, RESULT_JOINT_SIGMA,
    RESULT_PHASE_SPAN_RAD, RESULT_RAW_RATE, RESULT_RAW_RESIDUAL,
    RESULT_RAW_SIGMA, RESULT_SAMPLE_COUNT, RESULT_START_TIME_US, RESULT_VALID,
    calculate_window_estimate, solve_window_estimate,
)
from phases.phase0.code.data.database.prep_raw_schema import connect_database
from phases.phase1.code.prep_04_mean_orbit import MEAN_ORBIT_ELEMENTS_TABLE


DEFAULT_DATABASE = Path("phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite")
POD_QUALITY_TABLE = "swarm_a_pod_quality"
RAW_B_L_SET_TABLE = "swarm_a_phase_harmonic_decay_raw_b_l_sets_v2"
JOINT_H2_H3_SET_TABLE = "swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2"
# Retained only so the historical P1.6/P1.7 branch stays readable until it is migrated.
DECAY_CANDIDATE_TABLE = "swarm_a_phase_harmonic_decay_candidates_v1"
ORBIT_WINDOWS = (3, 5)
MAXIMUM_SOURCE_GAP_S = 20.0
BATCH_OUTPUT_COUNT = 100_000
ALGORITHM_VERSION = "trailing_exact_phase_h2_h3_rolling_ols_v2"
REJECT_INITIAL = "initial"
REJECT_GAP = "gap_in_window"
REJECT_NON_MONOTONIC_PHASE = "non_monotonic_phase"


@dataclass(frozen=True)
class PhaseSegment:
    """Input: one chunk's continuous B-L phase data and boundary cause.
    Output: immutable source segment for exact 3/5-phase-orbit estimators."""

    chunk_id: int
    source_series: PhaseSeries
    initial_reject_reason: str


def create_decay_candidate_table(connection):
    """Input: SQLite connection.
    Output: retained legacy P1.5.6 long table exists for old P1.6/P1.7 readers."""
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {DECAY_CANDIDATE_TABLE} (
            time_us INTEGER NOT NULL,
            decay_method TEXT NOT NULL,
            orbit_window INTEGER NOT NULL,
            decay_rate_m_day REAL NOT NULL,
            decay_rate_1sigma_m_day REAL NOT NULL,
            fit_residual_std_m REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            window_start_time_us INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            harmonic_orders TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (time_us, decay_method, orbit_window)
        )
    """)


def create_decay_tables(connection):
    """Input: SQLite connection.
    Output: two versioned P1.5.6 raw/joint derived tables exist."""
    _create_raw_table(connection)
    _create_joint_table(connection)


def _create_raw_table(connection):
    """Input: SQLite connection.
    Output: one raw B-L rolling-estimator table exists."""
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {RAW_B_L_SET_TABLE} (
            time_us INTEGER PRIMARY KEY,
            chunk_id INTEGER NOT NULL,
            orbit_3_window_start_time_us INTEGER,
            orbit_3_sample_count INTEGER,
            orbit_3_phase_span_rad REAL,
            orbit_3_decay_rate_m_s REAL,
            orbit_3_decay_rate_1sigma_m_s REAL,
            orbit_3_fit_residual_std_m REAL,
            orbit_3_reject_reason TEXT,
            orbit_5_window_start_time_us INTEGER,
            orbit_5_sample_count INTEGER,
            orbit_5_phase_span_rad REAL,
            orbit_5_decay_rate_m_s REAL,
            orbit_5_decay_rate_1sigma_m_s REAL,
            orbit_5_fit_residual_std_m REAL,
            orbit_5_reject_reason TEXT,
            algorithm_version TEXT NOT NULL
        )
    """)


def _create_joint_table(connection):
    """Input: SQLite connection.
    Output: one joint-H2/H3 rolling-estimator table exists."""
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {JOINT_H2_H3_SET_TABLE} (
            time_us INTEGER PRIMARY KEY,
            chunk_id INTEGER NOT NULL,
            orbit_3_window_start_time_us INTEGER,
            orbit_3_sample_count INTEGER,
            orbit_3_phase_span_rad REAL,
            orbit_3_decay_rate_m_s REAL,
            orbit_3_decay_rate_1sigma_m_s REAL,
            orbit_3_fit_residual_std_m REAL,
            orbit_3_h2_cos_m REAL,
            orbit_3_h2_sin_m REAL,
            orbit_3_h3_cos_m REAL,
            orbit_3_h3_sin_m REAL,
            orbit_3_reject_reason TEXT,
            orbit_5_window_start_time_us INTEGER,
            orbit_5_sample_count INTEGER,
            orbit_5_phase_span_rad REAL,
            orbit_5_decay_rate_m_s REAL,
            orbit_5_decay_rate_1sigma_m_s REAL,
            orbit_5_fit_residual_std_m REAL,
            orbit_5_h2_cos_m REAL,
            orbit_5_h2_sin_m REAL,
            orbit_5_h3_cos_m REAL,
            orbit_5_h3_sin_m REAL,
            orbit_5_reject_reason TEXT,
            harmonic_orders TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        )
    """)


def source_chunk_ids(connection):
    """Input: SQLite connection with usable P1.5.1 mean elements.
    Output: ordered chunk IDs containing valid B-L phase-estimator inputs."""
    return [row[0] for row in connection.execute(f"""
        SELECT DISTINCT quality.chunk_id
        FROM {MEAN_ORBIT_ELEMENTS_TABLE} AS mean
        JOIN {POD_QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1 AND quality.chunk_id IS NOT NULL
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
        ORDER BY quality.chunk_id
    """)]


def load_chunk_phase_series(connection, chunk_id):
    """Input: SQLite connection and usable-POD chunk ID.
    Output: {time_us[], a_m[], wrapped_u_rad[]} arrays for that chunk."""
    filters = """
        quality.is_usable = 1 AND quality.chunk_id = ?
        AND mean.rejection_reason IS NULL
        AND mean.mean_semi_major_axis_m IS NOT NULL
        AND mean.mean_argument_of_perigee_rad IS NOT NULL
        AND mean.mean_anomaly_rad IS NOT NULL
    """
    row_count = connection.execute(f"""
        SELECT COUNT(*) FROM {MEAN_ORBIT_ELEMENTS_TABLE} AS mean
        JOIN {POD_QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE {filters}
    """, (chunk_id,)).fetchone()[0]
    time_us = np.empty(row_count, dtype=np.int64)
    values = np.empty((row_count, 2), dtype=np.float64)
    cursor = connection.execute(f"""
        SELECT mean.time_us, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad + mean.mean_anomaly_rad
        FROM {MEAN_ORBIT_ELEMENTS_TABLE} AS mean
        JOIN {POD_QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE {filters}
        ORDER BY mean.time_us
    """, (chunk_id,))
    for index, row in enumerate(cursor):
        time_us[index] = row[0]
        values[index, 0] = row[1]
        values[index, 1] = row[2]
    return time_us, values


def phase_segments(chunk_id, time_us, values):
    """Input: one chunk's time/a/wrapped-u arrays.
    Output: PhaseSegment values without gaps or backward phase steps."""
    initial_reason = REJECT_INITIAL
    gap_starts = np.flatnonzero(
        np.diff(time_us) / 1_000_000 > MAXIMUM_SOURCE_GAP_S,
    ) + 1
    run_start = 0
    for run_stop in (*gap_starts, len(time_us)):
        yield from _continuous_phase_segments(
            chunk_id, time_us[run_start:run_stop], values[run_start:run_stop],
            initial_reason,
        )
        run_start = run_stop
        initial_reason = REJECT_GAP


def _continuous_phase_segments(chunk_id, time_us, values, initial_reason):
    """Input: one time-continuous chunk slice with wrapped phase.
    Output: PhaseSegments split only where unwrapped `u` moves backward."""
    unwrapped_values = values.copy()
    unwrapped_values[:, 1] = np.unwrap(unwrapped_values[:, 1])
    phase_starts = np.flatnonzero(np.diff(unwrapped_values[:, 1]) <= 0.0) + 1
    segment_start = 0
    reason = initial_reason
    for segment_stop in (*phase_starts, len(time_us)):
        if segment_start < segment_stop:
            yield _phase_segment(
                chunk_id, time_us[segment_start:segment_stop],
                unwrapped_values[segment_start:segment_stop], reason,
            )
        segment_start = segment_stop
        reason = REJECT_NON_MONOTONIC_PHASE


def _phase_segment(chunk_id, time_us, values, initial_reject_reason):
    """Input: continuous wrapped phase slice and its boundary reason.
    Output: PhaseSegment with unwrapped, strictly increasing `u`."""
    return PhaseSegment(
        chunk_id, PhaseSeries(time_us, values), initial_reject_reason,
    )


def write_decay_candidates(database_path=DEFAULT_DATABASE, resume=False):
    """Input: SQLite path and optional resume flag for completed source chunks.
    Output: {source_rows, raw_rows, joint_rows} for P1.5.6 v2 tables."""
    connection = connect_database(Path(database_path))
    try:
        with connection:
            create_decay_tables(connection)
            if not resume:
                connection.execute(f"DELETE FROM {RAW_B_L_SET_TABLE}")
                connection.execute(f"DELETE FROM {JOINT_H2_H3_SET_TABLE}")
        source_rows = raw_rows = joint_rows = 0
        for chunk_id in source_chunk_ids(connection):
            time_us, values = load_chunk_phase_series(connection, chunk_id)
            source_rows += len(time_us)
            if resume and _chunk_is_complete(connection, chunk_id, len(time_us)):
                raw_rows += len(time_us)
                joint_rows += len(time_us)
                continue
            with connection:
                connection.execute(
                    f"DELETE FROM {RAW_B_L_SET_TABLE} WHERE chunk_id = ?",
                    (chunk_id,),
                )
                connection.execute(
                    f"DELETE FROM {JOINT_H2_H3_SET_TABLE} WHERE chunk_id = ?",
                    (chunk_id,),
                )
            for segment in phase_segments(chunk_id, time_us, values):
                stored = _write_phase_segment(connection, segment)
                raw_rows += stored
                joint_rows += stored
        with connection:
            _write_metadata(connection, source_rows, raw_rows, joint_rows)
    finally:
        connection.close()
    return {"source_rows": source_rows, "raw_rows": raw_rows, "joint_rows": joint_rows}


def _chunk_is_complete(connection, chunk_id, expected_row_count):
    """Input: SQLite connection, chunk key, and expected 10-second row count.
    Output: whether both P1.5.6 method tables already contain that full chunk."""
    raw_count = connection.execute(
        f"SELECT COUNT(*) FROM {RAW_B_L_SET_TABLE} WHERE chunk_id = ?",
        (chunk_id,),
    ).fetchone()[0]
    joint_count = connection.execute(
        f"SELECT COUNT(*) FROM {JOINT_H2_H3_SET_TABLE} WHERE chunk_id = ?",
        (chunk_id,),
    ).fetchone()[0]
    return raw_count == expected_row_count and joint_count == expected_row_count


def _write_phase_segment(connection, segment):
    """Input: SQLite connection and one continuous PhaseSegment.
    Output: matching raw/joint row count written for that segment."""
    series = segment.source_series
    stored_rows = 0
    for start_index in range(0, len(series.time_us), BATCH_OUTPUT_COUNT):
        stop_index = min(start_index + BATCH_OUTPUT_COUNT, len(series.time_us))
        batch_start = _batch_start_index(series, start_index)
        batch = PhaseSeries(series.time_us[batch_start:stop_index],
                            series.values[batch_start:stop_index])
        estimates = {
            orbit_count: solve_window_estimate(calculate_window_estimate(
                batch, orbit_count,
            ))[start_index - batch_start:]
            for orbit_count in ORBIT_WINDOWS
        }
        times = series.time_us[start_index:stop_index]
        connection.executemany(
            f"INSERT INTO {RAW_B_L_SET_TABLE} VALUES ({', '.join('?' for _ in range(17))})",
            _raw_table_rows(times, segment, estimates),
        )
        connection.executemany(
            f"INSERT INTO {JOINT_H2_H3_SET_TABLE} VALUES ({', '.join('?' for _ in range(26))})",
            _joint_table_rows(times, segment, estimates),
        )
        connection.commit()
        stored_rows += len(times)
    return stored_rows


def _batch_start_index(series, output_start_index):
    """Input: PhaseSeries and first requested output index in a batch.
    Output: earliest source index needed for an exact 5-orbit trailing window."""
    span_rad = max(ORBIT_WINDOWS) * 2.0 * np.pi
    target_phase = series.values[output_start_index, 1] - span_rad
    return max(0, int(np.searchsorted(series.values[:, 1], target_phase, side="right")) - 1)


def _raw_table_rows(time_us, segment, estimates):
    """Input: time keys, PhaseSegment, and {orbit_count: estimate[]}.
    Output: raw-B-L SQLite rows with 3/5-orbit values in one row per time."""
    return [
        (int(time_value), segment.chunk_id,
         *_raw_window_columns(estimates[3][index], 3, segment),
         *_raw_window_columns(estimates[5][index], 5, segment),
         ALGORITHM_VERSION)
        for index, time_value in enumerate(time_us)
    ]


def _joint_table_rows(time_us, segment, estimates):
    """Input: time keys, PhaseSegment, and {orbit_count: estimate[]}.
    Output: joint-H2/H3 rows with coefficients and 3/5-orbit values."""
    return [
        (int(time_value), segment.chunk_id,
         *_joint_window_columns(estimates[3][index], 3, segment),
         *_joint_window_columns(estimates[5][index], 5, segment),
         "2,3", ALGORITHM_VERSION)
        for index, time_value in enumerate(time_us)
    ]


def _raw_window_columns(result, orbit_count, segment):
    """Input: one estimate result, orbit count, and PhaseSegment.
    Output: raw table's {window, fit, reject} values for one orbit count."""
    return (
        _integer_or_none(result[RESULT_START_TIME_US]),
        _integer_or_none(result[RESULT_SAMPLE_COUNT]),
        _float_or_none(result[RESULT_PHASE_SPAN_RAD]),
        _float_or_none(result[RESULT_RAW_RATE]),
        _float_or_none(result[RESULT_RAW_SIGMA]),
        _float_or_none(result[RESULT_RAW_RESIDUAL]),
        _reject_reason(result, orbit_count, segment),
    )


def _joint_window_columns(result, orbit_count, segment):
    """Input: one estimate result, orbit count, and PhaseSegment.
    Output: joint table's {window, fit, H2/H3, reject} values."""
    return (
        _integer_or_none(result[RESULT_START_TIME_US]),
        _integer_or_none(result[RESULT_SAMPLE_COUNT]),
        _float_or_none(result[RESULT_PHASE_SPAN_RAD]),
        _float_or_none(result[RESULT_JOINT_RATE]),
        _float_or_none(result[RESULT_JOINT_SIGMA]),
        _float_or_none(result[RESULT_JOINT_RESIDUAL]),
        _float_or_none(result[RESULT_H2_COS_M]),
        _float_or_none(result[RESULT_H2_SIN_M]),
        _float_or_none(result[RESULT_H3_COS_M]),
        _float_or_none(result[RESULT_H3_SIN_M]),
        _reject_reason(result, orbit_count, segment),
    )


def _reject_reason(result, orbit_count, segment):
    """Input: estimate result, requested orbit count, and PhaseSegment.
    Output: NULL for valid fit, otherwise its explicit boundary reason."""
    if result[RESULT_VALID] == 1.0:
        return None
    if segment.initial_reject_reason == REJECT_INITIAL:
        return f"insufficient_{orbit_count}_orbits"
    return segment.initial_reject_reason


def _integer_or_none(value):
    """Input: scalar float that may represent missing SQLite integer data.
    Output: int for finite value, otherwise None."""
    return int(round(value)) if np.isfinite(value) else None


def _float_or_none(value):
    """Input: scalar float that may represent missing SQLite REAL data.
    Output: float for finite value, otherwise None."""
    return float(value) if np.isfinite(value) else None


def _write_metadata(connection, source_rows, raw_rows, joint_rows):
    """Input: SQLite connection and completed P1.5.6 row counts.
    Output: v2 estimator identity, units, and table counts in metadata."""
    connection.executemany("INSERT OR REPLACE INTO metadata VALUES (?, ?)", [
        ("p1_5_6_v2_algorithm", ALGORITHM_VERSION),
        ("p1_5_6_v2_tables", f"{RAW_B_L_SET_TABLE},{JOINT_H2_H3_SET_TABLE}"),
        ("p1_5_6_v2_units", "decay_rate_m_s,1sigma_m_s,residual_m,phase_rad"),
        ("p1_5_6_v2_source_rows", str(source_rows)),
        ("p1_5_6_v2_raw_rows", str(raw_rows)),
        ("p1_5_6_v2_joint_rows", str(joint_rows)),
    ])


def validate_decay_tables(database_path=DEFAULT_DATABASE):
    """Input: SQLite path after P1.5.6 v2 write.
    Output: {raw_rows, joint_rows, unmatched_rows, validity_mismatches}."""
    connection = sqlite3.connect(Path(database_path))
    try:
        raw_rows = connection.execute(f"SELECT COUNT(*) FROM {RAW_B_L_SET_TABLE}").fetchone()[0]
        joint_rows = connection.execute(f"SELECT COUNT(*) FROM {JOINT_H2_H3_SET_TABLE}").fetchone()[0]
        unmatched_rows = connection.execute(f"""
            SELECT COUNT(*) FROM {RAW_B_L_SET_TABLE} AS raw
            LEFT JOIN {JOINT_H2_H3_SET_TABLE} AS joint ON joint.time_us = raw.time_us
            WHERE joint.time_us IS NULL
            UNION ALL
            SELECT COUNT(*) FROM {JOINT_H2_H3_SET_TABLE} AS joint
            LEFT JOIN {RAW_B_L_SET_TABLE} AS raw ON raw.time_us = joint.time_us
            WHERE raw.time_us IS NULL
        """).fetchall()
        validity_mismatches = connection.execute(f"""
            SELECT COUNT(*) FROM {RAW_B_L_SET_TABLE} AS raw
            JOIN {JOINT_H2_H3_SET_TABLE} AS joint ON joint.time_us = raw.time_us
            WHERE (raw.orbit_3_decay_rate_m_s IS NULL) != (joint.orbit_3_decay_rate_m_s IS NULL)
               OR (raw.orbit_5_decay_rate_m_s IS NULL) != (joint.orbit_5_decay_rate_m_s IS NULL)
        """).fetchone()[0]
    finally:
        connection.close()
    return {"raw_rows": raw_rows, "joint_rows": joint_rows,
            "unmatched_rows": sum(row[0] for row in unmatched_rows),
            "validity_mismatches": validity_mismatches}


def main():
    """Input: python -m ...prep_14_phase_harmonic_decay_candidates [DATABASE].
    Output: P1.5.6 v2 raw/joint row counts and validation summary."""
    arguments = sys.argv[1:]
    if len(arguments) > 2:
        raise ValueError("Usage: [DATABASE [--resume]]")
    database_path = Path(arguments[0]) if arguments else DEFAULT_DATABASE
    resume = len(arguments) == 2 and arguments[1] == "--resume"
    if len(arguments) == 2 and not resume:
        raise ValueError("Usage: [DATABASE [--resume]]")
    result = write_decay_candidates(database_path, resume)
    validation = validate_decay_tables(database_path)
    print(f"P1.5.6 v2 source rows: {result['source_rows']}")
    print(f"P1.5.6 v2 raw rows: {result['raw_rows']}")
    print(f"P1.5.6 v2 joint rows: {result['joint_rows']}")
    print(f"P1.5.6 v2 unmatched rows: {validation['unmatched_rows']}")


if __name__ == "__main__":
    main()
