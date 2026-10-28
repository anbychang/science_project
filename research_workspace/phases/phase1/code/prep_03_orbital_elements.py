"""Calculate and store Swarm-A instantaneous semi-major axes."""

from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from research_workspace.phases.phase0.code.calculation.pod.calc_coordinates import itrf_states_to_gcrf
from research_workspace.phases.phase1.code.calc_orbital_response import (
    MU_M3_S2,
    calculate_semi_major_axis,
)
from research_workspace.phases.phase0.code.data.database.prep_raw_schema import connect_database

DEFAULT_DATABASE = Path("research_workspace/phases/phase1/data/sqlite/swarm_a_data.sqlite")
ALGORITHM_NAME = "two_body_specific_energy_gcrf_v1"


def create_orbital_element_table(connection):
    """Input: SQLite connection
    Output: orbital-element table exists"""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_a_orbital_elements (
            time_us INTEGER PRIMARY KEY,
            semi_major_axis_m REAL,
            rejection_reason TEXT,
            FOREIGN KEY (time_us) REFERENCES swarm_a_states(time_us)
        )
        """
    )


def source_states(connection, source_id):
    """Input: SQLite connection and raw POD source id
    Output: [(time_us, ITRF state), ...]"""
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
            SELECT time_us, x_m, y_m, z_m, vx_m_s, vy_m_s, vz_m_s
            FROM swarm_a_states
            WHERE source_id = ?
            ORDER BY time_us
            """,
            (source_id,),
        )
    ]


def element_row(time_us, state):
    """Input: raw time_us and one GCRF state
    Output: (time_us, semi_major_axis_m, rejection_reason)"""
    try:
        semi_major_axis_m = calculate_semi_major_axis(state)
    except ValueError as error:
        # Keep the reason so one bad POD point does not stop all later days.
        return time_us, None, str(error)
    return time_us, semi_major_axis_m, None


def write_source(connection, source_id):
    """Input: SQLite connection and raw POD source id
    Output: (written rows, rejected rows)"""
    source_rows = source_states(connection, source_id)
    states_gcrf = itrf_states_to_gcrf([state for _, state in source_rows])
    rows = [
        element_row(time_us, state)
        for (time_us, _), state in zip(source_rows, states_gcrf)
    ]

    connection.executemany(
        "INSERT INTO swarm_a_orbital_elements VALUES (?, ?, ?)",
        rows,
    )
    return len(rows), sum(row[2] is not None for row in rows)


def write_metadata(connection):
    """Input: SQLite connection
    Output: calculation settings are stored"""
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("orbital_element_algorithm", ALGORITHM_NAME),
            ("orbital_element_mu_m3_s2", str(MU_M3_S2)),
            ("astropy_iers_data_version", version("astropy-iers-data")),
        ],
    )


def write_orbital_elements(database_path=DEFAULT_DATABASE):
    """Input: SQLite database path
    Output: {source_files, new_source_files, stored_rows, rejected_rows}"""
    database_path = Path(database_path)
    stored_rows = 0
    rejected_rows = 0

    with connect_database(database_path) as connection:
        create_orbital_element_table(connection)
        source_ids = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT source_id FROM swarm_a_states ORDER BY source_id"
            )
        ]
        connection.execute("DELETE FROM swarm_a_orbital_elements")

        for source_number, source_id in enumerate(source_ids, start=1):
            source_rows, source_rejections = write_source(
                connection,
                source_id,
            )
            stored_rows += source_rows
            rejected_rows += source_rejections
            connection.commit()
            print(
                f"POD source files: {source_number}/{len(source_ids)}",
                flush=True,
            )

        write_metadata(connection)

    return {
        "source_files": len(source_ids),
        "new_source_files": len(source_ids),
        "stored_rows": stored_rows,
        "rejected_rows": rejected_rows,
    }


def main():
    """Input: python -m research_workspace.phases.phase1.code.prep_03_orbital_elements
    Output: orbital-element write summary"""
    result = write_orbital_elements()
    print(f"POD source files: {result['source_files']}")
    print(f"POD source files rebuilt: {result['new_source_files']}")
    print(f"Orbital-element rows written: {result['stored_rows']}")
    print(f"Rows rejected: {result['rejected_rows']}")


if __name__ == "__main__":
    main()
