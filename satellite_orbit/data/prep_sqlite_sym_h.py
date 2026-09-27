"""Write local SYM-H CSV files into SQLite."""

import csv
from datetime import datetime
from pathlib import Path

from satellite_orbit.data.prep_sqlite_common import time_to_us

def read_sym_h_file(file_path):
    """Input: SYM-H CSV path
    Output: [(time_us, sym_h_nt, version), ...]"""
    rows = []
    with Path(file_path).open(encoding="utf-8", newline="") as file:
        for row in csv.reader(file):
            if not row or row[0].startswith("#"):
                continue
            if int(row[1]) == 99999:
                continue
            time_utc = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            rows.append((time_to_us(time_utc), int(row[1]), int(row[2])))
    return rows


def write_sym_h(connection, geomagnetic_folder):
    """Input: {SQLite connection, geomagnetic folder}
    Output: number of SYM-H source rows read"""
    stored_rows = 0
    for file_path in sorted(Path(geomagnetic_folder).glob("sym_h_*.csv")):
        rows = read_sym_h_file(file_path)
        stored_rows += len(rows)
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
    return stored_rows
