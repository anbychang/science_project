"""Write local geomagnetic index files into SQLite."""

from pathlib import Path

from satellite_orbit.data.load_geomagnetic import load_geomagnetic_file
from satellite_orbit.data.prep_sqlite_common import time_to_us

INDEX_COLUMNS = {
    "sym_h": ("sym_h_nt", "sym_h_version"),
    "ae": ("ae_nt", "ae_version"),
}


def geomagnetic_row(observation):
    """Input: {time, value_nt, version}
    Output: (time_us, value_nt, version)"""
    return (
        time_to_us(observation["time"]),
        observation["value_nt"],
        observation["version"],
    )


def write_geomagnetic(connection, geomagnetic_folder, index_name):
    """Input: {SQLite connection, geomagnetic folder, sym_h or ae}
    Output: number of source rows written"""
    if index_name not in INDEX_COLUMNS:
        raise ValueError(f"Unsupported geomagnetic index: {index_name}")

    value_column, version_column = INDEX_COLUMNS[index_name]
    query = f"""
        INSERT INTO geomagnetic (time_us, {value_column}, {version_column})
        VALUES (?, ?, ?)
        ON CONFLICT(time_us) DO UPDATE SET
            {value_column} = excluded.{value_column},
            {version_column} = excluded.{version_column}
    """
    stored_rows = 0

    for file_path in sorted(Path(geomagnetic_folder).glob(f"{index_name}_*.csv")):
        observations = load_geomagnetic_file(file_path)
        rows = [geomagnetic_row(observation) for observation in observations]
        connection.executemany(query, rows)
        stored_rows += len(rows)

    return stored_rows
