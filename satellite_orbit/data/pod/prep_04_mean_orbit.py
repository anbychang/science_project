"""Calculate Brouwer-Lyddane mean semi-major axes from valid Swarm-A POD."""

import hashlib
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from satellite_orbit.calculation.pod.calc_coordinates import itrf_states_to_gcrf
from satellite_orbit.calculation.pod.calc_mean_orbit import (
    add_project_orekit_site_packages,
    calculate_mean_semi_major_axis,
)
from satellite_orbit.data.database.prep_raw_schema import connect_database

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
ALGORITHM_NAME = "orekit_brouwer_lyddane_j2_to_j5_m2_0_v2"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMPLEMENTATION_PATHS = (
    Path(__file__),
    PROJECT_ROOT / "satellite_orbit/calculation/pod/calc_coordinates.py",
    PROJECT_ROOT / "satellite_orbit/calculation/pod/calc_mean_orbit.py",
)


def create_mean_orbit_table(connection):
    """Input: SQLite connection
    Output: mean-orbit table exists"""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_a_mean_orbital_elements (
            time_us INTEGER PRIMARY KEY,
            mean_semi_major_axis_m REAL,
            rejection_reason TEXT,
            FOREIGN KEY (time_us) REFERENCES swarm_a_states(time_us)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS swarm_a_states_source_time
        ON swarm_a_states (source_id, time_us)
        """
    )


def mean_orbit_source_states(connection, source_id):
    """Input: SQLite connection and POD source id
    Output: [(time_us, ITRF state), ...] for valid P1.3 rows"""
    return [
        (
            row[0],
            {
                "time": datetime.fromtimestamp(row[0] / 1_000_000, timezone.utc),
                "frame": "ITRF",
                "position_m": row[1:4],
                "velocity_m_s": row[4:7],
            },
        )
        for row in connection.execute(
            """
            SELECT state.time_us, state.x_m, state.y_m, state.z_m,
                   state.vx_m_s, state.vy_m_s, state.vz_m_s
            FROM swarm_a_states AS state
            JOIN swarm_a_orbital_elements AS element
                ON element.time_us = state.time_us
            WHERE state.source_id = ?
              AND element.semi_major_axis_m IS NOT NULL
              AND element.rejection_reason IS NULL
            ORDER BY state.time_us
            """,
            (source_id,),
        )
    ]


def mean_orbit_row(time_us, state_gcrf):
    """Input: raw time_us and one GCRF state
    Output: (time_us, mean_semi_major_axis_m, rejection_reason)"""
    try:
        mean_semi_major_axis_m = calculate_mean_semi_major_axis(state_gcrf)
    except ValueError as error:
        return time_us, None, str(error)
    return time_us, float(mean_semi_major_axis_m), None


def write_source(connection, source_id):
    """Input: SQLite connection and POD source id
    Output: (written rows, rejected rows)"""
    source_rows = mean_orbit_source_states(connection, source_id)
    states_gcrf = itrf_states_to_gcrf([state for _, state in source_rows])
    rows = [
        mean_orbit_row(time_us, state)
        for (time_us, _), state in zip(source_rows, states_gcrf)
    ]
    connection.execute(
        """
        DELETE FROM swarm_a_mean_orbital_elements
        WHERE time_us IN (
            SELECT time_us
            FROM swarm_a_states
            WHERE source_id = ?
        )
        """,
        (source_id,),
    )
    connection.executemany(
        "INSERT INTO swarm_a_mean_orbital_elements VALUES (?, ?, ?)",
        rows,
    )
    return len(rows), sum(row[2] is not None for row in rows)


def source_is_written(connection, source_id):
    """Input: SQLite connection and POD source id
    Output: whether every usable source state has a mean-orbit row"""
    valid_rows = connection.execute(
        """
        SELECT count(*)
        FROM swarm_a_states AS state
        JOIN swarm_a_orbital_elements AS element
            ON element.time_us = state.time_us
        WHERE state.source_id = ?
          AND element.semi_major_axis_m IS NOT NULL
          AND element.rejection_reason IS NULL
        """,
        (source_id,),
    ).fetchone()[0]
    stored_rows = connection.execute(
        """
        SELECT count(*)
        FROM swarm_a_mean_orbital_elements AS mean
        JOIN swarm_a_states AS state
            ON state.time_us = mean.time_us
        WHERE state.source_id = ?
        """,
        (source_id,),
    ).fetchone()[0]
    return stored_rows == valid_rows


def implementation_fingerprint():
    """Input: current mean-orbit implementation files
    Output: deterministic SHA-256 fingerprint"""
    digest = hashlib.sha256()
    for implementation_path in IMPLEMENTATION_PATHS:
        digest.update(implementation_path.name.encode())
        digest.update(implementation_path.read_bytes())
    return digest.hexdigest()


def mean_orbit_metadata():
    """Input: installed calculation dependencies
    Output: [(metadata name, value), ...] for one implementation"""
    add_project_orekit_site_packages()
    return [
        ("mean_orbit_algorithm", ALGORITHM_NAME),
        (
            "mean_orbit_input_policy",
            "all valid P1.3 rows; P1.4 event exclusions apply downstream",
        ),
        ("mean_orbit_input_frame", "GCRF"),
        ("mean_orbit_input_transform", "astropy_itrf_to_gcrf"),
        ("mean_orbit_gravity_field_degree_order", "5,0"),
        ("mean_orbit_m2", "0.0"),
        ("orekit_jpype_version", version("orekit-jpype")),
        ("astropy_version", version("astropy")),
        ("mean_orbit_implementation_fingerprint", implementation_fingerprint()),
    ]


def require_matching_resume_metadata(connection, expected_metadata):
    """Input: SQLite connection and current implementation metadata
    Output: resume safety confirmed, or explicit rebuild error"""
    existing_rows = connection.execute(
        "SELECT count(*) FROM swarm_a_mean_orbital_elements"
    ).fetchone()[0]
    if existing_rows == 0:
        return

    metadata_names = [name for name, _ in expected_metadata]
    placeholders = ", ".join("?" for _ in metadata_names)
    stored_metadata = dict(
        connection.execute(
            f"SELECT name, value FROM metadata WHERE name IN ({placeholders})",
            metadata_names,
        )
    )
    mismatched_names = [
        name
        for name, value in expected_metadata
        if stored_metadata.get(name) != value
    ]
    if mismatched_names:
        names = ", ".join(mismatched_names)
        raise ValueError(
            f"Mean-orbit resume metadata differs: {names}. Use rebuild=True."
        )


def write_metadata(connection, metadata):
    """Input: SQLite connection and current mean-orbit metadata
    Output: mean-orbit settings are stored"""
    connection.executemany("INSERT OR REPLACE INTO metadata VALUES (?, ?)", metadata)


def write_mean_orbits(
    database_path=DEFAULT_DATABASE,
    rebuild=False,
    source_limit=None,
):
    """Input: SQLite path and optional rebuild/limit
    Output: {source_files, new_source_files, stored_rows, rejected_rows}"""
    database_path = Path(database_path)
    stored_rows = 0
    rejected_rows = 0
    new_source_files = 0

    expected_metadata = mean_orbit_metadata()
    connection = connect_database(database_path)
    try:
        create_mean_orbit_table(connection)
        source_ids = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT source_id FROM swarm_a_states ORDER BY source_id"
            )
        ]
        if rebuild:
            connection.execute("DELETE FROM swarm_a_mean_orbital_elements")
        else:
            require_matching_resume_metadata(connection, expected_metadata)

        pending_source_ids = [
            source_id for source_id in source_ids if not source_is_written(connection, source_id)
        ]
        if source_limit is not None:
            pending_source_ids = pending_source_ids[:source_limit]

        for source_id in pending_source_ids:
            source_rows, source_rejections = write_source(connection, source_id)
            new_source_files += 1
            stored_rows += source_rows
            rejected_rows += source_rejections
            connection.commit()
            print(f"POD source files: {new_source_files}/{len(pending_source_ids)}", flush=True)

        write_metadata(connection, expected_metadata)
        connection.commit()
    finally:
        connection.close()

    return {
        "source_files": len(source_ids),
        "new_source_files": new_source_files,
        "stored_rows": stored_rows,
        "rejected_rows": rejected_rows,
    }


def main():
    """Input: python -m satellite_orbit.data.pod.prep_04_mean_orbit [SOURCE_LIMIT]
    Output: mean-orbit write summary"""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise ValueError("Usage: [SOURCE_LIMIT]")
    source_limit = int(arguments[0]) if arguments else None
    if source_limit is not None and source_limit <= 0:
        raise ValueError("Source limit must be positive.")
    result = write_mean_orbits(source_limit=source_limit)
    print(f"POD source files: {result['source_files']}")
    print(f"Mean-orbit rows written: {result['stored_rows']}")
    print(f"Rows rejected: {result['rejected_rows']}")


if __name__ == "__main__":
    main()
