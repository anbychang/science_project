"""Write local SYM-H and AE files into SQLite."""

from pathlib import Path

from research_workspace.phases.phase0.code.data.database.prep_raw_identifiers import time_to_us
from research_workspace.phases.phase0.code.data.geomagnetic.load_geomagnetic import load_geomagnetic_file

def geomagnetic_rows(file_path):
    """Input: local SYM-H or AE CSV path
    Output: [(time_us, value_nt, version), ...]"""
    return [
        (
            time_to_us(observation["time"]),
            observation["value_nt"],
            observation["version"],
        )
        for observation in load_geomagnetic_file(file_path)
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
            WHERE geomagnetic.sym_h_nt IS NULL
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
            WHERE geomagnetic.ae_nt IS NULL
            """,
            rows,
        )
        stored_rows += len(rows)

    return stored_rows
