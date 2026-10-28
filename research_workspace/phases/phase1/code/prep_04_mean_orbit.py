"""Calculate Brouwer-Lyddane mean semi-major axes from valid Swarm-A POD."""

import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from research_workspace.phases.phase0.code.calculation.pod.calc_coordinates import itrf_states_to_gcrf
from research_workspace.phases.phase1.code.calc_mean_orbit import (
    MEAN_ORBIT_CONVERGENCE_EPSILON,
    MEAN_ORBIT_MAX_ITERATIONS,
    add_project_orekit_site_packages,
    calculate_mean_orbital_elements,
    calculate_mean_semi_major_axis,
    initialize_mean_orbit_context,
)
from research_workspace.phases.phase0.code.data.database.prep_raw_schema import connect_database

DEFAULT_DATABASE = Path(
    "research_workspace/phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite"
)
ALGORITHM_NAME = "orekit_brouwer_lyddane_j2_to_j5_m2_0_v3"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
IMPLEMENTATION_PATHS = (
    Path(__file__),
    PROJECT_ROOT / "research_workspace/phases/phase0/code/calculation/pod/calc_coordinates.py",
    PROJECT_ROOT / "research_workspace/phases/phase1/code/calc_mean_orbit.py",
)
MEAN_ORBIT_ELEMENT_FIELDS = (
    "mean_semi_major_axis_m",
    "mean_eccentricity",
    "mean_inclination_rad",
    "mean_longitude_rad",
    "mean_eccentric_longitude_rad",
    "mean_true_longitude_rad",
    "mean_equinoctial_ex",
    "mean_equinoctial_ey",
    "mean_equinoctial_hx",
    "mean_equinoctial_hy",
    "mean_keplerian_period_s",
    "mean_keplerian_mean_motion_rad_s",
    "mean_argument_of_perigee_rad",
    "mean_raan_rad",
    "mean_anomaly_rad",
    "mean_eccentric_anomaly_rad",
    "mean_true_anomaly_rad",
    "mean_x_m",
    "mean_y_m",
    "mean_z_m",
    "mean_vx_m_s",
    "mean_vy_m_s",
    "mean_vz_m_s",
)
MEAN_ORBIT_ELEMENTS_TABLE = "swarm_a_mean_orbit_elements_v1"
MEAN_ORBIT_ELEMENT_SCOPE_METADATA_NAMES = (
    "mean_orbit_elements_start_time_us",
    "mean_orbit_elements_stop_time_us",
)
FULL_MEAN_ORBIT_START_TIME_US = int(
    datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1_000_000
)
FULL_MEAN_ORBIT_STOP_TIME_US = int(
    datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1_000_000
)
THREE_YEAR_MEAN_ORBIT_START_TIME_US = int(
    datetime(2023, 7, 1, tzinfo=timezone.utc).timestamp() * 1_000_000
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


def create_mean_orbit_elements_table(connection):
    """Input: SQLite connection
    Output: versioned full mean-orbit table exists"""
    element_columns = ",\n            ".join(
        f"{field_name} REAL" for field_name in MEAN_ORBIT_ELEMENT_FIELDS
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MEAN_ORBIT_ELEMENTS_TABLE} (
            time_us INTEGER PRIMARY KEY,
            {element_columns},
            rejection_reason TEXT,
            FOREIGN KEY (time_us) REFERENCES swarm_a_states(time_us)
        )
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


def mean_orbit_element_source_states(
    connection,
    source_id,
    time_scope,
):
    """Input: SQLite connection and POD source id
    Output: valid P1.3 states in [start_time_us, stop_time_us)"""
    start_time_us, stop_time_us = time_scope
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
              AND state.time_us >= ?
              AND state.time_us < ?
              AND element.semi_major_axis_m IS NOT NULL
              AND element.rejection_reason IS NULL
            ORDER BY state.time_us
            """,
            (source_id, start_time_us, stop_time_us),
        )
    ]


def missing_mean_orbit_element_source_states(connection, source_id, time_scope):
    """Input: SQLite connection, POD source id, and requested time scope.
    Output: valid P1.3 states without a versioned mean-element row."""
    start_time_us, stop_time_us = time_scope
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
            f"""
            SELECT state.time_us, state.x_m, state.y_m, state.z_m,
                   state.vx_m_s, state.vy_m_s, state.vz_m_s
            FROM swarm_a_states AS state
            JOIN swarm_a_orbital_elements AS element
                ON element.time_us = state.time_us
            LEFT JOIN {MEAN_ORBIT_ELEMENTS_TABLE} AS mean
                ON mean.time_us = state.time_us
            WHERE state.source_id = ?
              AND state.time_us >= ?
              AND state.time_us < ?
              AND element.semi_major_axis_m IS NOT NULL
              AND element.rejection_reason IS NULL
              AND mean.time_us IS NULL
            ORDER BY state.time_us
            """,
            (source_id, start_time_us, stop_time_us),
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


def mean_orbit_element_row(time_us, state_gcrf):
    """Input: raw time_us and one GCRF state
    Output: (time_us, mean elements, rejection_reason)"""
    try:
        elements = calculate_mean_orbital_elements(state_gcrf)
    except ValueError as error:
        return (time_us, *([None] * len(MEAN_ORBIT_ELEMENT_FIELDS)), str(error))
    return (
        time_us,
        *(elements[field_name] for field_name in MEAN_ORBIT_ELEMENT_FIELDS),
        None,
    )


def mean_orbit_rows(source_rows):
    """Input: [(time_us, ITRF state), ...]
    Output: [(time_us, mean_semi_major_axis_m, rejection_reason), ...]"""
    states_gcrf = itrf_states_to_gcrf([state for _, state in source_rows])
    return [
        mean_orbit_row(time_us, state)
        for (time_us, _), state in zip(source_rows, states_gcrf)
    ]


def mean_orbit_element_rows(source_rows):
    """Input: [(time_us, ITRF state), ...]
    Output: [(time_us, mean elements, rejection_reason), ...]"""
    states_gcrf = itrf_states_to_gcrf([state for _, state in source_rows])
    return [
        mean_orbit_element_row(time_us, state)
        for (time_us, _), state in zip(source_rows, states_gcrf)
    ]


def calculate_source_rows(source_id, source_rows):
    """Input: POD source id and [(time_us, ITRF state), ...]
    Output: (source_id, [(time_us, mean_semi_major_axis_m, rejection_reason), ...])"""
    return source_id, mean_orbit_rows(source_rows)


def calculate_source_element_rows(source_id, source_rows):
    """Input: POD source id and [(time_us, ITRF state), ...]
    Output: (source_id, [(time_us, mean elements, rejection_reason), ...])"""
    return source_id, mean_orbit_element_rows(source_rows)


def write_source_rows(connection, source_id, rows):
    """Input: SQLite connection, POD source id, and calculated mean-orbit rows
    Output: (written rows, rejected rows)"""
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


def write_source_element_rows(connection, source_id, rows):
    """Input: SQLite connection, POD source id, and full mean-orbit rows
    Output: (written rows, rejected rows)"""
    placeholders = ", ".join("?" for _ in range(len(MEAN_ORBIT_ELEMENT_FIELDS) + 2))
    connection.executemany(
        f"INSERT INTO {MEAN_ORBIT_ELEMENTS_TABLE} VALUES ({placeholders})",
        rows,
    )
    rejection_index = len(MEAN_ORBIT_ELEMENT_FIELDS) + 1
    return len(rows), sum(row[rejection_index] is not None for row in rows)


def write_source(connection, source_id):
    """Input: SQLite connection and POD source id
    Output: (written rows, rejected rows)"""
    source_rows = mean_orbit_source_states(connection, source_id)
    return write_source_rows(connection, source_id, mean_orbit_rows(source_rows))


def write_source_elements(connection, source_id, time_scope):
    """Input: SQLite connection and POD source id
    Output: (written rows, rejected rows)"""
    source_rows = missing_mean_orbit_element_source_states(
        connection, source_id, time_scope
    )
    return write_source_element_rows(
        connection,
        source_id,
        mean_orbit_element_rows(source_rows),
    )


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


def source_elements_are_written(connection, source_id, time_scope):
    """Input: SQLite connection and POD source id
    Output: whether every usable source state has a full mean-orbit row"""
    start_time_us, stop_time_us = time_scope
    missing_row = connection.execute(
        f"""
        SELECT EXISTS(
            SELECT state.time_us
            FROM swarm_a_states AS state
            JOIN swarm_a_orbital_elements AS element
                ON element.time_us = state.time_us
            LEFT JOIN {MEAN_ORBIT_ELEMENTS_TABLE} AS mean
                ON mean.time_us = state.time_us
            WHERE state.source_id = ?
              AND state.time_us >= ?
              AND state.time_us < ?
              AND element.semi_major_axis_m IS NOT NULL
              AND element.rejection_reason IS NULL
              AND mean.time_us IS NULL
        )
        """,
        (source_id, start_time_us, stop_time_us),
    ).fetchone()[0]
    return not missing_row


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
        ("mean_orbit_convergence_epsilon", str(MEAN_ORBIT_CONVERGENCE_EPSILON)),
        ("mean_orbit_max_iterations", str(MEAN_ORBIT_MAX_ITERATIONS)),
        ("orekit_jpype_version", version("orekit-jpype")),
        ("astropy_version", version("astropy")),
        ("mean_orbit_implementation_fingerprint", implementation_fingerprint()),
    ]


def mean_orbit_elements_metadata(start_time_us, stop_time_us):
    """Input: installed calculation dependencies
    Output: [(metadata name, value), ...] for the full mean-orbit table"""
    return [
        (f"mean_orbit_elements_{name.removeprefix('mean_orbit_')}", value)
        for name, value in mean_orbit_metadata()
    ] + [
        ("mean_orbit_elements_table", MEAN_ORBIT_ELEMENTS_TABLE),
        ("mean_orbit_elements_fields", ",".join(MEAN_ORBIT_ELEMENT_FIELDS)),
        ("mean_orbit_elements_start_time_us", str(start_time_us)),
        ("mean_orbit_elements_stop_time_us", str(stop_time_us)),
    ]


def require_matching_resume_metadata(
    connection,
    expected_metadata,
    table_name="swarm_a_mean_orbital_elements",
):
    """Input: SQLite connection and current implementation metadata
    Output: resume safety confirmed, or explicit rebuild error"""
    existing_rows = connection.execute(
        f"SELECT count(*) FROM {table_name}"
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


def require_extendable_element_scope(connection, expected_metadata, time_scope):
    """Input: SQLite connection, expected v1 metadata, and requested time scope.
    Output: existing v1 rows are compatible and lie inside the requested scope."""
    existing_rows = connection.execute(
        f"SELECT count(*) FROM {MEAN_ORBIT_ELEMENTS_TABLE}"
    ).fetchone()[0]
    if existing_rows == 0:
        return
    metadata_names = [
        name
        for name, _ in expected_metadata
        if name not in MEAN_ORBIT_ELEMENT_SCOPE_METADATA_NAMES
    ]
    placeholders = ", ".join("?" for _ in metadata_names)
    stored_metadata = dict(
        connection.execute(
            f"SELECT name, value FROM metadata WHERE name IN ({placeholders})",
            metadata_names,
        )
    )
    expected_values = dict(expected_metadata)
    mismatched_names = [
        name for name in metadata_names if stored_metadata.get(name) != expected_values[name]
    ]
    if mismatched_names:
        raise ValueError(
            "Mean-orbit element metadata differs: " + ", ".join(mismatched_names)
        )
    first_time_us, last_time_us = connection.execute(
        f"SELECT min(time_us), max(time_us) FROM {MEAN_ORBIT_ELEMENTS_TABLE}"
    ).fetchone()
    start_time_us, stop_time_us = time_scope
    if start_time_us > first_time_us or stop_time_us <= last_time_us:
        raise ValueError(
            "Requested mean-orbit element scope must contain existing rows. "
            "Create a new P1.5 database for a narrower scope."
        )


def write_metadata(connection, metadata):
    """Input: SQLite connection and current mean-orbit metadata
    Output: mean-orbit settings are stored"""
    connection.executemany("INSERT OR REPLACE INTO metadata VALUES (?, ?)", metadata)


def submit_source_calculation(
    executor,
    connection,
    source_id,
    source_calculator,
    source_reader=mean_orbit_source_states,
):
    """Input: thread executor, SQLite reader connection, and POD source id
    Output: future yielding one source id and its calculated rows"""
    source_rows = source_reader(connection, source_id)
    return executor.submit(source_calculator, source_id, source_rows)


def write_sources_parallel(
    connection,
    source_ids,
    workers,
    source_calculator=calculate_source_rows,
    source_row_writer=write_source_rows,
    source_reader=mean_orbit_source_states,
):
    """Input: writer connection, source ids, and worker count
    Output: (new_source_files, stored_rows, rejected_rows)"""
    new_source_files = 0
    stored_rows = 0
    rejected_rows = 0
    source_id_iterator = iter(source_ids)
    initialize_mean_orbit_context()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for _ in range(min(workers, len(source_ids))):
            source_id = next(source_id_iterator)
            future = submit_source_calculation(
                executor,
                connection,
                source_id,
                source_calculator,
                source_reader,
            )
            futures[future] = source_id

        while futures:
            future = next(as_completed(futures))
            futures.pop(future)
            source_id, rows = future.result()
            source_rows, source_rejections = source_row_writer(
                connection,
                source_id,
                rows,
            )
            connection.commit()
            new_source_files += 1
            stored_rows += source_rows
            rejected_rows += source_rejections
            print(f"POD source files: {new_source_files}/{len(source_ids)}", flush=True)
            try:
                next_source_id = next(source_id_iterator)
            except StopIteration:
                continue
            next_future = submit_source_calculation(
                executor,
                connection,
                next_source_id,
                source_calculator,
                source_reader,
            )
            futures[next_future] = next_source_id
    return new_source_files, stored_rows, rejected_rows


def write_mean_orbits(
    database_path=DEFAULT_DATABASE,
    rebuild=False,
    source_limit=None,
    workers=1,
):
    """Input: SQLite path and optional rebuild, limit, and worker count
    Output: {source_files, new_source_files, stored_rows, rejected_rows}"""
    database_path = Path(database_path)
    if workers <= 0:
        raise ValueError("Worker count must be positive.")
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

        if workers == 1:
            for source_id in pending_source_ids:
                source_rows, source_rejections = write_source(connection, source_id)
                new_source_files += 1
                stored_rows += source_rows
                rejected_rows += source_rejections
                connection.commit()
                print(
                    f"POD source files: {new_source_files}/{len(pending_source_ids)}",
                    flush=True,
                )
        else:
            new_source_files, stored_rows, rejected_rows = write_sources_parallel(
                connection,
                pending_source_ids,
                workers,
            )

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


def write_mean_orbit_elements(
    database_path=DEFAULT_DATABASE,
    rebuild=False,
    source_limit=None,
    workers=1,
    start_time_us=FULL_MEAN_ORBIT_START_TIME_US,
    stop_time_us=FULL_MEAN_ORBIT_STOP_TIME_US,
):
    """Input: SQLite path and optional rebuild, limit, and worker count
    Output: {source_files, new_source_files, stored_rows, rejected_rows}"""
    database_path = Path(database_path)
    if start_time_us >= stop_time_us:
        raise ValueError("Mean-orbit element time window must be increasing.")
    if rebuild:
        raise ValueError(
            "The versioned full mean-orbit table is append/resume only; "
            "create a new database to start a different result."
        )
    if workers <= 0:
        raise ValueError("Worker count must be positive.")
    stored_rows = 0
    rejected_rows = 0
    new_source_files = 0

    expected_metadata = mean_orbit_elements_metadata(start_time_us, stop_time_us)
    time_scope = (start_time_us, stop_time_us)
    connection = connect_database(database_path)
    try:
        create_mean_orbit_elements_table(connection)
        source_ids = [
            row[0]
            for row in connection.execute(
                """
                SELECT DISTINCT state.source_id
                FROM swarm_a_states AS state
                JOIN swarm_a_orbital_elements AS element
                    ON element.time_us = state.time_us
                WHERE state.time_us >= ?
                  AND state.time_us < ?
                  AND element.semi_major_axis_m IS NOT NULL
                  AND element.rejection_reason IS NULL
                ORDER BY state.source_id
                """,
                (start_time_us, stop_time_us),
            )
        ]
        require_extendable_element_scope(connection, expected_metadata, time_scope)
        write_metadata(connection, expected_metadata)
        connection.commit()

        pending_source_ids = [
            source_id
            for source_id in source_ids
            if not source_elements_are_written(connection, source_id, time_scope)
        ]
        if source_limit is not None:
            pending_source_ids = pending_source_ids[:source_limit]

        if workers == 1:
            for source_id in pending_source_ids:
                source_rows, source_rejections = write_source_elements(
                    connection, source_id, time_scope
                )
                new_source_files += 1
                stored_rows += source_rows
                rejected_rows += source_rejections
                connection.commit()
                print(
                    f"POD source files: {new_source_files}/{len(pending_source_ids)}",
                    flush=True,
                )
        else:
            new_source_files, stored_rows, rejected_rows = write_sources_parallel(
                connection,
                pending_source_ids,
                workers,
                calculate_source_element_rows,
                write_source_element_rows,
                lambda connection, source_id: mean_orbit_element_source_states(
                    connection, source_id, time_scope
                ),
            )

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
    """Input: python -m research_workspace.phases.phase1.code.prep_04_mean_orbit [elements] [SOURCE_LIMIT]
    Output: mean-orbit write summary"""
    arguments = sys.argv[1:]
    write_elements = arguments[:1] == ["elements"]
    if write_elements:
        arguments = arguments[1:]
    if len(arguments) > 1:
        raise ValueError("Usage: [elements] [SOURCE_LIMIT]")
    source_limit = int(arguments[0]) if arguments else None
    if source_limit is not None and source_limit <= 0:
        raise ValueError("Source limit must be positive.")
    writer = write_mean_orbit_elements if write_elements else write_mean_orbits
    result = writer(source_limit=source_limit)
    print(f"POD source files: {result['source_files']}")
    print(f"Mean-orbit rows written: {result['stored_rows']}")
    print(f"Rows rejected: {result['rejected_rows']}")


if __name__ == "__main__":
    main()
