"""Write quiet-period spectra and complete-orbit decay diagnostics."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

from phases.phase1.code.calc_orbit_decay_diagnostics import (
    OrbitMean,
    calculate_periodogram,
    strongest_periodogram_peaks,
    trailing_orbit_fits,
)
from phases.phase0.code.data.database.prep_raw_schema import connect_database


DEFAULT_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
)
MEAN_ORBIT_TABLE = "swarm_a_mean_orbit_elements_v1"
PHASE_ORBIT_TABLE = "swarm_a_phase_orbit_mean_v2"
POD_QUALITY_TABLE = "swarm_a_pod_quality"
PERIODOGRAM_TABLE = "swarm_a_phase_quiet_periodogram_v1"
ORBIT_DECAY_TABLE = "swarm_a_phase_orbit_trailing_decay_v2"
QUIET_NOISE_TABLE = "swarm_a_phase_orbit_quiet_noise_v1"
QUIET_START_UTC = datetime(2023, 12, 25, tzinfo=timezone.utc)
QUIET_STOP_UTC = datetime(2024, 1, 1, tzinfo=timezone.utc)
ORBIT_WINDOWS = (3, 5)
ALGORITHM_VERSION = "quiet_spectrum_complete_orbit_ols_v1"
MICROSECONDS_PER_SECOND = 1_000_000


def create_diagnostic_tables(connection):
    """Input: SQLite connection.
    Output: P1.5 diagnostic derived tables exist."""
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {PERIODOGRAM_TABLE} (
            quiet_start_time_us INTEGER NOT NULL, rank INTEGER NOT NULL,
            frequency_hz REAL NOT NULL, period_s REAL NOT NULL,
            power_m2 REAL NOT NULL, sample_count INTEGER NOT NULL,
            cadence_s REAL NOT NULL, algorithm_version TEXT NOT NULL,
            PRIMARY KEY (quiet_start_time_us, rank)
        )
    """)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ORBIT_DECAY_TABLE} (
            time_us INTEGER NOT NULL, orbit_window INTEGER NOT NULL,
            decay_rate_m_day REAL NOT NULL, decay_rate_1sigma_m_day REAL NOT NULL,
            fit_residual_std_m REAL NOT NULL, orbit_count INTEGER NOT NULL,
            window_start_time_us INTEGER NOT NULL, chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (time_us, orbit_window)
        )
    """)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {QUIET_NOISE_TABLE} (
            quiet_start_time_us INTEGER NOT NULL, orbit_window INTEGER NOT NULL,
            mean_decay_rate_m_day REAL NOT NULL, rate_std_m_day REAL NOT NULL,
            fit_count INTEGER NOT NULL, algorithm_version TEXT NOT NULL,
            PRIMARY KEY (quiet_start_time_us, orbit_window)
        )
    """)


def utc_to_us(utc_time):
    """Input: timezone-aware UTC datetime.
    Output: Unix microseconds."""
    if utc_time.tzinfo is None:
        raise ValueError("UTC time needs timezone information.")
    return int(utc_time.timestamp() * MICROSECONDS_PER_SECOND)


def read_quiet_mean_elements(connection):
    """Input: SQLite connection with mean elements and quality rows.
    Output: uniformly sampled quiet-period [(time_us, mean_a_m), ...]."""
    return connection.execute(f"""
        SELECT mean.time_us, mean.mean_semi_major_axis_m
        FROM {MEAN_ORBIT_TABLE} AS mean
        JOIN {POD_QUALITY_TABLE} AS quality ON quality.time_us = mean.time_us
        WHERE quality.is_usable = 1
          AND mean.rejection_reason IS NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.time_us >= ? AND mean.time_us < ?
        ORDER BY mean.time_us
    """, (utc_to_us(QUIET_START_UTC), utc_to_us(QUIET_STOP_UTC))).fetchall()


def read_complete_orbit_means(connection):
    """Input: SQLite connection with P1.5.4 orbit means.
    Output: ordered complete OrbitMean values."""
    rows = connection.execute(f"""
        SELECT time_us, phase_weighted_mean_semi_major_axis_m,
               orbit_start_time_us, chunk_id
        FROM {PHASE_ORBIT_TABLE}
        ORDER BY chunk_id, time_us
    """).fetchall()
    return [OrbitMean(*row) for row in rows]


def periodogram_rows(quiet_mean_elements):
    """Input: quiet-period mean-element rows.
    Output: ranked SQLite rows for the quiet periodogram table."""
    spectrum = calculate_periodogram(quiet_mean_elements)
    peaks = strongest_periodogram_peaks(spectrum)
    return [
        (
            utc_to_us(QUIET_START_UTC), rank, peak.frequency_hz,
            peak.period_s, peak.power_m2, len(quiet_mean_elements),
            spectrum.cadence_s, ALGORITHM_VERSION,
        )
        for rank, peak in enumerate(peaks, start=1)
    ]


def orbit_decay_rows(orbit_means):
    """Input: ordered complete OrbitMean values.
    Output: trailing 3- and 5-orbit SQLite rows."""
    rows = []
    for orbit_window in ORBIT_WINDOWS:
        for fit in trailing_orbit_fits(orbit_means, orbit_window):
            rows.append((
                fit.time_us, orbit_window, fit.rate_m_day,
                fit.rate_1sigma_m_day, fit.residual_std_m, fit.orbit_count,
                fit.window_start_time_us, fit.chunk_id, ALGORITHM_VERSION,
            ))
    return rows


def quiet_noise_rows(decay_rows):
    """Input: trailing complete-orbit decay SQLite rows.
    Output: mean and sample standard deviation in the quiet window."""
    quiet_start_us = utc_to_us(QUIET_START_UTC)
    quiet_stop_us = utc_to_us(QUIET_STOP_UTC)
    rows = []
    for orbit_window in ORBIT_WINDOWS:
        rates_m_day = [
            row[2] for row in decay_rows
            if row[1] == orbit_window and quiet_start_us <= row[0] < quiet_stop_us
        ]
        if len(rates_m_day) < 2:
            raise ValueError(f"Quiet window has too few {orbit_window}-orbit fits.")
        rows.append((
            quiet_start_us, orbit_window, mean(rates_m_day),
            stdev(rates_m_day), len(rates_m_day), ALGORITHM_VERSION,
        ))
    return rows


def write_orbit_decay_diagnostics(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5.1 and P1.5.4 tables.
    Output: {periodogram_rows, decay_rows, quiet_noise_rows}."""
    connection = connect_database(Path(database_path))
    try:
        with connection:
            create_diagnostic_tables(connection)
            quiet_mean_elements = read_quiet_mean_elements(connection)
            spectrum_rows = periodogram_rows(quiet_mean_elements)
            decay_rows = orbit_decay_rows(read_complete_orbit_means(connection))
            noise_rows = quiet_noise_rows(decay_rows)
            connection.execute(f"DELETE FROM {PERIODOGRAM_TABLE}")
            connection.execute(f"DELETE FROM {ORBIT_DECAY_TABLE}")
            connection.execute(f"DELETE FROM {QUIET_NOISE_TABLE}")
            connection.executemany(
                f"INSERT INTO {PERIODOGRAM_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                spectrum_rows,
            )
            connection.executemany(
                f"INSERT INTO {ORBIT_DECAY_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                decay_rows,
            )
            connection.executemany(
                f"INSERT INTO {QUIET_NOISE_TABLE} VALUES (?, ?, ?, ?, ?, ?)",
                noise_rows,
            )
    finally:
        connection.close()
    return {
        "periodogram_rows": len(spectrum_rows),
        "decay_rows": len(decay_rows),
        "quiet_noise_rows": len(noise_rows),
    }


def main():
    """Input: python -m ...prep_12_orbit_decay_diagnostics [DATABASE].
    Output: P1.5 quiet-spectrum and complete-orbit OLS summary."""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise ValueError("Usage: [DATABASE]")
    database_path = Path(arguments[0]) if arguments else DEFAULT_DATABASE
    result = write_orbit_decay_diagnostics(database_path)
    print(f"Quiet periodogram peaks: {result['periodogram_rows']}")
    print(f"Trailing 3/5-orbit decay rows: {result['decay_rows']}")
    print(f"Quiet noise summaries: {result['quiet_noise_rows']}")


if __name__ == "__main__":
    main()
