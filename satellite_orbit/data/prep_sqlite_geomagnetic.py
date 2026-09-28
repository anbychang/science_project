"""Write local SYM-H and AE files into SQLite."""

from pathlib import Path

from satellite_orbit.data.load_geomagnetic import load_geomagnetic_file
from satellite_orbit.data.prep_sqlite_common import time_to_us

def geomagnetic_rows(file_path):
    """Input: local SYM-H or AE CSV path
    Output: [(time_us, value_nt, version), ...]"""
    observations = load_geomagnetic_file(file_path)
    return [
        (
            time_to_us(observation["time"]),
            observation["value_nt"],
            observation["version"],
        )
        for observation in observations
    ]


def write_sym_h(connection, geomagnetic_folder):
    """Input: {SQLite connection, geomagnetic folder}
    Output: number of SYM-H source rows written"""
    stored_rows = 0

    for file_path in sorted(Path(geomagnetic_folder).glob("sym_h_*.csv")):
        rows = geomagnetic_rows(file_path)
        connection.executemany(
            """
            INSERT INTO geomagnetic (time_us, sym_h_nt, sym_h_version)
            VALUES (?, ?, ?)
            ON CONFLICT(time_us) DO UPDATE SET
                sym_h_nt = excluded.sym_h_nt,
                sym_h_version = excluded.sym_h_version
            """,
            rows,
        )
        stored_rows += len(rows)

    return stored_rows


def write_ae(connection, geomagnetic_folder):
    """Input: {SQLite connection, geomagnetic folder}
    Output: number of AE source rows written"""
    stored_rows = 0

    for file_path in sorted(Path(geomagnetic_folder).glob("ae_*.csv")):
        rows = geomagnetic_rows(file_path)
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
        stored_rows += len(rows)

    return stored_rows
