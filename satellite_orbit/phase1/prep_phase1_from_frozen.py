"""Build P1.6 output from a frozen P1.5 source without new raw data."""

import sys
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import connect_database, create_tables
from satellite_orbit.data.pod.prep_03_orbital_elements import (
    create_orbital_element_table,
)
from satellite_orbit.data.pod.prep_05_pod_quality import create_quality_table
from satellite_orbit.data.pod.prep_mean_orbit_cache import (
    copy_verified_mean_orbit_cache,
)
from satellite_orbit.data.pod.prep_06_orbit_10min import write_orbit_10min
from satellite_orbit.data.pod.prep_07_decay_rate import write_decay_rates
from satellite_orbit.phase1.prep_08_analysis_10min import write_analysis_10min


FROZEN_TABLES = (
    "space_weather",
    "geomagnetic",
    "source_files",
    "swarm_a_pod_source_provenance",
    "swarm_a_states",
    "swarm_a_orbital_elements",
    "swarm_a_pod_quality",
)
FROZEN_METADATA_NAMES = (
    "weather_preparation_version",
    "weather_signature",
    "orbital_element_algorithm",
    "orbital_element_mu_m3_s2",
    "astropy_iers_data_version",
    "p1_4_quality_policy_version",
    "p1_4_official_orbit_events",
)


def require_new_target(database_path):
    """Input: target SQLite path
    Output: target path is absent and its parent exists"""
    if database_path.exists():
        raise ValueError(f"Frozen-copy target already exists: {database_path}")
    if not database_path.parent.is_dir():
        raise ValueError(f"Frozen-copy target parent does not exist: {database_path.parent}")


def create_p1_5_base(database_path, frozen_database_path):
    """Input: absent target SQLite path and frozen source SQLite path
    Output: {database_path, table_rows, mean_orbit_rows} through P1.5"""
    database_path = Path(database_path)
    frozen_database_path = Path(frozen_database_path)
    require_new_target(database_path)
    if not frozen_database_path.is_file():
        raise ValueError(f"Frozen source does not exist: {frozen_database_path}")

    table_rows = {}
    connection = connect_database(database_path)
    try:
        create_tables(connection)
        create_orbital_element_table(connection)
        create_quality_table(connection)
        connection.execute("ATTACH DATABASE ? AS frozen", (str(frozen_database_path),))
        try:
            for table_name in FROZEN_TABLES:
                connection.execute(
                    f"INSERT INTO {table_name} SELECT * FROM frozen.{table_name}"
                )
                table_rows[table_name] = connection.execute(
                    f"SELECT count(*) FROM {table_name}"
                ).fetchone()[0]
            placeholders = ", ".join("?" for _ in FROZEN_METADATA_NAMES)
            connection.execute(
                "INSERT INTO metadata "
                "SELECT name, value FROM frozen.metadata "
                f"WHERE name IN ({placeholders})",
                FROZEN_METADATA_NAMES,
            )
            connection.commit()
        finally:
            connection.execute("DETACH DATABASE frozen")
    finally:
        connection.close()

    mean_orbit_rows = copy_verified_mean_orbit_cache(
        database_path,
        frozen_database_path,
    )["stored_rows"]
    return {
        "database_path": database_path,
        "table_rows": table_rows,
        "mean_orbit_rows": mean_orbit_rows,
    }


def write_p1_6_outputs(database_path):
    """Input: SQLite path through P1.5
    Output: {orbit_10min, decay_rates, analysis} from fixed frozen input"""
    return {
        "orbit_10min": write_orbit_10min(database_path),
        "decay_rates": write_decay_rates(database_path),
        "analysis": write_analysis_10min(database_path),
    }


def build_p1_6_from_frozen(database_path, frozen_database_path):
    """Input: absent target SQLite path and frozen source SQLite path
    Output: P1.5 copied base and newly calculated P1.6 output"""
    p1_5_base = create_p1_5_base(database_path, frozen_database_path)
    return {
        "p1_5_base": p1_5_base,
        "p1_6_outputs": write_p1_6_outputs(database_path),
    }


def main():
    """Input: TARGET_DATABASE FROZEN_DATABASE
    Output: P1.5 copy and P1.6 calculation summary"""
    arguments = sys.argv[1:]
    if len(arguments) != 2:
        raise ValueError("Usage: TARGET_DATABASE FROZEN_DATABASE")
    result = build_p1_6_from_frozen(arguments[0], arguments[1])
    print(f"P1.5 mean-orbit rows: {result['p1_5_base']['mean_orbit_rows']}")
    print(
        "P1.6 analysis rows: "
        f"{result['p1_6_outputs']['analysis']['stored_rows']}"
    )


if __name__ == "__main__":
    main()
