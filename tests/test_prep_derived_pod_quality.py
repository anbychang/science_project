"""Check POD quality decisions and derived-table rebuilding."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_05_pod_quality import (
    create_quality_table,
    official_orbit_event_at,
    planned_orbit_raise_campaign_id,
    quality_row,
    row_provenance,
    starts_new_chunk,
    write_pod_quality,
)


def valid_row():
    """Input: none
    Output: one usable POD row"""
    return {
        "time_us": 1_000_000,
        "x_m": 7_000_000.0,
        "y_m": 0.0,
        "z_m": 0.0,
        "vx_m_s": 0.0,
        "vy_m_s": 7_500.0,
        "vz_m_s": 0.0,
        "semi_major_axis_m": 7_000_000.0,
        "orbital_rejection_reason": None,
    }


def chunk_row(time_us, file_name, frame="IGS20", cadence_s=10.0):
    """Input: source metadata for one POD time
    Output: row usable by chunk-boundary checks"""
    return {
        "time_us": time_us,
        "file_name": file_name,
        "sp3_frame_label": frame,
        "cadence_s": cadence_s,
    }


def previous_chunk_row(row, is_usable=True):
    """Input: one previous source row
    Output: quality context used by the next chunk check"""
    return {
        "time_us": row["time_us"],
        "is_usable": is_usable,
        "provenance": row_provenance(row),
    }


def insert_source_file(connection, source_id, file_name, frame="IGS20", cadence_s=10.0):
    """Input: SQLite connection and POD source metadata
    Output: raw source row and derived provenance row"""
    connection.execute(
        """
        INSERT INTO source_files (source_id, file_name, signature)
        VALUES (?, ?, ?)
        """,
        (source_id, file_name, "test-signature"),
    )
    connection.execute(
        """
        INSERT INTO swarm_a_pod_source_provenance (
            source_id, sp3_frame_label, coverage_start_time_us,
            coverage_end_time_us, epoch_count, cadence_s, time_system
        ) VALUES (?, ?, 0, 0, 1, ?, 'GPS')
        """,
        (source_id, frame, cadence_s),
    )


class PodQualityTest(unittest.TestCase):
    """Input: small synthetic POD rows
    Output: expected usability decisions"""

    def test_accepts_valid_row(self):
        """Input: finite state and valid orbital element
        Output: usable row"""
        result = quality_row(valid_row(), None)
        self.assertEqual(result, (1_000_000, 1, None, None))

    def test_rejects_non_finite_state(self):
        """Input: state with NaN position
        Output: non_finite_state reason"""
        row = valid_row()
        row["x_m"] = float("nan")
        result = quality_row(row, None)
        self.assertEqual(result[2], "non_finite_state")

    def test_rejects_missing_orbital_element(self):
        """Input: state without P1.3 result
        Output: missing_orbital_element reason"""
        row = valid_row()
        row["semi_major_axis_m"] = None
        result = quality_row(row, None)
        self.assertEqual(result[2], "missing_orbital_element")

    def test_rejects_invalid_orbital_energy(self):
        """Input: P1.3 rejected orbital state
        Output: invalid_orbital_energy reason"""
        row = valid_row()
        row["orbital_rejection_reason"] = "Orbit state is not bound to Earth."
        result = quality_row(row, None)
        self.assertEqual(result[2], "invalid_orbital_energy")

    def test_rejects_official_orbit_raise_campaign_dates(self):
        """Input: dates inside and outside official maneuver windows
        Output: each official operation has its typed rejection reason"""
        checks = [
            (
                datetime(2022, 1, 13, tzinfo=timezone.utc),
                "official_orbit_control_manoeuvre",
            ),
            (datetime(2022, 1, 14, tzinfo=timezone.utc), None),
            (datetime(2023, 4, 25, 23, 59, 59, tzinfo=timezone.utc), None),
            (
                datetime(2023, 4, 26, tzinfo=timezone.utc),
                "planned_orbit_raise_campaign",
            ),
            (
                datetime(2023, 6, 7, 23, 59, 59, tzinfo=timezone.utc),
                "planned_orbit_raise_campaign",
            ),
            (datetime(2023, 6, 8, tzinfo=timezone.utc), None),
            (
                datetime(2023, 1, 6, tzinfo=timezone.utc),
                "official_collision_avoidance_manoeuvre",
            ),
            (datetime(2023, 1, 7, tzinfo=timezone.utc), None),
            (
                datetime(2026, 7, 21, tzinfo=timezone.utc),
                "planned_orbit_raise_campaign",
            ),
            (
                datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc),
                "planned_orbit_raise_campaign",
            ),
            (datetime(2026, 8, 1, tzinfo=timezone.utc), None),
        ]
        for timestamp, expected_reason in checks:
            with self.subTest(timestamp=timestamp):
                row = valid_row()
                row["time_us"] = int(timestamp.timestamp() * 1_000_000)
                self.assertEqual(quality_row(row, None)[2], expected_reason)

    def test_identifies_official_single_day_maneuvers(self):
        """Input: maneuver dates and their exclusive stops
        Output: stable ID and kind only inside the official date window"""
        checks = [
            (
                datetime(2022, 1, 13, tzinfo=timezone.utc),
                ("SWA_ORBIT_CONTROL_2022-01-13", "orbit_control_manoeuvre"),
            ),
            (datetime(2022, 1, 14, tzinfo=timezone.utc), None),
            (
                datetime(2023, 1, 6, tzinfo=timezone.utc),
                ("SWA_CAM_2023-01-06", "collision_avoidance_manoeuvre"),
            ),
            (datetime(2023, 1, 7, tzinfo=timezone.utc), None),
        ]
        for timestamp, expected_event in checks:
            with self.subTest(timestamp=timestamp):
                time_us = int(timestamp.timestamp() * 1_000_000)
                self.assertEqual(official_orbit_event_at(time_us), expected_event)

    def test_identifies_campaign_at_its_half_open_boundaries(self):
        """Input: campaign starts and stops
        Output: only timestamps inside a campaign have its stable ID"""
        checks = [
            (
                datetime(2022, 5, 3, tzinfo=timezone.utc),
                "SWA_C_ORBIT_RAISE_2022",
            ),
            (
                datetime(2023, 4, 26, tzinfo=timezone.utc),
                "SWA_C_ORBIT_RAISE_2023_PHASE_II",
            ),
            (
                datetime(2026, 7, 21, tzinfo=timezone.utc),
                "SWA_C_ORBIT_RAISE_2026",
            ),
            (datetime(2026, 8, 1, tzinfo=timezone.utc), None),
        ]
        for timestamp, expected_campaign_id in checks:
            with self.subTest(timestamp=timestamp):
                time_us = int(timestamp.timestamp() * 1_000_000)
                self.assertEqual(
                    planned_orbit_raise_campaign_id(time_us),
                    expected_campaign_id,
                )

    def test_adjacent_sources_in_same_stream_keep_one_chunk(self):
        """Input: adjacent daily ZIPs with the same source conditions
        Output: no chunk boundary"""
        previous = chunk_row(
            0,
            "SW_OPER_SP3ACOM_2__20211231T235942_20220101T235942_0201.ZIP",
        )
        current = chunk_row(
            10_000_000,
            "SW_OPER_SP3ACOM_2__20220101T235942_20220102T235942_0201.ZIP",
        )
        self.assertFalse(starts_new_chunk(current, previous_chunk_row(previous)))

    def test_chunk_starts_when_source_conditions_change(self):
        """Input: changed frame, cadence, stream, or time continuity
        Output: one new chunk for every unsafe boundary"""
        previous = chunk_row(0, "SW_OPER_SP3ACOM_2__day_1.ZIP")
        changed_rows = [
            chunk_row(10_000_000, "SW_OPER_SP3ACOM_2__day_2.ZIP", frame="IGb20"),
            chunk_row(20_000_000, "SW_OPER_SP3ACOM_2__day_2.ZIP", cadence_s=20.0),
            chunk_row(10_000_000, "OTHER_PRODUCT__day_2.ZIP"),
            chunk_row(20_000_000, "SW_OPER_SP3ACOM_2__day_2.ZIP"),
        ]
        for row in changed_rows:
            with self.subTest(row=row):
                self.assertTrue(starts_new_chunk(row, previous_chunk_row(previous)))

    def test_unknown_source_metadata_starts_new_chunk(self):
        """Input: usable rows with incomplete source metadata
        Output: a safe boundary"""
        previous = chunk_row(0, "SW_OPER_SP3ACOM_2__day_1.ZIP")
        current = chunk_row(10_000_000, None)
        self.assertTrue(starts_new_chunk(current, previous_chunk_row(previous)))

    def test_rejected_previous_row_starts_new_chunk(self):
        """Input: usable row after a rejected row
        Output: new chunk"""
        previous = chunk_row(0, "SW_OPER_SP3ACOM_2__day_1.ZIP")
        current = chunk_row(10_000_000, "SW_OPER_SP3ACOM_2__day_2.ZIP")
        self.assertTrue(starts_new_chunk(current, previous_chunk_row(previous, False)))

    def test_rebuild_removes_stale_quality_rows(self):
        """Input: raw POD rows and one obsolete derived row
        Output: only quality rows matching raw POD remain"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "quality.sqlite"
            with sqlite3.connect(database_path) as connection:
                create_tables(connection)
                connection.execute(
                    """
                    CREATE TABLE swarm_a_orbital_elements (
                        time_us INTEGER PRIMARY KEY,
                        semi_major_axis_m REAL,
                        rejection_reason TEXT
                    )
                    """
                )
                connection.executemany(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (0, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, 0, 1),
                        (10_000_000, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, 0, 1),
                    ],
                )
                connection.executemany(
                    "INSERT INTO swarm_a_orbital_elements VALUES (?, ?, ?)",
                    [(0, 7e6, None), (10_000_000, 7e6, None)],
                )
                insert_source_file(
                    connection,
                    1,
                    "SW_OPER_SP3ACOM_2__20220101T000000_20220102T000000_0201.ZIP",
                )
                connection.execute(
                    """
                    CREATE TABLE swarm_a_pod_quality (
                        time_us INTEGER PRIMARY KEY,
                        is_usable INTEGER NOT NULL,
                        rejection_reason TEXT,
                        interval_id INTEGER
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
                    (99_000_000, 1, None, 99),
                )
            connection.close()

            result = write_pod_quality(database_path)

            with sqlite3.connect(database_path) as connection:
                quality_rows = connection.execute(
                    "SELECT time_us, chunk_id FROM swarm_a_pod_quality ORDER BY time_us"
                ).fetchall()
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(swarm_a_pod_quality)")
                }
            connection.close()

        self.assertEqual(result["raw_rows"], 2)
        self.assertEqual(quality_rows, [(0, 1), (10_000_000, 1)])
        self.assertEqual(columns, {"time_us", "is_usable", "rejection_reason", "chunk_id"})

    def test_rebuild_refuses_to_invalidate_downstream_output(self):
        """Input: populated mean-orbit output
        Output: quality rebuild fails before changing its upstream contract"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "quality.sqlite"
            with sqlite3.connect(database_path) as connection:
                create_tables(connection)
                connection.execute(
                    "CREATE TABLE swarm_a_mean_orbital_elements (time_us INTEGER PRIMARY KEY)"
                )
                connection.execute(
                    "INSERT INTO swarm_a_mean_orbital_elements VALUES (1)"
                )
            connection.close()

            with self.assertRaisesRegex(ValueError, "invalidate downstream output"):
                write_pod_quality(database_path)

    def test_writer_keeps_adjacent_same_stream_sources_in_one_chunk(self):
        """Input: two adjacent daily source files in one stream
        Output: both usable rows share one chunk ID"""
        with tempfile.TemporaryDirectory() as temporary_folder:
            database_path = Path(temporary_folder) / "chunks.sqlite"
            with sqlite3.connect(database_path) as connection:
                create_tables(connection)
                connection.execute(
                    """
                    CREATE TABLE swarm_a_orbital_elements (
                        time_us INTEGER PRIMARY KEY,
                        semi_major_axis_m REAL,
                        rejection_reason TEXT
                    )
                    """
                )
                insert_source_file(connection, 1, "SW_OPER_SP3ACOM_2__day_1.ZIP")
                insert_source_file(connection, 2, "SW_OPER_SP3ACOM_2__day_2.ZIP")
                connection.executemany(
                    "INSERT INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (0, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, 0, 1),
                        (10_000_000, 7e6, 0.0, 0.0, 0.0, 7500.0, 0.0, 0, 2),
                    ],
                )
                connection.executemany(
                    "INSERT INTO swarm_a_orbital_elements VALUES (?, ?, ?)",
                    [(0, 7e6, None), (10_000_000, 7e6, None)],
                )

            result = write_pod_quality(database_path)

            with sqlite3.connect(database_path) as connection:
                chunk_ids = connection.execute(
                    "SELECT chunk_id FROM swarm_a_pod_quality ORDER BY time_us"
                ).fetchall()
            connection.close()

        self.assertEqual(result["chunk_count"], 1)
        self.assertEqual(chunk_ids, [(1,), (1,)])


if __name__ == "__main__":
    unittest.main()
