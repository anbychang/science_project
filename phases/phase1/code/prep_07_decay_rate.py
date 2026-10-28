"""Write chunk-local 3-, 6-, and 12-hour backward semi-major-axis rates."""

import sys
from math import isfinite
from pathlib import Path

from phases.phase0.code.data.database.prep_raw_schema import connect_database
from phases.phase1.code.prep_06_orbit_10min import (
    BIN_DURATION_US,
    MAXIMUM_POD_GAP_S,
    MINIMUM_POD_COUNT,
)


DEFAULT_DATABASE = Path("phases/phase1/data/sqlite/swarm_a_analysis.sqlite")
BACKWARD_INTERVALS = ((3, 18), (6, 36), (12, 72))
BACKWARD_INTERVAL_SAMPLES = BACKWARD_INTERVALS[-1][1]
BACKWARD_INTERVAL_SECONDS = BACKWARD_INTERVAL_SAMPLES * BIN_DURATION_US / 1_000_000
SECONDS_PER_DAY = 86_400
ALGORITHM_VERSION = "backward_difference_3h_6h_12h_mean_orbit_v3"
DECAY_COLUMNS = {
    "time_us",
    "semi_major_axis_orbit_mean_m",
    "da_dt_3h_backward_m_s",
    "da_dt_3h_backward_m_day",
    "da_dt_6h_backward_m_s",
    "da_dt_6h_backward_m_day",
    "da_dt_12h_backward_m_s",
    "da_dt_12h_backward_m_day",
    "chunk_id",
    "algorithm_version",
}


def create_decay_rate_table(connection):
    """Input: SQLite connection
    Output: release-qualified decay-rate table exists"""
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(swarm_a_orbit_decay_10min)")
    }
    if existing_columns and existing_columns != DECAY_COLUMNS:
        require_empty_analysis_for_decay_schema_migration(connection)
        connection.execute("DROP TABLE swarm_a_orbit_decay_10min")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_a_orbit_decay_10min (
            time_us INTEGER PRIMARY KEY,
            semi_major_axis_orbit_mean_m REAL NOT NULL,
            da_dt_3h_backward_m_s REAL NOT NULL,
            da_dt_3h_backward_m_day REAL NOT NULL,
            da_dt_6h_backward_m_s REAL NOT NULL,
            da_dt_6h_backward_m_day REAL NOT NULL,
            da_dt_12h_backward_m_s REAL NOT NULL,
            da_dt_12h_backward_m_day REAL NOT NULL,
            chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            FOREIGN KEY (time_us) REFERENCES swarm_a_orbit_10min(time_us)
        )
        """
    )


def require_empty_analysis_for_decay_schema_migration(connection):
    """Input: SQLite connection
    Output: decay schema migration cannot orphan analysis rows"""
    analysis_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'swarm_a_analysis_10min'"
    ).fetchone()
    if analysis_exists and connection.execute(
        "SELECT 1 FROM swarm_a_analysis_10min LIMIT 1"
    ).fetchone():
        raise ValueError(
            "Cannot migrate decay schema while analysis output exists. "
            "Use a new target with write_phase1_rebuild."
        )


def clear_analysis_rows(connection):
    """Input: SQLite connection
    Output: stale final analysis rows removed when present"""
    analysis_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'swarm_a_analysis_10min'"
    ).fetchone()
    if analysis_exists:
        connection.execute("DELETE FROM swarm_a_analysis_10min")


def clear_release_audit_metadata(connection):
    """Input: SQLite connection
    Output: stale P1.7 release evidence removed"""
    connection.executemany(
        "DELETE FROM metadata WHERE name = ?",
        [
            ("p1_7_release_audit_version",),
            ("p1_7_release_status",),
            ("p1_7_release_manifest",),
            ("p1_7_rebuild_commands",),
            ("p1_7_rebuild_status",),
        ],
    )


def orbit_rows(connection):
    """Input: SQLite connection with 10-minute orbit rows
    Output: [(time_us, semi_major_axis_m, pod_count, gap_s, chunk_id), ...]"""
    return connection.execute(
        """
        SELECT time_us, semi_major_axis_orbit_mean_m, pod_count, max_pod_gap_s, chunk_id
        FROM swarm_a_orbit_10min
        ORDER BY chunk_id, time_us
        """
    ).fetchall()


def validate_orbit_row(row):
    """Input: one 10-minute orbit row
    Output: row is valid for the decay-rate stage"""
    _, semi_major_axis_m, pod_count, max_pod_gap_s, chunk_id = row
    if chunk_id is None:
        raise ValueError("Orbit row has no chunk_id.")
    if pod_count < MINIMUM_POD_COUNT:
        raise ValueError("Orbit row has too few POD observations.")
    if max_pod_gap_s > MAXIMUM_POD_GAP_S:
        raise ValueError("Orbit row has a POD gap longer than 10 seconds.")
    if not isfinite(semi_major_axis_m):
        raise ValueError("Orbit row has a non-finite semi-major axis.")


def contiguous_chunk_runs(rows):
    """Input: ordered 10-minute rows
    Output: [[row, ...], ...] split at chunk boundaries and time gaps"""
    runs = []
    current_run = []
    previous_row = None
    for row in rows:
        validate_orbit_row(row)
        if previous_row is None or (
            row[4] == previous_row[4]
            and row[0] - previous_row[0] == BIN_DURATION_US
        ):
            current_run.append(row)
        else:
            runs.append(current_run)
            current_run = [row]
        previous_row = row
    if current_run:
        runs.append(current_run)
    return runs


def decay_rows_for_run(run):
    """Input: one contiguous chunk-local orbit run
    Output: [(time_us, mean_a_m, 3h/6h/12h rates, chunk_id, version), ...]"""
    if len(run) <= BACKWARD_INTERVAL_SAMPLES:
        return []

    rows = []
    for index in range(BACKWARD_INTERVAL_SAMPLES, len(run)):
        time_us, semi_major_axis_m, _, _, chunk_id = run[index]
        rate_values = []
        for _, interval_samples in BACKWARD_INTERVALS:
            interval_seconds = interval_samples * BIN_DURATION_US / 1_000_000
            past_semi_major_axis_m = run[index - interval_samples][1]
            derivative_m_s = (
                semi_major_axis_m - past_semi_major_axis_m
            ) / interval_seconds
            rate_values.extend((derivative_m_s, derivative_m_s * SECONDS_PER_DAY))
        rows.append(
            (
                time_us,
                semi_major_axis_m,
                *rate_values,
                chunk_id,
                ALGORITHM_VERSION,
            )
        )
    return rows


def write_metadata(connection):
    """Input: SQLite connection
    Output: decay-rate algorithm contract is stored"""
    connection.executemany(
        "DELETE FROM metadata WHERE name = ?",
        [
            ("orbit_decay_window_samples",),
            ("orbit_decay_polynomial_order",),
            ("orbit_decay_center_convention",),
        ],
    )
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("orbit_decay_algorithm", ALGORITHM_VERSION),
            ("orbit_decay_interval_hours", "3,6,12"),
            ("orbit_decay_interval_samples", "18,36,72"),
            ("orbit_decay_interval_seconds", "10800.0,21600.0,43200.0"),
            ("orbit_decay_time_convention", "time_us is interval end time"),
            (
                "orbit_decay_edge_exclusion",
                "exclude first 72 10-minute samples of each contiguous run so all windows exist",
            ),
            (
                "orbit_decay_run_contract",
                "single chunk_id; consecutive 600-second rows; no gap or cross-chunk interval",
            ),
            (
                "orbit_decay_rate_definition",
                "for each H in 3,6,12: (a(t) - a(t - H)) / H * 86400; negative means semi-major-axis decline",
            ),
        ],
    )


def write_decay_rates(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5-B orbit rows
    Output: {input_rows, contiguous_runs, stored_rows}"""
    database_path = Path(database_path)
    with connect_database(database_path) as connection:
        with connection:
            clear_analysis_rows(connection)
            clear_release_audit_metadata(connection)
            create_decay_rate_table(connection)
            runs = contiguous_chunk_runs(orbit_rows(connection))
            rows = [row for run in runs for row in decay_rows_for_run(run)]
            connection.execute("DELETE FROM swarm_a_orbit_decay_10min")
            connection.executemany(
                "INSERT INTO swarm_a_orbit_decay_10min VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
            )
            write_metadata(connection)

    return {
        "input_rows": sum(len(run) for run in runs),
        "contiguous_runs": len(runs),
        "stored_rows": len(rows),
    }


def main():
    """Input: python -m phases.phase1.code.prep_07_decay_rate
    Output: signed semi-major-axis-rate write summary"""
    if sys.argv[1:]:
        raise ValueError("Usage: no arguments")
    result = write_decay_rates()
    print(f"10-minute orbit input rows: {result['input_rows']}")
    print(f"Contiguous chunk runs: {result['contiguous_runs']}")
    print(f"Semi-major-axis-rate rows written: {result['stored_rows']}")


if __name__ == "__main__":
    main()
