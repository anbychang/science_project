"""Check 10-minute Swarm-A mean-orbit storage."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_04_mean_orbit import create_mean_orbit_table
from satellite_orbit.data.pod.prep_06_orbit_10min import (
    ALGORITHM_VERSION,
    write_orbit_10min,
)
from satellite_orbit.data.pod.prep_05_pod_quality import create_quality_table


BIN_START_US = 1_800_000_000_000_000


def create_database(database_path):
    """Input: SQLite path
    Output: database with P1.5-B input tables"""
    with sqlite3.connect(database_path) as connection:
        create_tables(connection)
        create_quality_table(connection)
        create_mean_orbit_table(connection)
    connection.close()


def add_mean_rows(connection, offsets_s, chunk_id):
    """Input: offsets in seconds and one quality chunk
    Output: matching state, quality, and mean-orbit rows"""
    rows = [
        (
            BIN_START_US + offset_s * 1_000_000,
            7_000_000.0 + row_index,
            chunk_id,
        )
        for row_index, offset_s in enumerate(offsets_s)
    ]
    connection.executemany(
        "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (time_us, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, time_us, 1)
            for time_us, _, _ in rows
        ],
    )
    connection.executemany(
        "INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
        [(time_us, 1, None, row_chunk_id) for time_us, _, row_chunk_id in rows],
    )
    connection.executemany(
        "INSERT INTO swarm_a_mean_orbital_elements VALUES (?, ?, ?)",
        [(time_us, mean_a, None) for time_us, mean_a, _ in rows],
    )


class Orbit10MinuteStorageTest(unittest.TestCase):
    """Input: small completed mean-orbit sequences
    Output: chunk-local UTC 10-minute rows"""

    def test_writes_full_10_minute_bin(self):
        """Input: 60 contiguous 10-second mean-orbit rows
        Output: one mean 10-minute row"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "orbit_10min.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_mean_rows(connection, range(0, 600, 10), 1)
            connection.close()

            result = write_orbit_10min(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_row = connection.execute(
                    "SELECT * FROM swarm_a_orbit_10min"
                ).fetchone()
            connection.close()

        self.assertEqual(result["stored_rows"], 1)
        self.assertEqual(
            stored_row,
            (
                BIN_START_US + 600_000_000,
                7_000_029.5,
                60,
                10.0,
                1,
                ALGORITHM_VERSION,
            ),
        )

    def test_writes_56_row_chunk_edge_bin(self):
        """Input: 56 contiguous rows in the only bin of a chunk
        Output: one accepted edge bin"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "edge_10min.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_mean_rows(connection, range(0, 560, 10), 1)
            connection.close()

            write_orbit_10min(database_path)

            with sqlite3.connect(database_path) as connection:
                pod_count = connection.execute(
                    "SELECT pod_count FROM swarm_a_orbit_10min"
                ).fetchone()[0]
            connection.close()

        self.assertEqual(pod_count, 56)

    def test_keeps_one_chunk_across_two_source_ids(self):
        """Input: 60 contiguous chunk rows from two source IDs
        Output: one complete 10-minute row"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "sources_10min.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_mean_rows(connection, range(0, 600, 10), 1)
                connection.execute(
                    "UPDATE swarm_a_states SET source_id = 2 WHERE time_us >= ?",
                    (BIN_START_US + 300_000_000,),
                )
            connection.close()

            write_orbit_10min(database_path)

            with sqlite3.connect(database_path) as connection:
                pod_count = connection.execute(
                    "SELECT pod_count FROM swarm_a_orbit_10min"
                ).fetchone()[0]
            connection.close()

        self.assertEqual(pod_count, 60)

    def test_rejects_55_row_bin(self):
        """Input: 55 contiguous mean-orbit rows
        Output: no 10-minute row"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "short_10min.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_mean_rows(connection, range(0, 550, 10), 1)
            connection.close()

            write_orbit_10min(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_rows = connection.execute(
                    "SELECT count(*) FROM swarm_a_orbit_10min"
                ).fetchone()[0]
            connection.close()

        self.assertEqual(stored_rows, 0)

    def test_rejects_bin_with_a_gap_larger_than_10_seconds(self):
        """Input: 59 rows with one 20-second gap
        Output: no 10-minute row"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "gap_10min.sqlite"
            create_database(database_path)
            offsets_s = [offset_s for offset_s in range(0, 600, 10) if offset_s != 300]
            with sqlite3.connect(database_path) as connection:
                add_mean_rows(connection, offsets_s, 1)
            connection.close()

            write_orbit_10min(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_rows = connection.execute(
                    "SELECT count(*) FROM swarm_a_orbit_10min"
                ).fetchone()[0]
            connection.close()

        self.assertEqual(stored_rows, 0)

    def test_rejects_56_row_bin_inside_a_chunk(self):
        """Input: a short bin between two full bins in one chunk
        Output: the short middle bin is not written"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "middle_10min.sqlite"
            create_database(database_path)
            offsets_s = list(range(0, 600, 10))
            offsets_s += list(range(600, 1160, 10))
            offsets_s += list(range(1200, 1800, 10))
            with sqlite3.connect(database_path) as connection:
                add_mean_rows(connection, offsets_s, 1)
            connection.close()

            write_orbit_10min(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_times = connection.execute(
                    "SELECT time_us FROM swarm_a_orbit_10min ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(stored_times, [(BIN_START_US + 600_000_000,)])

    def test_does_not_mix_chunks_in_one_utc_bin(self):
        """Input: one UTC bin split across two chunks
        Output: only the independently valid chunk edge is written"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "chunks_10min.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                add_mean_rows(connection, range(0, 560, 10), 1)
                add_mean_rows(connection, range(560, 600, 10), 2)
            connection.close()

            write_orbit_10min(database_path)

            with sqlite3.connect(database_path) as connection:
                stored_rows = connection.execute(
                    "SELECT pod_count, chunk_id FROM swarm_a_orbit_10min"
                ).fetchall()
            connection.close()

        self.assertEqual(stored_rows, [(56, 1)])

    def test_rejects_incomplete_mean_orbit_input(self):
        """Input: usable POD row without a mean-orbit result
        Output: clear incomplete-input error"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "incomplete_10min.sqlite"
            create_database(database_path)
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (BIN_START_US, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, BIN_START_US, 1),
                )
                connection.execute(
                    "INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
                    (BIN_START_US, 1, None, 1),
                )
            connection.close()

            with self.assertRaisesRegex(ValueError, "1 usable mean-orbit rows are incomplete"):
                write_orbit_10min(database_path)

if __name__ == "__main__":
    unittest.main()
