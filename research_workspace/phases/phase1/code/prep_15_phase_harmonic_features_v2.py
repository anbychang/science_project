"""Write one causal P1.6 feature row for every P1.5.6 v2 epoch."""

import sqlite3
import sys
from itertools import islice
from pathlib import Path

from research_workspace.phases.phase1.code.calc_feature_alignment import (
    align_space_weather,
    align_sym_h,
    feature_quality_flags,
)
from research_workspace.phases.phase0.code.data.database.prep_raw_schema import connect_database
from research_workspace.phases.phase1.code.prep_14_phase_harmonic_decay_candidates import (
    RAW_B_L_SET_TABLE,
)
from research_workspace.phases.phase1.code.prep_08_analysis_10min import (
    next_sym_h_observation,
    sym_h_rows,
    weather_by_time,
)


DEFAULT_DATABASE = Path("research_workspace/phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite")
FEATURE_TABLE = "swarm_a_phase_harmonic_features_v2"
ALGORITHM_VERSION = "causal_features_phase_harmonic_v2"
BATCH_SIZE = 100_000
FEATURE_COLUMNS = (
    "time_us", "sym_h_nt", "sym_h_left_time_us", "sym_h_right_time_us", "ap_now",
    "ap_source_time_us", "f107_sfu", "f107_source_time_us", "f107a_sfu",
    "f107a_source_time_us", "f107_data_type", "quality_flags", "algorithm_version",
)


def create_feature_table(connection):
    """Input: SQLite connection. Output: versioned P1.6 feature table exists."""
    existing = tuple(row[1] for row in connection.execute(f"PRAGMA table_info({FEATURE_TABLE})"))
    if existing and existing != FEATURE_COLUMNS:
        raise ValueError(f"{FEATURE_TABLE} schema differs; create a new table version.")
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {FEATURE_TABLE} (
            time_us INTEGER PRIMARY KEY,
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
            FOREIGN KEY (time_us) REFERENCES {RAW_B_L_SET_TABLE}(time_us)
        )
    """)


def feature_rows(times, observations, weather):
    """Input: ordered epoch rows, SYM-H observations, weather map. Output: feature rows."""
    left_observation = None
    right_observation = next_sym_h_observation(observations)
    for time_row in times:
        time_us = time_row["time_us"]
        while right_observation is not None and right_observation["time_us"] < time_us:
            left_observation = right_observation
            right_observation = next_sym_h_observation(observations)
        sym_h = align_sym_h(time_us, left_observation, right_observation)
        weather_features = align_space_weather(time_us, weather)
        yield (
            time_us, sym_h["sym_h_nt"], sym_h["sym_h_left_time_us"],
            sym_h["sym_h_right_time_us"], weather_features["ap_now"],
            weather_features["ap_source_time_us"], weather_features["f107_sfu"],
            weather_features["f107_source_time_us"], weather_features["f107a_sfu"],
            weather_features["f107a_source_time_us"], weather_features["f107_data_type"],
            feature_quality_flags(sym_h, weather_features), ALGORITHM_VERSION,
        )


def write_batches(connection, rows):
    """Input: SQLite connection and feature-row iterator. Output: stored row count."""
    insert_sql = f"INSERT INTO {FEATURE_TABLE} VALUES ({', '.join('?' for _ in FEATURE_COLUMNS)})"
    stored_rows = 0
    while batch := list(islice(rows, BATCH_SIZE)):
        connection.executemany(insert_sql, batch)
        connection.commit()
        stored_rows += len(batch)
    return stored_rows


def write_phase_harmonic_features(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5.6 v2 tables and raw features. Output: row counts."""
    connection = connect_database(Path(database_path))
    try:
        connection.row_factory = sqlite3.Row
        create_feature_table(connection)
        input_rows = connection.execute(f"SELECT count(*) FROM {RAW_B_L_SET_TABLE}").fetchone()[0]
        connection.execute(f"DELETE FROM {FEATURE_TABLE}")
        rows = feature_rows(
            connection.execute(f"SELECT time_us FROM {RAW_B_L_SET_TABLE} ORDER BY time_us"),
            sym_h_rows(connection), weather_by_time(connection),
        )
        stored_rows = write_batches(connection, rows)
        connection.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", (
            "p1_6_phase_harmonic_v2_algorithm", ALGORITHM_VERSION,
        ))
        connection.commit()
    finally:
        connection.close()
    return {"input_rows": input_rows, "stored_rows": stored_rows}


def main():
    """Input: python -m ...prep_15_phase_harmonic_features_v2 [DATABASE]. Output: row count."""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise ValueError("Usage: [DATABASE]")
    result = write_phase_harmonic_features(Path(arguments[0]) if arguments else DEFAULT_DATABASE)
    print(f"P1.6 v2 feature rows: {result['stored_rows']}")


if __name__ == "__main__":
    main()
