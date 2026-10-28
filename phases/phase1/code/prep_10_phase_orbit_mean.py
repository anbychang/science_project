"""Write chunk-local phase-orbit moments and decay-slope candidates."""

import sys
from collections import deque
from dataclasses import dataclass
from math import cos, floor, hypot, pi, sin
from pathlib import Path
from statistics import median

from phases.phase1.code.calc_orbit_decay_diagnostics import (
    ordinary_least_squares,
)
from phases.phase0.code.data.database.prep_raw_schema import connect_database


DEFAULT_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
)
MEAN_ORBIT_TABLE = "swarm_a_mean_orbit_elements_v1"
PHASE_ORBIT_TABLE = "swarm_a_phase_orbit_mean_v2"
HARMONIC_DIAGNOSTIC_TABLE = "swarm_a_phase_harmonic_diagnostic_v1"
DAILY_DECAY_TABLE = "swarm_a_phase_orbit_decay_daily_v2"
LOCAL_DECAY_TABLE = "swarm_a_phase_orbit_decay_local_v1"
TRAILING_DECAY_TABLE = "swarm_a_phase_harmonic_decay_trailing_1h_v1"
TWO_PI = 2.0 * pi
MAXIMUM_POD_GAP_S = 10.0
MINIMUM_ORBIT_SAMPLES = 500
MINIMUM_PHASE_COVERAGE_RAD = TWO_PI - 0.05
MINIMUM_ORBITS_PER_DAILY_FIT = 10
MINIMUM_ORBITS_PER_LOCAL_FIT = 6
LOCAL_WINDOW_HOURS = (12, 24)
MINIMUM_LOCAL_WINDOW_COVERAGE = 0.9
MICROSECONDS_PER_SECOND = 1_000_000
MICROSECONDS_PER_DAY = 86_400_000_000
SECONDS_PER_DAY = 86_400
PHASE_SCOPE_PADDING_US = 2 * 60 * 60 * MICROSECONDS_PER_SECOND
TRAILING_WINDOW_SECONDS = 3_600
TRAILING_WINDOW_US = TRAILING_WINDOW_SECONDS * MICROSECONDS_PER_SECOND
TRAILING_OUTPUT_INTERVAL_SECONDS = 600
TRAILING_OUTPUT_INTERVAL_US = TRAILING_OUTPUT_INTERVAL_SECONDS * MICROSECONDS_PER_SECOND
TRAILING_FIT_SAMPLE_INTERVAL_SECONDS = 10
TRAILING_FIT_SAMPLE_INTERVAL_US = (
    TRAILING_FIT_SAMPLE_INTERVAL_SECONDS * MICROSECONDS_PER_SECOND
)
MINIMUM_TRAILING_COVERAGE = 0.9
MINIMUM_TRAILING_SAMPLES = int(
    TRAILING_WINDOW_SECONDS
    / TRAILING_FIT_SAMPLE_INTERVAL_SECONDS
    * MINIMUM_TRAILING_COVERAGE,
)
ALGORITHM_VERSION = "phase_weighted_orbit_h2_h3_local_ols_v1"
TRAILING_ALGORITHM_VERSION = "phase_orbit_h2_h3_subtracted_trailing_1h_ols_v2"


@dataclass(frozen=True)
class PhaseSample:
    """Input: one usable mean-element sample
    Output: phase-domain sample within one chunk"""

    chunk_id: int
    time_us: int
    semi_major_axis_m: float
    phase_rad: float


@dataclass(frozen=True)
class MeanElementSample:
    """Input: one usable mean-element sample
    Output: time, a, and phase for a trailing local fit"""

    chunk_id: int
    time_us: int
    semi_major_axis_m: float
    phase_rad: float


def create_phase_orbit_tables(connection):
    """Input: SQLite connection
    Output: P1.5.4--P1.5.6 derived tables exist"""
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {PHASE_ORBIT_TABLE} (
            time_us INTEGER PRIMARY KEY, orbit_start_time_us INTEGER NOT NULL,
            phase_weighted_mean_semi_major_axis_m REAL NOT NULL,
            h2_cosine_m REAL NOT NULL, h2_sine_m REAL NOT NULL, h2_amplitude_m REAL NOT NULL,
            h3_cosine_m REAL NOT NULL, h3_sine_m REAL NOT NULL, h3_amplitude_m REAL NOT NULL,
            pod_count INTEGER NOT NULL, phase_coverage_rad REAL NOT NULL,
            max_pod_gap_s REAL NOT NULL, chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        )
    """)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {HARMONIC_DIAGNOSTIC_TABLE} (
            chunk_id INTEGER PRIMARY KEY, orbit_count INTEGER NOT NULL,
            h2_amplitude_median_m REAL NOT NULL, h2_amplitude_max_m REAL NOT NULL,
            h3_amplitude_median_m REAL NOT NULL, h3_amplitude_max_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        )
    """)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {DAILY_DECAY_TABLE} (
            time_us INTEGER PRIMARY KEY, utc_day_start_us INTEGER NOT NULL,
            daily_decay_rate_m_day REAL NOT NULL, daily_decay_rate_1sigma_m_day REAL NOT NULL,
            fit_residual_std_m REAL NOT NULL, orbit_count INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL, algorithm_version TEXT NOT NULL
        )
    """)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {LOCAL_DECAY_TABLE} (
            time_us INTEGER NOT NULL, window_hours INTEGER NOT NULL,
            local_decay_rate_m_day REAL NOT NULL, local_decay_rate_1sigma_m_day REAL NOT NULL,
            fit_residual_std_m REAL NOT NULL, orbit_count INTEGER NOT NULL,
            window_start_time_us INTEGER NOT NULL, window_stop_time_us INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL, algorithm_version TEXT NOT NULL,
            PRIMARY KEY (time_us, window_hours)
        )
    """)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {TRAILING_DECAY_TABLE} (
            time_us INTEGER PRIMARY KEY, trailing_window_start_time_us INTEGER NOT NULL,
            decay_rate_m_day REAL NOT NULL, decay_rate_1sigma_m_day REAL NOT NULL,
            fit_residual_std_m REAL NOT NULL, sample_count INTEGER NOT NULL,
            phase_coverage_rad REAL NOT NULL, max_pod_gap_s REAL NOT NULL,
            chunk_id INTEGER NOT NULL, algorithm_version TEXT NOT NULL
        )
    """)


def usable_mean_element_rows(connection):
    """Input: SQLite connection
    Output: ordered rows {chunk_id, time_us, mean a, omega, M}"""
    return connection.execute(f"""
        SELECT quality.chunk_id, mean.time_us, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN swarm_a_pod_quality AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1 AND quality.chunk_id IS NOT NULL
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
        ORDER BY quality.chunk_id, mean.time_us
    """)


def unwrapped_phase(raw_phase_rad, previous_raw_phase_rad, previous_phase_rad):
    """Input: raw phase and prior raw/unwrapped phase in rad
    Output: continuous phase in rad"""
    if previous_raw_phase_rad is None:
        return raw_phase_rad
    phase_increment_rad = (raw_phase_rad - previous_raw_phase_rad + pi) % TWO_PI - pi
    return previous_phase_rad + phase_increment_rad


def phase_weights(samples):
    """Input: [PhaseSample, ...] from one orbit
    Output: trapezoidal phase weights in rad"""
    phases = [sample.phase_rad for sample in samples]
    if len(phases) < 2:
        return []
    return [(phases[1] - phases[0]) / 2.0, *(
        (right_phase - left_phase) / 2.0
        for left_phase, right_phase in zip(phases, phases[2:])
    ), (phases[-1] - phases[-2]) / 2.0]


def harmonic_coefficient(samples, weights, harmonic_order, trig_function):
    """Input: samples, weights, harmonic order, and sine/cosine
    Output: phase Fourier coefficient in m"""
    phase_weight_sum = sum(weights)
    mean_a_m = sum(weight * sample.semi_major_axis_m for sample, weight in zip(samples, weights)) / phase_weight_sum
    return 2.0 * sum(
        weight * (sample.semi_major_axis_m - mean_a_m)
        * trig_function(harmonic_order * sample.phase_rad)
        for sample, weight in zip(samples, weights)
    ) / phase_weight_sum


def accepted_orbit_row(samples):
    """Input: [PhaseSample, ...] from one candidate orbit
    Output: phase-orbit row, or None when incomplete"""
    if len(samples) < MINIMUM_ORBIT_SAMPLES:
        return None
    weights = phase_weights(samples)
    phase_coverage_rad = samples[-1].phase_rad - samples[0].phase_rad
    maximum_gap_s = max(
        (later.time_us - earlier.time_us) / MICROSECONDS_PER_SECOND
        for earlier, later in zip(samples, samples[1:])
    )
    if phase_coverage_rad < MINIMUM_PHASE_COVERAGE_RAD or maximum_gap_s > MAXIMUM_POD_GAP_S:
        return None
    phase_weight_sum = sum(weights)
    mean_a_m = sum(weight * sample.semi_major_axis_m for sample, weight in zip(samples, weights)) / phase_weight_sum
    h2_cosine_m = harmonic_coefficient(samples, weights, 2, cos)
    h2_sine_m = harmonic_coefficient(samples, weights, 2, sin)
    h3_cosine_m = harmonic_coefficient(samples, weights, 3, cos)
    h3_sine_m = harmonic_coefficient(samples, weights, 3, sin)
    return (
        samples[-1].time_us, samples[0].time_us, mean_a_m,
        h2_cosine_m, h2_sine_m, hypot(h2_cosine_m, h2_sine_m),
        h3_cosine_m, h3_sine_m, hypot(h3_cosine_m, h3_sine_m),
        len(samples), phase_coverage_rad, maximum_gap_s, samples[-1].chunk_id,
        ALGORITHM_VERSION,
    )


def phase_orbit_rows(rows):
    """Input: ordered rows {chunk_id, time_us, mean a, omega, M}
    Output: phase-weighted rows, never crossing chunk or source gap"""
    current_samples = []
    previous_row = None
    previous_raw_phase_rad = None
    previous_phase_rad = None
    orbit_number = None
    for row in rows:
        chunk_id, time_us, semi_major_axis_m, omega_rad, mean_anomaly_rad = row
        new_chunk = previous_row is not None and chunk_id != previous_row[0]
        source_gap = previous_row is not None and (
            time_us - previous_row[1]
        ) / MICROSECONDS_PER_SECOND > MAXIMUM_POD_GAP_S
        if new_chunk or source_gap:
            accepted_row = accepted_orbit_row(current_samples)
            if accepted_row is not None:
                yield accepted_row
            current_samples = []
            previous_raw_phase_rad = None
            previous_phase_rad = None
            orbit_number = None
        raw_phase_rad = (omega_rad + mean_anomaly_rad) % TWO_PI
        phase_rad = unwrapped_phase(raw_phase_rad, previous_raw_phase_rad, previous_phase_rad)
        current_orbit_number = floor(phase_rad / TWO_PI)
        if orbit_number is not None and current_orbit_number != orbit_number:
            accepted_row = accepted_orbit_row(current_samples)
            if accepted_row is not None:
                yield accepted_row
            current_samples = []
        current_samples.append(PhaseSample(chunk_id, time_us, semi_major_axis_m, phase_rad))
        previous_row = row
        previous_raw_phase_rad = raw_phase_rad
        previous_phase_rad = phase_rad
        orbit_number = current_orbit_number
    accepted_row = accepted_orbit_row(current_samples)
    if accepted_row is not None:
        yield accepted_row


def phase_source_bounds(output_start_time_us, output_stop_time_us):
    """Input: optional [start, stop) phase-orbit output scope
    Output: source [start, stop) including two prior hours for orbit completion"""
    if (output_start_time_us is None) != (output_stop_time_us is None):
        raise ValueError("Phase-orbit scope needs both start and stop times.")
    if output_start_time_us is None:
        return None, None
    if output_stop_time_us <= output_start_time_us:
        raise ValueError("Phase-orbit stop time must be after its start time.")
    return output_start_time_us - PHASE_SCOPE_PADDING_US, output_stop_time_us


def write_phase_orbit_means(
    database_path=DEFAULT_DATABASE, output_start_time_us=None, output_stop_time_us=None,
):
    """Input: SQLite path and optional phase-orbit output [start, stop) scope
    Output: {input_rows, stored_rows} for P1.5.4"""
    source_start_time_us, source_stop_time_us = phase_source_bounds(
        output_start_time_us, output_stop_time_us,
    )
    connection = connect_database(Path(database_path))
    try:
        with connection:
            create_phase_orbit_tables(connection)
            rows = list(phase_orbit_rows(trailing_mean_element_rows(
                connection, source_start_time_us, source_stop_time_us,
            )))
            if output_start_time_us is not None:
                rows = [
                    row for row in rows
                    if output_start_time_us <= row[0] < output_stop_time_us
                ]
                connection.execute(f"""
                    DELETE FROM {PHASE_ORBIT_TABLE}
                    WHERE time_us >= ? AND time_us < ?
                """, (output_start_time_us, output_stop_time_us))
            else:
                connection.execute(f"DELETE FROM {PHASE_ORBIT_TABLE}")
            connection.executemany(
                f"INSERT INTO {PHASE_ORBIT_TABLE} VALUES ({', '.join('?' for _ in range(14))})", rows
            )
            write_metadata(connection)
    finally:
        connection.close()
    return {"input_rows": None, "stored_rows": len(rows)}


def write_harmonic_diagnostics(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5.4 phase-orbit rows
    Output: {stored_rows} for P1.5.5"""
    connection = connect_database(Path(database_path))
    try:
        with connection:
            amplitudes_by_chunk = {}
            for row in connection.execute(f"SELECT chunk_id, h2_amplitude_m, h3_amplitude_m FROM {PHASE_ORBIT_TABLE}"):
                amplitudes_by_chunk.setdefault(row[0], []).append((row[1], row[2]))
            summaries = [
                (chunk_id, len(amplitudes), median(value[0] for value in amplitudes), max(value[0] for value in amplitudes),
                 median(value[1] for value in amplitudes), max(value[1] for value in amplitudes), ALGORITHM_VERSION)
                for chunk_id, amplitudes in amplitudes_by_chunk.items()
            ]
            connection.execute(f"DELETE FROM {HARMONIC_DIAGNOSTIC_TABLE}")
            connection.executemany(f"INSERT INTO {HARMONIC_DIAGNOSTIC_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?)", summaries)
    finally:
        connection.close()
    return {"diagnostic_rows": len(summaries)}


def utc_day_start_us(time_us):
    """Input: UTC time in microseconds
    Output: UTC day start in microseconds"""
    return time_us // MICROSECONDS_PER_DAY * MICROSECONDS_PER_DAY


def phase_orbit_source_rows(connection):
    """Input: SQLite connection with P1.5.4 rows
    Output: ordered rows {orbit end, mean a, chunk_id, orbit start}"""
    return connection.execute(f"""
        SELECT time_us, phase_weighted_mean_semi_major_axis_m, chunk_id,
               orbit_start_time_us
        FROM {PHASE_ORBIT_TABLE} ORDER BY chunk_id, time_us
    """).fetchall()


def daily_decay_rows(rows):
    """Input: P1.5.4 source rows
    Output: chunk-local fixed-day OLS rows"""
    groups = {}
    for time_us, semi_major_axis_m, chunk_id, _ in rows:
        groups.setdefault((chunk_id, utc_day_start_us(time_us)), []).append((time_us, semi_major_axis_m))
    for (chunk_id, day_start_us), points in groups.items():
        if len(points) >= MINIMUM_ORBITS_PER_DAILY_FIT:
            fit = ordinary_least_squares(points)
            yield (points[-1][0], day_start_us, fit["rate_m_day"], fit["rate_1sigma_m_day"], fit["residual_std_m"], len(points), chunk_id, ALGORITHM_VERSION)


def local_decay_rows(rows, window_hours):
    """Input: P1.5.4 source rows and centered window hours
    Output: chunk-local centered OLS rows"""
    half_window_us = window_hours * MICROSECONDS_PER_DAY // 48
    minimum_span_us = int(2 * half_window_us * MINIMUM_LOCAL_WINDOW_COVERAGE)
    rows_by_chunk = {}
    for row in rows:
        rows_by_chunk.setdefault(row[2], []).append(row)
    for chunk_id, chunk_rows in rows_by_chunk.items():
        for time_us, _, _, _ in chunk_rows:
            points = [
                row for row in chunk_rows
                if abs(row[0] - time_us) <= half_window_us
            ]
            covered_span_us = points[-1][0] - points[0][3] if points else 0
            if len(points) >= MINIMUM_ORBITS_PER_LOCAL_FIT and covered_span_us >= minimum_span_us:
                fit = ordinary_least_squares([(point[0], point[1]) for point in points])
                yield (time_us, window_hours, fit["rate_m_day"], fit["rate_1sigma_m_day"], fit["residual_std_m"], len(points), points[0][3], points[-1][0], chunk_id, ALGORITHM_VERSION)


def trailing_residual_fit(samples):
    """Input: one-hour H2/H3-subtracted MeanElementSample window
    Output: local linear decay fit"""
    return ordinary_least_squares([
        (sample.time_us, sample.semi_major_axis_m)
        for sample in samples
    ])


def phase_coverage_rad(samples):
    """Input: one ordered MeanElementSample window
    Output: total unwrapped phase coverage in rad"""
    previous_raw_phase_rad = None
    previous_phase_rad = None
    first_phase_rad = None
    for sample in samples:
        phase_rad = unwrapped_phase(
            sample.phase_rad, previous_raw_phase_rad, previous_phase_rad,
        )
        if first_phase_rad is None:
            first_phase_rad = phase_rad
        previous_raw_phase_rad = sample.phase_rad
        previous_phase_rad = phase_rad
    return previous_phase_rad - first_phase_rad


def trailing_decay_rows(rows, first_output_time_us=None):
    """Input: ordered H2/H3-subtracted samples
    Output: trailing one-hour decay rows at or after an optional output start"""
    window_samples = deque()
    previous_source_sample = None
    previous_fit_sample = None
    next_output_time_us = None
    for source_sample in rows:
        source_gap_s = (
            previous_source_sample is not None
            and (source_sample.time_us - previous_source_sample.time_us)
            / MICROSECONDS_PER_SECOND > MAXIMUM_POD_GAP_S
        )
        new_chunk = (
            previous_source_sample is not None
            and source_sample.chunk_id != previous_source_sample.chunk_id
        )
        if source_gap_s or new_chunk:
            window_samples.clear()
            next_output_time_us = None
            previous_fit_sample = None
        previous_source_sample = source_sample
        if (
            previous_fit_sample is not None
            and source_sample.time_us - previous_fit_sample.time_us
            < TRAILING_FIT_SAMPLE_INTERVAL_US
        ):
            continue
        sample = source_sample
        previous_fit_sample = sample
        window_samples.append(sample)
        while (
            sample.time_us - window_samples[0].time_us > TRAILING_WINDOW_US
        ):
            window_samples.popleft()
        if next_output_time_us is None:
            next_output_time_us = sample.time_us + TRAILING_WINDOW_US
        if sample.time_us < next_output_time_us:
            continue
        covered_span_us = sample.time_us - window_samples[0].time_us
        maximum_gap_s = max(
            (later.time_us - earlier.time_us) / MICROSECONDS_PER_SECOND
            for earlier, later in zip(window_samples, list(window_samples)[1:])
        )
        if (
            len(window_samples) >= MINIMUM_TRAILING_SAMPLES
            and covered_span_us >= int(TRAILING_WINDOW_US * MINIMUM_TRAILING_COVERAGE)
            and maximum_gap_s <= MAXIMUM_POD_GAP_S
        ):
            fit = trailing_residual_fit(list(window_samples))
            if (
                first_output_time_us is None
                or sample.time_us >= first_output_time_us
            ):
                yield (
                    sample.time_us, window_samples[0].time_us,
                    fit["rate_m_day"], fit["rate_1sigma_m_day"],
                    fit["residual_std_m"], len(window_samples),
                    phase_coverage_rad(window_samples), maximum_gap_s,
                    sample.chunk_id, TRAILING_ALGORITHM_VERSION,
                )
        next_output_time_us = sample.time_us + TRAILING_OUTPUT_INTERVAL_US


def trailing_mean_element_rows(connection, start_time_us, stop_time_us):
    """Input: SQLite connection and optional [start, stop) source scope
    Output: ordered usable rows for a trailing H2/H3 fit"""
    query = f"""
        SELECT quality.chunk_id, mean.time_us, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN swarm_a_pod_quality AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1 AND quality.chunk_id IS NOT NULL
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
    """
    parameters = []
    if start_time_us is not None:
        query += " AND mean.time_us >= ?"
        parameters.append(start_time_us)
    if stop_time_us is not None:
        query += " AND mean.time_us < ?"
        parameters.append(stop_time_us)
    return connection.execute(
        query + " ORDER BY quality.chunk_id, mean.time_us", parameters,
    )


def harmonic_residual_rows(connection, start_time_us, stop_time_us):
    """Input: SQLite connection and source [start, stop) scope
    Output: ordered mean-element rows with their containing-orbit H2/H3 removed"""
    query = f"""
        SELECT orbit_start_time_us, time_us, chunk_id,
               h2_cosine_m, h2_sine_m, h3_cosine_m, h3_sine_m
        FROM {PHASE_ORBIT_TABLE}
    """
    parameters = []
    if start_time_us is not None:
        query += " WHERE time_us >= ?"
        parameters.append(start_time_us)
    if stop_time_us is not None:
        query += " AND" if parameters else " WHERE"
        query += " orbit_start_time_us < ?"
        parameters.append(stop_time_us)
    orbit_rows = connection.execute(
        query + " ORDER BY time_us", parameters,
    ).fetchall()
    orbit_index = 0
    for chunk_id, time_us, semi_major_axis_m, omega_rad, mean_anomaly_rad in (
        trailing_mean_element_rows(connection, start_time_us, stop_time_us)
    ):
        while (
            orbit_index < len(orbit_rows)
            and time_us > orbit_rows[orbit_index][1]
        ):
            orbit_index += 1
        if orbit_index == len(orbit_rows):
            return
        start_us, _, orbit_chunk_id, h2_cosine_m, h2_sine_m, h3_cosine_m, h3_sine_m = orbit_rows[orbit_index]
        if time_us < start_us or chunk_id != orbit_chunk_id:
            continue
        phase_rad = (omega_rad + mean_anomaly_rad) % TWO_PI
        harmonic_deviation_m = (
            h2_cosine_m * cos(2.0 * phase_rad)
            + h2_sine_m * sin(2.0 * phase_rad)
            + h3_cosine_m * cos(3.0 * phase_rad)
            + h3_sine_m * sin(3.0 * phase_rad)
        )
        yield MeanElementSample(
            chunk_id, time_us, semi_major_axis_m - harmonic_deviation_m,
            phase_rad,
        )


def trailing_source_bounds(output_start_time_us, output_stop_time_us):
    """Input: optional [start, stop) trailing output scope
    Output: source [start, stop) including the required prior hour"""
    if (output_start_time_us is None) != (output_stop_time_us is None):
        raise ValueError("Trailing decay scope needs both start and stop times.")
    if output_start_time_us is None:
        return None, None
    if output_stop_time_us <= output_start_time_us:
        raise ValueError("Trailing decay stop time must be after its start time.")
    return output_start_time_us - TRAILING_WINDOW_US, output_stop_time_us


def write_trailing_decay_candidates(
    database_path=DEFAULT_DATABASE, output_start_time_us=None, output_stop_time_us=None,
):
    """Input: SQLite path and optional trailing-output [start, stop) scope
    Output: {stored_rows} for P1.5.6 trailing one-hour decay"""
    source_start_time_us, source_stop_time_us = trailing_source_bounds(
        output_start_time_us, output_stop_time_us,
    )
    connection = connect_database(Path(database_path))
    try:
        with connection:
            create_phase_orbit_tables(connection)
            rows = list(trailing_decay_rows(
                harmonic_residual_rows(
                    connection, source_start_time_us, source_stop_time_us,
                ),
                output_start_time_us,
            ))
            if output_start_time_us is None:
                connection.execute(f"DELETE FROM {TRAILING_DECAY_TABLE}")
            else:
                connection.execute(f"""
                    DELETE FROM {TRAILING_DECAY_TABLE}
                    WHERE time_us >= ? AND time_us < ?
                """, (output_start_time_us, output_stop_time_us))
            connection.executemany(
                f"INSERT INTO {TRAILING_DECAY_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    finally:
        connection.close()
    return {"trailing_decay_rows": len(rows)}


def write_decay_candidates(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5.4 phase-orbit rows
    Output: {daily_rows, local_rows} for P1.5.6"""
    connection = connect_database(Path(database_path))
    try:
        with connection:
            source_rows = phase_orbit_source_rows(connection)
            daily_rows = list(daily_decay_rows(source_rows))
            local_rows = [row for window_hours in LOCAL_WINDOW_HOURS for row in local_decay_rows(source_rows, window_hours)]
            connection.execute(f"DELETE FROM {DAILY_DECAY_TABLE}")
            connection.execute(f"DELETE FROM {LOCAL_DECAY_TABLE}")
            connection.executemany(f"INSERT INTO {DAILY_DECAY_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?)", daily_rows)
            connection.executemany(f"INSERT INTO {LOCAL_DECAY_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", local_rows)
    finally:
        connection.close()
    return {"daily_rows": len(daily_rows), "local_rows": len(local_rows)}


def write_metadata(connection):
    """Input: SQLite connection
    Output: P1.5.4--P1.5.6 method contract is stored"""
    connection.executemany("INSERT OR REPLACE INTO metadata VALUES (?, ?)", [
        ("phase_orbit_algorithm", ALGORITHM_VERSION),
        ("phase_orbit_phase", "u = mean_argument_of_perigee + mean_anomaly"),
        ("phase_orbit_chunk_policy", "reset phase and fits at every chunk_id boundary"),
        ("phase_orbit_mean_policy", "trapezoidal delta_u weighted mean"),
        ("phase_orbit_harmonics", "H2 and H3 phase Fourier coefficients per orbit"),
        ("phase_orbit_trailing_decay", "1h trailing local OLS with H2/H3"),
    ])


def write_phase_orbit_products(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5.1 and P1.4 inputs
    Output: P1.5.4--P1.5.6 write counts"""
    mean_result = write_phase_orbit_means(database_path)
    diagnostic_result = write_harmonic_diagnostics(database_path)
    decay_result = write_trailing_decay_candidates(database_path)
    return {**mean_result, **diagnostic_result, **decay_result}


def main():
    """Input: python -m phases.phase1.code.prep_10_phase_orbit_mean [DATABASE]
    Output: P1.5.4--P1.5.6 write summary"""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise ValueError("Usage: [DATABASE]")
    database_path = Path(arguments[0]) if arguments else DEFAULT_DATABASE
    result = write_phase_orbit_products(database_path)
    print(f"Mean-element input rows: {result['input_rows']}")
    print(f"Phase-orbit rows: {result['stored_rows']}")
    print(f"Harmonic diagnostic rows: {result['diagnostic_rows']}")
    print(f"Trailing 1-hour decay rows: {result['trailing_decay_rows']}")


if __name__ == "__main__":
    main()
