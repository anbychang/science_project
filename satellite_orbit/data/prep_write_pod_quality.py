"""Mark basic POD quality without changing raw observations."""

import sqlite3
from math import isfinite
from pathlib import Path

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
BATCH_SIZE = 10_000


def create_quality_table(connection):
    """Input: SQLite connection
    Output: POD quality table exists"""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_a_pod_quality (
            time_us INTEGER PRIMARY KEY,
            is_usable INTEGER NOT NULL,
            rejection_reason TEXT,
            interval_id INTEGER,
            FOREIGN KEY (time_us) REFERENCES swarm_a_states(time_us)
        )
        """
    )


def clear_quality_table(connection):
    """Input: SQLite connection
    Output: old POD quality rows removed"""
    connection.execute("DELETE FROM swarm_a_pod_quality")


def quality_row(row, previous_time_us):
    """Input: one POD row and the previous time
    Output: (time_us, is_usable, rejection_reason, interval_id)"""
    time_us = row["time_us"]
    state_values = [
        row["x_m"],
        row["y_m"],
        row["z_m"],
        row["vx_m_s"],
        row["vy_m_s"],
        row["vz_m_s"],
    ]

    if previous_time_us is not None and time_us <= previous_time_us:
        return time_us, 0, "time_not_increasing", None
    if not all(value is not None and isfinite(value) for value in state_values):
        return time_us, 0, "non_finite_state", None
    if row["orbital_rejection_reason"] is not None:
        return time_us, 0, "invalid_orbital_energy", None
    if row["semi_major_axis_m"] is None:
        return time_us, 0, "missing_orbital_element", None
    if not isfinite(row["semi_major_axis_m"]) or row["semi_major_axis_m"] <= 0.0:
        return time_us, 0, "invalid_orbital_element", None
    return time_us, 1, None, None


def quality_source_rows(connection):
    """Input: SQLite connection
    Output: POD rows with their orbital-element result"""
    return connection.execute(
        """
        SELECT
            state.time_us,
            state.x_m,
            state.y_m,
            state.z_m,
            state.vx_m_s,
            state.vy_m_s,
            state.vz_m_s,
            state.source_id,
            element.semi_major_axis_m,
            element.rejection_reason AS orbital_rejection_reason
        FROM swarm_a_states AS state
        LEFT JOIN swarm_a_orbital_elements AS element
            ON element.time_us = state.time_us
        ORDER BY state.time_us
        """
    )


def measure_native_cadence_us(connection):
    """Input: SQLite connection
    Output: most common within-source time difference in microseconds"""
    time_rows = connection.execute(
        "SELECT time_us, source_id FROM swarm_a_states ORDER BY time_us"
    )
    difference_counts = {}
    previous_time_us = None
    previous_source_id = None

    for time_us, source_id in time_rows:
        if source_id == previous_source_id and time_us > previous_time_us:
            difference_us = time_us - previous_time_us
            difference_counts[difference_us] = difference_counts.get(difference_us, 0) + 1
        previous_time_us = time_us
        previous_source_id = source_id

    cadence_us = None
    largest_count = 0
    for difference_us, count in difference_counts.items():
        if count > largest_count:
            cadence_us = difference_us
            largest_count = count
    return cadence_us


def starts_new_interval(
    row,
    previous_time_us,
    previous_source_id,
    previous_is_usable,
    cadence_us,
):
    """Input: current and previous POD quality context
    Output: True when a new continuous interval starts"""
    if previous_time_us is None:
        return True
    if row["source_id"] != previous_source_id:
        return True
    if not previous_is_usable:
        return True
    return row["time_us"] - previous_time_us > cadence_us


def write_pod_quality(database_path=DEFAULT_DATABASE):
    """Input: SQLite database path
    Output: {raw_rows, usable_rows, interval_count, rejection_counts}"""
    database_path = Path(database_path)
    raw_rows = 0
    usable_rows = 0
    rejection_counts = {}

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        create_quality_table(connection)
        clear_quality_table(connection)
        cadence_us = measure_native_cadence_us(connection)
        if cadence_us is None:
            raise ValueError("Cannot measure POD cadence from the raw states.")
        source_rows = quality_source_rows(connection)
        previous_time_us = None
        previous_source_id = None
        previous_is_usable = False
        interval_id = 0

        try:
            while True:
                batch = source_rows.fetchmany(BATCH_SIZE)
                if not batch:
                    break

                quality_rows = []
                for row in batch:
                    result = quality_row(row, previous_time_us)
                    if result[1] == 1:
                        if starts_new_interval(
                            row,
                            previous_time_us,
                            previous_source_id,
                            previous_is_usable,
                            cadence_us,
                        ):
                            interval_id += 1
                        result = result[:3] + (interval_id,)
                    quality_rows.append(result)
                    previous_time_us = row["time_us"]
                    previous_source_id = row["source_id"]
                    previous_is_usable = result[1] == 1
                    raw_rows += 1
                    if result[1] == 1:
                        usable_rows += 1
                    else:
                        reason = result[2]
                        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

                connection.executemany(
                    "INSERT OR REPLACE INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
                    quality_rows,
                )
                connection.commit()
        finally:
            source_rows.close()

    return {
        "raw_rows": raw_rows,
        "usable_rows": usable_rows,
        "interval_count": interval_id,
        "native_cadence_s": cadence_us / 1_000_000,
        "rejection_counts": rejection_counts,
    }


def main():
    """Input: python -m satellite_orbit.data.prep_write_pod_quality
    Output: POD quality summary"""
    result = write_pod_quality()
    print(f"POD rows checked: {result['raw_rows']}")
    print(f"Usable POD rows: {result['usable_rows']}")
    print(f"Native cadence (s): {result['native_cadence_s']}")
    print(f"Continuous intervals: {result['interval_count']}")
    for reason, count in result["rejection_counts"].items():
        print(f"{reason}: {count}")


if __name__ == "__main__":
    main()
