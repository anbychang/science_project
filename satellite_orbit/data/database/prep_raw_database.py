"""Build the local SQLite database from downloaded files."""

from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import connect_database, create_tables
from satellite_orbit.data.density.prep_raw_density import write_density_folder
from satellite_orbit.data.geomagnetic.prep_raw_geomagnetic import write_ae, write_sym_h
from satellite_orbit.data.pod.prep_raw_pod import write_pod_folder
from satellite_orbit.data.space_weather.prep_raw_weather import write_space_weather

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
DEFAULT_POD_FOLDER = Path("data/swarm_a_pod")
DEFAULT_WEATHER_FILE = Path("data/space_weather/SW-All.csv")
DEFAULT_GEOMAGNETIC_FOLDER = Path("data/geomagnetic")
DEFAULT_DENSITY_FOLDER = Path("data/swarm_density_acc")


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

    with connect_database(database_path) as connection:
        create_tables(connection)
        weather_rows = write_space_weather(connection, weather_file)
        sym_h_rows = write_sym_h(connection, geomagnetic_folder)
        ae_rows = write_ae(connection, geomagnetic_folder)
        known_weather_times = {
            row[0] for row in connection.execute("SELECT time_us FROM space_weather")
        }

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
    """Input: python -m satellite_orbit.data.database.prep_raw_database
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
