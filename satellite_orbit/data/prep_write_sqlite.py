"""Build the local SQLite database from downloaded files."""

import sqlite3
from pathlib import Path

from satellite_orbit.data.prep_sqlite_density import write_density_folder
from satellite_orbit.data.prep_sqlite_geomagnetic import write_geomagnetic
from satellite_orbit.data.prep_sqlite_pod import write_pod_folder
from satellite_orbit.data.prep_sqlite_tables import create_tables
from satellite_orbit.data.prep_sqlite_weather import write_space_weather

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
DEFAULT_POD_FOLDER = Path("data/swarm_a_pod")
DEFAULT_WEATHER_FILE = Path("data/space_weather/SW-All.csv")
DEFAULT_GEOMAGNETIC_FOLDER = Path("data/geomagnetic")
DEFAULT_DENSITY_FOLDER = Path("data/swarm_density_acc")


def weather_times(connection):
    """Input: SQLite connection
    Output: {weather time_us, ...}"""
    times = set()
    for row in connection.execute("SELECT time_us FROM space_weather"):
        times.add(row[0])
    return times


def write_sqlite_database(
    database_path=DEFAULT_DATABASE,
    pod_folder=DEFAULT_POD_FOLDER,
    weather_file=DEFAULT_WEATHER_FILE,
    geomagnetic_folder=DEFAULT_GEOMAGNETIC_FOLDER,
    density_folder=DEFAULT_DENSITY_FOLDER,
):
    """Input: {database path, downloaded data folders}
    Output: {database path, written row counts}"""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        create_tables(connection)
        weather_rows = write_space_weather(connection, weather_file)
        sym_h_rows = write_geomagnetic(connection, geomagnetic_folder, "sym_h")
        ae_rows = write_geomagnetic(connection, geomagnetic_folder, "ae")
        known_weather_times = weather_times(connection)

        pod_files, state_rows = write_pod_folder(
            connection,
            pod_folder,
            known_weather_times,
        )
        density_files, density_rows = write_density_folder(
            connection,
            density_folder,
        )

    return {
        "database_path": database_path,
        "weather_rows": weather_rows,
        "sym_h_rows": sym_h_rows,
        "ae_rows": ae_rows,
        "pod_files": pod_files,
        "state_rows": state_rows,
        "density_files": density_files,
        "density_rows": density_rows,
    }


def main():
    """Input: python -m satellite_orbit.data.prep_write_sqlite
    Output: database update summary"""
    result = write_sqlite_database()
    print(f"Database: {result['database_path']}")
    print(f"Weather rows added: {result['weather_rows']}")
    print(f"SYM-H source rows stored: {result['sym_h_rows']}")
    print(f"AE source rows stored: {result['ae_rows']}")
    print(f"POD files changed: {result['pod_files']}")
    print(f"Orbit states added: {result['state_rows']}")
    print(f"Density files added: {result['density_files']}")
    print(f"Density points added: {result['density_rows']}")


if __name__ == "__main__":
    main()
