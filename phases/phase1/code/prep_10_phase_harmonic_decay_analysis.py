"""Write causal P1.6 features beside the four local-decay candidates."""

import sqlite3
import sys
from pathlib import Path

from phases.phase1.code.calc_feature_alignment import (
    align_space_weather,
    align_sym_h,
    feature_quality_flags,
)
from phases.phase0.code.data.database.prep_raw_schema import connect_database
from phases.phase1.code.prep_14_phase_harmonic_decay_candidates import (
    DECAY_CANDIDATE_TABLE,
)
from phases.phase1.code.prep_08_analysis_10min import (
    next_sym_h_observation,
    sym_h_rows,
    weather_by_time,
)


DEFAULT_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
)
ANALYSIS_TABLE = "swarm_a_phase_harmonic_decay_analysis_v1"
ALGORITHM_VERSION = "causal_features_phase_harmonic_decay_v1"
ANALYSIS_COLUMN_NAMES = (
    "time_us",
    "decay_method",
    "orbit_window",
    "decay_rate_m_day",
    "decay_rate_1sigma_m_day",
    "fit_residual_std_m",
    "sample_count",
    "window_start_time_us",
    "chunk_id",
    "harmonic_orders",
    "sym_h_nt",
    "sym_h_left_time_us",
    "sym_h_right_time_us",
    "ap_now",
    "ap_source_time_us",
    "f107_sfu",
    "f107_source_time_us",
    "f107a_sfu",
    "f107a_source_time_us",
    "f107_data_type",
    "quality_flags",
    "algorithm_version",
)


def create_phase_harmonic_analysis_table(connection):
    """Input: SQLite connection.
    Output: versioned P1.6 candidate-analysis table exists."""
    existing_columns = tuple(
        row[1] for row in connection.execute(f"PRAGMA table_info({ANALYSIS_TABLE})")
    )
    if existing_columns and existing_columns != ANALYSIS_COLUMN_NAMES:
        raise ValueError(f"{ANALYSIS_TABLE} schema differs; create a new table version.")
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ANALYSIS_TABLE} (
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
            sym_h_nt REAL,
            sym_h_left_time_us INTEGER,
            sym_h_right_time_us INTEGER,
            ap_now REAL,
            ap_source_time_us INTEGER,
            f107_sfu REAL,
            f107_source_time_us INTEGER,
            f107a_sfu REAL,
            f107a_source_time_us INTEGER,
            f107_data_type TEXT,
            quality_flags TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (time_us, decay_method, orbit_window),
            FOREIGN KEY (time_us, decay_method, orbit_window)
                REFERENCES {DECAY_CANDIDATE_TABLE} (time_us, decay_method, orbit_window)
        )
    """)


def candidate_rows(connection):
    """Input: SQLite connection with P1.5.6 candidate rows.
    Output: ordered candidate rows for causal feature alignment."""
    return connection.execute(f"""
        SELECT time_us, decay_method, orbit_window, decay_rate_m_day,
               decay_rate_1sigma_m_day, fit_residual_std_m, sample_count,
               window_start_time_us, chunk_id, harmonic_orders
        FROM {DECAY_CANDIDATE_TABLE}
        ORDER BY time_us, decay_method, orbit_window
    """)


def analysis_rows(candidates, observations, weather):
    """Input: ordered candidates, SYM-H observations, and causal weather map.
    Output: candidate-analysis rows retaining feature source times."""
    left_observation = None
    right_observation = next_sym_h_observation(observations)
    for candidate in candidates:
        target_time_us = candidate["time_us"]
        while (
            right_observation is not None
            and right_observation["time_us"] < target_time_us
        ):
            left_observation = right_observation
            right_observation = next_sym_h_observation(observations)
        sym_h_features = align_sym_h(
            target_time_us, left_observation, right_observation,
        )
        weather_features = align_space_weather(target_time_us, weather)
        yield (
            *candidate,
            sym_h_features["sym_h_nt"],
            sym_h_features["sym_h_left_time_us"],
            sym_h_features["sym_h_right_time_us"],
            weather_features["ap_now"],
            weather_features["ap_source_time_us"],
            weather_features["f107_sfu"],
            weather_features["f107_source_time_us"],
            weather_features["f107a_sfu"],
            weather_features["f107a_source_time_us"],
            weather_features["f107_data_type"],
            feature_quality_flags(sym_h_features, weather_features),
            ALGORITHM_VERSION,
        )


def write_phase_harmonic_analysis_metadata(connection):
    """Input: SQLite connection.
    Output: P1.6 candidate-analysis contract is stored in metadata."""
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("phase_harmonic_decay_analysis_algorithm", ALGORITHM_VERSION),
            (
                "phase_harmonic_decay_analysis_feature_contract",
                "weather source <= candidate time; SYM-H right endpoint <= candidate time + 120 s",
            ),
        ],
    )


def write_phase_harmonic_decay_analysis(database_path=DEFAULT_DATABASE):
    """Input: three-year SQLite path with P1.5.6 candidates and raw features.
    Output: {input_rows, stored_rows} for P1.6 causal candidate analysis."""
    connection = connect_database(Path(database_path))
    try:
        connection.row_factory = sqlite3.Row
        with connection:
            create_phase_harmonic_analysis_table(connection)
            input_rows = connection.execute(
                f"SELECT count(*) FROM {DECAY_CANDIDATE_TABLE}"
            ).fetchone()[0]
            weather = weather_by_time(connection)
            connection.execute(f"DELETE FROM {ANALYSIS_TABLE}")
            connection.executemany(
                f"INSERT INTO {ANALYSIS_TABLE} VALUES ({', '.join('?' for _ in ANALYSIS_COLUMN_NAMES)})",
                analysis_rows(candidate_rows(connection), sym_h_rows(connection), weather),
            )
            write_phase_harmonic_analysis_metadata(connection)
    finally:
        connection.close()
    return {"input_rows": input_rows, "stored_rows": input_rows}


def main():
    """Input: python -m ...prep_10_phase_harmonic_decay_analysis [DATABASE].
    Output: P1.6 three-year candidate-analysis row count."""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise ValueError("Usage: [DATABASE]")
    database_path = Path(arguments[0]) if arguments else DEFAULT_DATABASE
    result = write_phase_harmonic_decay_analysis(database_path)
    print(f"P1.6 candidate input rows: {result['input_rows']}")
    print(f"P1.6 candidate analysis rows: {result['stored_rows']}")


if __name__ == "__main__":
    main()
