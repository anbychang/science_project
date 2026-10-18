"""Store fixed SP3 provenance for each immutable POD source file."""

import sqlite3
from pathlib import Path

from satellite_orbit.data.database.prep_raw_identifiers import time_to_us
from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.load_sp3_inventory import load_sp3_inventory

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
DEFAULT_POD_FOLDER = Path("data/swarm_a_pod")


def source_provenance_row(inventory):
    """Input: SP3 inventory
    Output: SQLite derived provenance tuple"""
    return (
        inventory["sp3_frame_label"],
        time_to_us(inventory["coverage_start"]),
        time_to_us(inventory["coverage_end"]),
        inventory["epoch_count"],
        inventory["cadence_s"],
        inventory["time_system"],
    )


def write_source_provenance(connection, pod_folder):
    """Input: SQLite connection and POD folder
    Output: number of source provenance rows written"""
    source_ids = {
        row[1]: row[0]
        for row in connection.execute("SELECT source_id, file_name FROM source_files")
    }
    zip_paths = sorted(Path(pod_folder).rglob("*.ZIP"))
    if set(source_ids) != {path.name for path in zip_paths}:
        raise ValueError("POD ZIP files do not match source_files provenance.")

    written_rows = 0
    for zip_path in zip_paths:
        values = source_provenance_row(load_sp3_inventory(zip_path))
        source_id = source_ids[zip_path.name]
        old_values = connection.execute(
            """
            SELECT sp3_frame_label, coverage_start_time_us, coverage_end_time_us,
                   epoch_count, cadence_s, time_system
            FROM swarm_a_pod_source_provenance WHERE source_id = ?
            """,
            (source_id,),
        ).fetchone()
        if old_values == values:
            continue
        if old_values is not None:
            raise ValueError(f"Source provenance changed for {zip_path.name}.")
        connection.execute(
            """
            INSERT INTO swarm_a_pod_source_provenance (
                sp3_frame_label, coverage_start_time_us, coverage_end_time_us,
                epoch_count, cadence_s, time_system, source_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (*values, source_id),
        )
        written_rows += 1
    return written_rows


def write_database_provenance(database_path=DEFAULT_DATABASE, pod_folder=DEFAULT_POD_FOLDER):
    """Input: SQLite database path and POD folder
    Output: number of written source provenance rows"""
    with sqlite3.connect(database_path) as connection:
        create_tables(connection)
        return write_source_provenance(connection, pod_folder)


def main():
    """Input: python -m satellite_orbit.data.pod.prep_02_source_provenance
    Output: written source provenance row count"""
    print(f"POD source provenance rows written: {write_database_provenance()}")


if __name__ == "__main__":
    main()
