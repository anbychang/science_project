"""Write causal P1.6 features beside qualified multi-window orbit rates."""

import sqlite3
import sys
from pathlib import Path

from satellite_orbit.calculation.analysis.calc_feature_alignment import (
    align_space_weather,
    align_sym_h,
    feature_quality_flags,
)
from satellite_orbit.data.database.prep_raw_schema import connect_database


DEFAULT_DATABASE = Path("data/swarm_a_analysis.sqlite")
ALGORITHM_VERSION = "causal_space_weather_geomagnetic_backward_3h_6h_12h_v3"
ANALYSIS_COLUMNS = {
    "time_us",
    "semi_major_axis_orbit_mean_m",
    "da_dt_3h_backward_m_s",
    "da_dt_3h_backward_m_day",
    "da_dt_6h_backward_m_s",
    "da_dt_6h_backward_m_day",
    "da_dt_12h_backward_m_s",
    "da_dt_12h_backward_m_day",
    "pod_count",
    "max_pod_gap_s",
    "chunk_id",
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
}


def create_analysis_10min_table(connection):
    """Input: SQLite connection
    Output: P1.6 analysis table exists"""
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(swarm_a_analysis_10min)")
    }
    if existing_columns and existing_columns != ANALYSIS_COLUMNS:
        connection.execute("DROP TABLE swarm_a_analysis_10min")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_a_analysis_10min (
            time_us INTEGER PRIMARY KEY,
            semi_major_axis_orbit_mean_m REAL NOT NULL,
            da_dt_3h_backward_m_s REAL NOT NULL,
            da_dt_3h_backward_m_day REAL NOT NULL,
            da_dt_6h_backward_m_s REAL NOT NULL,
            da_dt_6h_backward_m_day REAL NOT NULL,
            da_dt_12h_backward_m_s REAL NOT NULL,
            da_dt_12h_backward_m_day REAL NOT NULL,
            pod_count INTEGER NOT NULL,
            max_pod_gap_s REAL NOT NULL,
            chunk_id INTEGER NOT NULL,
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
            FOREIGN KEY (time_us) REFERENCES swarm_a_orbit_decay_10min(time_us)
        )
        """
    )


def orbit_rows(connection):
    """Input: SQLite connection with qualified P1.5 output
    Output: [{decay row, orbit-quality fields}, ...] ordered by UTC"""
    return connection.execute(
        """
        SELECT
            decay.time_us,
            decay.semi_major_axis_orbit_mean_m,
            decay.da_dt_3h_backward_m_s,
            decay.da_dt_3h_backward_m_day,
            decay.da_dt_6h_backward_m_s,
            decay.da_dt_6h_backward_m_day,
            decay.da_dt_12h_backward_m_s,
            decay.da_dt_12h_backward_m_day,
            orbit.pod_count,
            orbit.max_pod_gap_s,
            decay.chunk_id
        FROM swarm_a_orbit_decay_10min AS decay
        JOIN swarm_a_orbit_10min AS orbit ON orbit.time_us = decay.time_us
        ORDER BY decay.time_us
        """
    ).fetchall()


def weather_by_time(connection):
    """Input: SQLite connection with raw space_weather
    Output: {time_us: causal weather source row}"""
    rows = connection.execute(
        """
        SELECT time_us, ap_now, f107_sfu, f107a_last81_sfu, f107_data_type
        FROM space_weather
        """
    ).fetchall()
    return {
        row["time_us"]: {
            "ap_now": row["ap_now"],
            "f107_sfu": row["f107_sfu"],
            "f107a_last81_sfu": row["f107a_last81_sfu"],
            "f107_data_type": row["f107_data_type"],
        }
        for row in rows
    }


def sym_h_rows(connection):
    """Input: SQLite connection with raw geomagnetic records
    Output: ordered SYM-H observation iterator"""
    return connection.execute(
        """
        SELECT time_us, sym_h_nt
        FROM geomagnetic
        WHERE sym_h_nt IS NOT NULL
        ORDER BY time_us
        """
    )


def next_sym_h_observation(observations):
    """Input: SYM-H observation iterator
    Output: {time_us, sym_h_nt}, or None at end"""
    row = next(observations, None)
    if row is None:
        return None
    return {"time_us": row["time_us"], "sym_h_nt": row["sym_h_nt"]}


def analysis_rows(orbits, observations, weather):
    """Input: ordered orbit rows, ordered SYM-H, and raw weather map
    Output: P1.6 analysis rows with causal feature provenance"""
    left_observation = None
    right_observation = next_sym_h_observation(observations)
    for orbit in orbits:
        target_time_us = orbit["time_us"]
        while (
            right_observation is not None
            and right_observation["time_us"] < target_time_us
        ):
            left_observation = right_observation
            right_observation = next_sym_h_observation(observations)

        sym_h_features = align_sym_h(
            target_time_us,
            left_observation,
            right_observation,
        )
        weather_features = align_space_weather(target_time_us, weather)
        yield (
            target_time_us,
            orbit["semi_major_axis_orbit_mean_m"],
            orbit["da_dt_3h_backward_m_s"],
            orbit["da_dt_3h_backward_m_day"],
            orbit["da_dt_6h_backward_m_s"],
            orbit["da_dt_6h_backward_m_day"],
            orbit["da_dt_12h_backward_m_s"],
            orbit["da_dt_12h_backward_m_day"],
            orbit["pod_count"],
            orbit["max_pod_gap_s"],
            orbit["chunk_id"],
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


def write_analysis_metadata(connection):
    """Input: SQLite connection
    Output: P1.6 causal feature policy is stored"""
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("analysis_10min_algorithm", ALGORITHM_VERSION),
            (
                "analysis_10min_feature_contract",
                "weather source <= orbit time; SYM-H permits right endpoint only for <=2min interpolation; density excluded",
            ),
        ],
    )


def write_analysis_10min(database_path=DEFAULT_DATABASE):
    """Input: SQLite path with P1.5 signed orbit-rate and raw feature tables
    Output: {input_rows, stored_rows}"""
    database_path = Path(database_path)
    connection = connect_database(database_path)
    try:
        connection.row_factory = sqlite3.Row
        with connection:
            create_analysis_10min_table(connection)
            orbits = orbit_rows(connection)
            weather = weather_by_time(connection)
            connection.execute("DELETE FROM swarm_a_analysis_10min")
            connection.executemany(
                """
                INSERT INTO swarm_a_analysis_10min VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                analysis_rows(orbits, sym_h_rows(connection), weather),
            )
            write_analysis_metadata(connection)
    finally:
        connection.close()

    return {"input_rows": len(orbits), "stored_rows": len(orbits)}


def main():
    """Input: python -m satellite_orbit.phase1.prep_08_analysis_10min
    Output: P1.6 write summary"""
    if sys.argv[1:]:
        raise ValueError("Usage: no arguments")
    result = write_analysis_10min()
    print(f"Semi-major-axis-rate input rows: {result['input_rows']}")
    print(f"Analysis rows written: {result['stored_rows']}")


if __name__ == "__main__":
    main()
