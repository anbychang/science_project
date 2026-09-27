"""Calculate and store Swarm-A instantaneous semi-major axes."""

import sqlite3
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from satellite_orbit.calculation.calc_coordinates import itrf_states_to_gcrf
from satellite_orbit.calculation.calc_forces import MU_M3_S2
from satellite_orbit.calculation.calc_orbital_response import calculate_semi_major_axis
from satellite_orbit.data.load_sqlite_states import load_sqlite_states
from satellite_orbit.data.prep_sqlite_common import time_to_us

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
ALGORITHM_NAME = "two_body_specific_energy_gcrf_v1"


def us_to_time(time_us):
    """Input: Unix time in microseconds
    Output: UTC datetime"""
    return datetime.fromtimestamp(time_us / 1_000_000, tz=timezone.utc)


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


def source_days(connection):
    """Input: SQLite connection
    Output: [(first_time_us, last_time_us, state_count), ...]"""
    return connection.execute(
        """
        SELECT MIN(time_us), MAX(time_us), COUNT(*)
        FROM swarm_a_states
        GROUP BY source_id
        ORDER BY source_id
        """
    ).fetchall()


def day_is_written(connection, day):
    """Input: {SQLite connection, POD day range}
    Output: True when all states already have an element row"""
    first_time_us, last_time_us, state_count = day
    element_count = connection.execute(
        """
        SELECT COUNT(*) FROM swarm_a_orbital_elements
        WHERE time_us >= ? AND time_us <= ?
        """,
        (first_time_us, last_time_us),
    ).fetchone()[0]
    return element_count == state_count


def element_row(state):
    """Input: one GCRF state
    Output: (time_us, semi_major_axis_m, rejection_reason)"""
    try:
        semi_major_axis_m = calculate_semi_major_axis(state)
    except ValueError as error:
        # Keep the reason so one bad POD point does not stop all later days.
        return time_to_us(state["time"]), None, str(error)
    return time_to_us(state["time"]), semi_major_axis_m, None


def write_one_day(connection, database_path, day):
    """Input: {SQLite connection, database path, POD day range}
    Output: (written rows, rejected rows)"""
    first_time_us, last_time_us, _ = day
    states_itrf = load_sqlite_states(
        us_to_time(first_time_us),
        us_to_time(last_time_us),
        database_path,
    )
    states_gcrf = itrf_states_to_gcrf(states_itrf)
    rows = []
    for state in states_gcrf:
        rows.append(element_row(state))

    connection.executemany(
        "INSERT OR REPLACE INTO swarm_a_orbital_elements VALUES (?, ?, ?)",
        rows,
    )
    rejected_rows = 0
    for row in rows:
        if row[2] is not None:
            rejected_rows += 1
    return len(rows), rejected_rows


def write_metadata(connection):
    """Input: SQLite connection
    Output: calculation settings are stored"""
    settings = [
        ("orbital_element_algorithm", ALGORITHM_NAME),
        ("orbital_element_mu_m3_s2", str(MU_M3_S2)),
        ("astropy_iers_data_version", version("astropy-iers-data")),
    ]
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        settings,
    )


def write_orbital_elements(database_path=DEFAULT_DATABASE):
    """Input: SQLite database path
    Output: {source_days, new_source_days, stored_rows, rejected_rows}"""
    database_path = Path(database_path)
    stored_rows = 0
    rejected_rows = 0

    with sqlite3.connect(database_path) as connection:
        create_orbital_element_table(connection)
        write_metadata(connection)
        all_days = source_days(connection)
        missing_days = []
        for day in all_days:
            if not day_is_written(connection, day):
                missing_days.append(day)

        for day_number, day in enumerate(missing_days, start=1):
            day_rows, day_rejections = write_one_day(connection, database_path, day)
            stored_rows += day_rows
            rejected_rows += day_rejections
            connection.commit()
            print(f"POD days: {day_number}/{len(missing_days)}", flush=True)

    return {
        "source_days": len(all_days),
        "new_source_days": len(missing_days),
        "stored_rows": stored_rows,
        "rejected_rows": rejected_rows,
    }


def main():
    """Input: python -m satellite_orbit.data.prep_write_orbital_elements
    Output: orbital-element write summary"""
    result = write_orbital_elements()
    print(f"POD source days: {result['source_days']}")
    print(f"Missing POD days written: {result['new_source_days']}")
    print(f"Orbital-element rows written: {result['stored_rows']}")
    print(f"Rows rejected: {result['rejected_rows']}")


if __name__ == "__main__":
    main()
