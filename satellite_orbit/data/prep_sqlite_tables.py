"""Create the SQLite tables used by the local data store."""


def create_tables(connection):
    """Input: SQLite connection
    Output: required tables exist"""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS space_weather (
            time_us INTEGER PRIMARY KEY,
            f107_sfu REAL NOT NULL,
            f107a_sfu REAL NOT NULL,
            ap_daily REAL NOT NULL,
            ap_now REAL NOT NULL,
            ap_3h REAL NOT NULL,
            ap_6h REAL NOT NULL,
            ap_9h REAL NOT NULL,
            ap_12_to_33h_avg REAL NOT NULL,
            ap_36_to_57h_avg REAL NOT NULL,
            f107_data_type TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS geomagnetic (
            time_us INTEGER PRIMARY KEY,
            sym_h_nt REAL,
            ae_nt REAL,
            sym_h_version INTEGER,
            ae_version INTEGER
        );

        CREATE TABLE IF NOT EXISTS swarm_a_states (
            time_us INTEGER PRIMARY KEY,
            x_m REAL NOT NULL,
            y_m REAL NOT NULL,
            z_m REAL NOT NULL,
            vx_m_s REAL NOT NULL,
            vy_m_s REAL NOT NULL,
            vz_m_s REAL NOT NULL,
            weather_time_us INTEGER NOT NULL,
            source_id INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS swarm_a_density (
            time_us INTEGER PRIMARY KEY,
            density_kg_m3 REAL NOT NULL,
            altitude_m REAL NOT NULL,
            latitude_deg REAL NOT NULL,
            longitude_deg REAL NOT NULL,
            local_solar_time_h REAL NOT NULL,
            source_file_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_files (
            source_id INTEGER PRIMARY KEY,
            file_name TEXT NOT NULL UNIQUE,
            signature TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
