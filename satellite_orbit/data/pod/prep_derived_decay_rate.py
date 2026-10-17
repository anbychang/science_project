"""Write chunk-local smoothed semi-major axis and decay rates."""

import math
import sys
from pathlib import Path

import numpy
from scipy.signal import savgol_filter

from satellite_orbit.data.database.prep_raw_schema import connect_database
from satellite_orbit.data.pod.prep_derived_orbit_10min import (
    BIN_DURATION_US,
    MAXIMUM_POD_GAP_S,
    MINIMUM_POD_COUNT,
)


DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
WINDOW_SAMPLES = 73
POLYNOMIAL_ORDER = 2
EDGE_SAMPLES = WINDOW_SAMPLES // 2
ALGORITHM_VERSION = "centered_savgol_mean_orbit_v1"


def create_decay_rate_table(connection):
    """Input: SQLite connection
    Output: release-qualified decay-rate table exists"""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_a_orbit_decay_10min (
            time_us INTEGER PRIMARY KEY,
            semi_major_axis_smooth_m REAL NOT NULL,
            da_dt_smooth_m_s REAL NOT NULL,
            decay_rate_smooth_m_day REAL NOT NULL,
            chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            FOREIGN KEY (time_us) REFERENCES swarm_a_orbit_10min(time_us)
        )
        """
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
    if not math.isfinite(semi_major_axis_m):
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
    Output: [(time_us, smooth_a_m, da_dt_m_s, decay_m_day, chunk_id, version), ...]"""
    if len(run) < WINDOW_SAMPLES:
        return []

    semi_major_axis_m = numpy.array([row[1] for row in run], dtype=float)
    smooth_m = savgol_filter(semi_major_axis_m, WINDOW_SAMPLES, POLYNOMIAL_ORDER)
    derivative_m_s = savgol_filter(
        semi_major_axis_m,
        WINDOW_SAMPLES,
        POLYNOMIAL_ORDER,
        deriv=1,
        delta=BIN_DURATION_US / 1_000_000,
    )
    rows = []
    for index in range(EDGE_SAMPLES, len(run) - EDGE_SAMPLES):
        time_us, _, _, _, chunk_id = run[index]
        decay_rate_m_day = -derivative_m_s[index] * 86_400
        values = smooth_m[index], derivative_m_s[index], decay_rate_m_day
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Savitzky-Golay produced a non-finite decay value.")
        rows.append((time_us, *values, chunk_id, ALGORITHM_VERSION))
    return rows


def write_metadata(connection):
    """Input: SQLite connection
    Output: decay-rate algorithm contract is stored"""
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("orbit_decay_algorithm", ALGORITHM_VERSION),
            ("orbit_decay_window_samples", str(WINDOW_SAMPLES)),
            ("orbit_decay_polynomial_order", str(POLYNOMIAL_ORDER)),
            ("orbit_decay_center_convention", "time_us is centered sample time"),
            (
                "orbit_decay_edge_exclusion",
                "exclude 36 10-minute samples at each contiguous run edge",
            ),
            (
                "orbit_decay_run_contract",
                "single chunk_id; consecutive 600-second rows; no gap or cross-chunk fit",
            ),
            (
                "orbit_decay_rate_definition",
                "-da_dt_smooth_m_s * 86400; positive means semi-major-axis decline",
            ),
        ],
    )


def write_decay_rates(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5-B orbit rows
    Output: {input_rows, contiguous_runs, stored_rows}"""
    database_path = Path(database_path)
    with connect_database(database_path) as connection:
        with connection:
            create_decay_rate_table(connection)
            runs = contiguous_chunk_runs(orbit_rows(connection))
            rows = [row for run in runs for row in decay_rows_for_run(run)]
            connection.execute("DELETE FROM swarm_a_orbit_decay_10min")
            connection.executemany(
                "INSERT INTO swarm_a_orbit_decay_10min VALUES (?, ?, ?, ?, ?, ?)", rows
            )
            write_metadata(connection)

    return {
        "input_rows": sum(len(run) for run in runs),
        "contiguous_runs": len(runs),
        "stored_rows": len(rows),
    }


def main():
    """Input: python -m satellite_orbit.data.pod.prep_derived_decay_rate
    Output: decay-rate write summary"""
    if sys.argv[1:]:
        raise ValueError("Usage: no arguments")
    result = write_decay_rates()
    print(f"10-minute orbit input rows: {result['input_rows']}")
    print(f"Contiguous chunk runs: {result['contiguous_runs']}")
    print(f"Decay-rate rows written: {result['stored_rows']}")


if __name__ == "__main__":
    main()
