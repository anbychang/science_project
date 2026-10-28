"""Reuse a verified immutable mean-orbit cache in a new Phase 1 target."""

from pathlib import Path

from phases.phase0.code.data.database.prep_raw_schema import connect_database
from phases.phase1.code.prep_03_orbital_elements import (
    create_orbital_element_table,
)
from phases.phase1.code.prep_04_mean_orbit import (
    create_mean_orbit_table,
    mean_orbit_metadata,
    write_metadata,
)

STATE_COLUMNS = (
    "time_us",
    "x_m",
    "y_m",
    "z_m",
    "vx_m_s",
    "vy_m_s",
    "vz_m_s",
    "weather_time_us",
    "source_id",
)
SOURCE_FILE_COLUMNS = ("source_id", "file_name", "signature")


def require_matching_table(connection, table_name, columns):
    """Input: target connection, cache table name, and column names
    Output: cache and target rows are exactly equal"""
    column_list = ", ".join(columns)
    target_only = connection.execute(
        f"SELECT EXISTS(SELECT {column_list} FROM {table_name} "
        f"EXCEPT SELECT {column_list} FROM mean_cache.{table_name})"
    ).fetchone()[0]
    cache_only = connection.execute(
        f"SELECT EXISTS(SELECT {column_list} FROM mean_cache.{table_name} "
        f"EXCEPT SELECT {column_list} FROM {table_name})"
    ).fetchone()[0]
    if target_only or cache_only:
        raise ValueError(f"Mean-orbit cache differs in {table_name}.")


def require_matching_metadata(connection, expected_metadata):
    """Input: target connection and current mean-orbit metadata
    Output: cached mean orbit uses the same numerical environment"""
    compatibility_names = (
        "mean_orbit_input_frame",
        "mean_orbit_input_transform",
        "mean_orbit_gravity_field_degree_order",
        "mean_orbit_m2",
        "orekit_jpype_version",
        "astropy_version",
    )
    expected_values = dict(expected_metadata)
    metadata_names = list(compatibility_names)
    placeholders = ", ".join("?" for _ in metadata_names)
    cached_metadata = dict(
        connection.execute(
            f"SELECT name, value FROM mean_cache.metadata WHERE name IN ({placeholders})",
            metadata_names,
        )
    )
    mismatched_names = [
        name
        for name in metadata_names
        if cached_metadata.get(name) != expected_values[name]
    ]
    if mismatched_names:
        raise ValueError(
            "Mean-orbit cache metadata differs: " + ", ".join(mismatched_names)
        )


def require_cached_mean_coverage(connection):
    """Input: target connection with attached cache
    Output: cache has every currently usable mean-orbit row"""
    missing_rows = connection.execute(
        """
        SELECT EXISTS(
            SELECT time_us
            FROM swarm_a_pod_quality
            WHERE is_usable = 1
            EXCEPT
            SELECT time_us FROM mean_cache.swarm_a_mean_orbital_elements
        )
        """
    ).fetchone()[0]
    if missing_rows:
        raise ValueError("Mean-orbit cache does not cover usable P1.4 rows.")


def copy_verified_orbital_element_cache(database_path, cache_database_path):
    """Input: target SQLite path and frozen cache SQLite path
    Output: {stored_rows} after verified P1.3 cache reuse"""
    database_path = Path(database_path)
    cache_database_path = Path(cache_database_path)
    if not cache_database_path.is_file():
        raise ValueError(f"P1.3 cache does not exist: {cache_database_path}")

    connection = connect_database(database_path)
    try:
        create_orbital_element_table(connection)
        connection.execute("ATTACH DATABASE ? AS mean_cache", (str(cache_database_path),))
        try:
            require_matching_table(connection, "source_files", SOURCE_FILE_COLUMNS)
            require_matching_table(connection, "swarm_a_states", STATE_COLUMNS)
            connection.execute("DELETE FROM swarm_a_orbital_elements")
            connection.execute(
                """
                INSERT INTO swarm_a_orbital_elements
                SELECT time_us, semi_major_axis_m, rejection_reason
                FROM mean_cache.swarm_a_orbital_elements
                """
            )
            stored_rows = connection.execute(
                "SELECT count(*) FROM swarm_a_orbital_elements"
            ).fetchone()[0]
            raw_rows = connection.execute("SELECT count(*) FROM swarm_a_states").fetchone()[0]
            if stored_rows != raw_rows:
                raise ValueError("P1.3 cache does not cover every raw state.")
            connection.execute(
                """
                INSERT OR REPLACE INTO metadata
                SELECT name, value FROM mean_cache.metadata
                WHERE name IN (
                    'orbital_element_algorithm',
                    'orbital_element_mu_m3_s2',
                    'astropy_iers_data_version'
                )
                """
            )
            connection.executemany(
                "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
                [
                    ("orbital_element_cache_database", str(cache_database_path)),
                    ("orbital_element_cache_validation", "exact_source_and_state_match"),
                ],
            )
            connection.commit()
        finally:
            connection.execute("DETACH DATABASE mean_cache")
    finally:
        connection.close()
    return {"stored_rows": stored_rows}


def copy_verified_mean_orbit_cache(database_path, cache_database_path):
    """Input: target SQLite path and frozen cache SQLite path
    Output: {stored_rows} after verified mean-orbit cache reuse"""
    database_path = Path(database_path)
    cache_database_path = Path(cache_database_path)
    if not cache_database_path.is_file():
        raise ValueError(f"Mean-orbit cache does not exist: {cache_database_path}")

    expected_metadata = mean_orbit_metadata()
    connection = connect_database(database_path)
    try:
        create_mean_orbit_table(connection)
        connection.execute("ATTACH DATABASE ? AS mean_cache", (str(cache_database_path),))
        try:
            require_matching_metadata(connection, expected_metadata)
            require_matching_table(connection, "source_files", SOURCE_FILE_COLUMNS)
            require_matching_table(connection, "swarm_a_states", STATE_COLUMNS)
            require_cached_mean_coverage(connection)
            connection.execute("DELETE FROM swarm_a_mean_orbital_elements")
            connection.execute(
                """
                INSERT INTO swarm_a_mean_orbital_elements
                SELECT cache.time_us, cache.mean_semi_major_axis_m,
                       cache.rejection_reason
                FROM mean_cache.swarm_a_mean_orbital_elements AS cache
                JOIN swarm_a_pod_quality AS quality
                    ON quality.time_us = cache.time_us
                WHERE quality.is_usable = 1
                """
            )
            stored_rows = connection.execute(
                "SELECT count(*) FROM swarm_a_mean_orbital_elements"
            ).fetchone()[0]
            cached_metadata = dict(
                connection.execute("SELECT name, value FROM mean_cache.metadata")
            )
            reused_metadata = dict(expected_metadata)
            reused_metadata["mean_orbit_algorithm"] = cached_metadata[
                "mean_orbit_algorithm"
            ]
            reused_metadata["mean_orbit_input_policy"] = (
                "verified cache rows for current usable P1.4 states"
            )
            reused_metadata["mean_orbit_implementation_fingerprint"] = (
                cached_metadata["mean_orbit_implementation_fingerprint"]
            )
            write_metadata(connection, list(reused_metadata.items()))
            connection.executemany(
                "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
                [
                    ("mean_orbit_cache_database", str(cache_database_path)),
                    ("mean_orbit_cache_validation", "exact_source_and_state_match"),
                ],
            )
            connection.commit()
        finally:
            connection.execute("DETACH DATABASE mean_cache")
    finally:
        connection.close()
    return {"stored_rows": stored_rows}
