"""Write local Swarm DNSAACC density files into SQLite."""

from pathlib import Path

from satellite_orbit.data.load_swarm_density import load_swarm_density
from satellite_orbit.data.prep_sqlite_common import time_to_us


def density_row(density_point, file_name):
    """Input: {density point, source file name}
    Output: one swarm_a_density table row"""
    return (
        time_to_us(density_point["time"]),
        density_point["density_kg_m3"],
        density_point["altitude_m"],
        density_point["latitude_deg"],
        density_point["longitude_deg"],
        density_point["local_solar_time_h"],
        file_name,
    )


def density_file_is_written(connection, file_name):
    """Input: {SQLite connection, density ZIP file name}
    Output: True when this source file is already stored"""
    row = connection.execute(
        "SELECT 1 FROM swarm_a_density WHERE source_file_name = ? LIMIT 1",
        (file_name,),
    ).fetchone()
    return row is not None


def write_density_folder(connection, density_folder):
    """Input: {SQLite connection, density ZIP folder}
    Output: (new source files, stored density points)"""
    stored_files = 0
    stored_points = 0

    for zip_path in sorted(Path(density_folder).glob("*.ZIP")):
        if density_file_is_written(connection, zip_path.name):
            continue
        density_points = load_swarm_density(zip_path)
        rows = []
        for density_point in density_points:
            rows.append(density_row(density_point, zip_path.name))
        connection.executemany(
            "INSERT OR REPLACE INTO swarm_a_density VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        stored_files += 1
        stored_points += len(rows)

    return stored_files, stored_points
