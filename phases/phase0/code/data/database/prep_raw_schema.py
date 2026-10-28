"""Create the SQLite tables used by the local data store."""

import sqlite3


def connect_database(database_path):
    """Input: SQLite database path
    Output: connection with foreign-key enforcement enabled"""
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables(connection):
    """Input: SQLite connection
    Output: required tables exist"""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS space_weather (
            time_us INTEGER PRIMARY KEY,
            f107_sfu REAL NOT NULL,
            f107a_sfu REAL NOT NULL,
            f107a_last81_sfu REAL,
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

        CREATE TABLE IF NOT EXISTS source_files (
            source_id INTEGER PRIMARY KEY,
            file_name TEXT NOT NULL UNIQUE,
            signature TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS swarm_a_pod_source_provenance (
            source_id INTEGER PRIMARY KEY,
            sp3_frame_label TEXT NOT NULL,
            coverage_start_time_us INTEGER NOT NULL,
            coverage_end_time_us INTEGER NOT NULL,
            epoch_count INTEGER NOT NULL,
            cadence_s REAL NOT NULL,
            time_system TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES source_files(source_id)
        );

        CREATE TABLE IF NOT EXISTS metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    add_f107a_last81_column(connection)


def add_f107a_last81_column(connection):
    """Input: SQLite connection
    Output: space_weather has f107a_last81_sfu"""
    columns = connection.execute("PRAGMA table_info(space_weather)").fetchall()
    column_names = set()
    for column in columns:
        column_names.add(column[1])
    if "f107a_last81_sfu" not in column_names:
        connection.execute("ALTER TABLE space_weather ADD COLUMN f107a_last81_sfu REAL")
