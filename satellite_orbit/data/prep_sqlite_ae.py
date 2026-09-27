"""Write local AE files into SQLite."""

from pathlib import Path

from satellite_orbit.data.load_geomagnetic import load_geomagnetic_file
from satellite_orbit.data.prep_sqlite_common import time_to_us


def ae_row(observation):
    """Input: {time, value_nt, version}
    Output: (time_us, ae_nt, version)"""
    return (
        time_to_us(observation["time"]),
        observation["value_nt"],
        observation["version"],
    )


def write_ae(connection, geomagnetic_folder):
    """Input: {SQLite connection, geomagnetic folder}
    Output: number of AE source rows read"""
    stored_rows = 0
    for file_path in sorted(Path(geomagnetic_folder).glob("ae_*.csv")):
        observations = load_geomagnetic_file(file_path)
        rows = []
        for observation in observations:
            rows.append(ae_row(observation))
        stored_rows += len(rows)
        connection.executemany(
            """
            INSERT INTO geomagnetic (time_us, ae_nt, ae_version)
            VALUES (?, ?, ?)
            ON CONFLICT(time_us) DO UPDATE SET
                ae_nt = excluded.ae_nt,
                ae_version = excluded.ae_version
            """,
            rows,
        )
    return stored_rows
