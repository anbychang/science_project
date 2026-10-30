"""Check the saved Trial5 recovery SQLite contract."""

import csv
import sqlite3
from pathlib import Path


TRIAL5_ROOT = Path(__file__).resolve().parents[1]
DATABASE = TRIAL5_ROOT / "data/sqlite/swarm_a_trial5_recovery_v1.sqlite"
EVENT_CSV = TRIAL5_ROOT / "data/analysis/trial5_recovery_events.csv"
EXPECTED_STORM_COUNT = 25
EXPECTED_MINUTE_COUNT = 214_907


def read_database() -> sqlite3.Connection:
    """Input: saved Trial5 SQLite path. Output: open read-only SQLite connection."""
    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def test_sqlite_preserves_all_trial5_minutes_and_storms() -> None:
    """Input: Trial5 SQLite. Output: expected counts and integrity status."""
    with read_database() as database:
        minute_count = database.execute(
            "SELECT count(*) FROM trial5_recovery_minute"
        ).fetchone()[0]
        storm_count = database.execute(
            "SELECT count(*) FROM trial5_25storm_recovery_overview"
        ).fetchone()[0]
        integrity = database.execute("PRAGMA integrity_check").fetchone()[0]
    assert minute_count == EXPECTED_MINUTE_COUNT
    assert storm_count == EXPECTED_STORM_COUNT
    assert integrity == "ok"


def test_sqlite_keeps_recovery_parameters_in_their_bounds() -> None:
    """Input: Trial5 SQLite. Output: nonnegative amplitude and positive time values."""
    with read_database() as database:
        invalid_count = database.execute("""
            SELECT count(*) FROM trial5_recovery_minute
            WHERE recovery_amplitude_log_density < 0 OR recovery_time_hours <= 0
        """).fetchone()[0]
    assert invalid_count == 0


def test_sqlite_overview_matches_saved_event_csv() -> None:
    """Input: Trial5 SQLite and event CSV. Output: identical storm-level amplitudes."""
    with EVENT_CSV.open(encoding="utf-8-sig", newline="") as source:
        csv_amplitudes = {
            row["storm_id"]: float(row["recovery_amplitude_log_density"])
            for row in csv.DictReader(source)
        }
    with read_database() as database:
        sqlite_amplitudes = {
            storm_id: amplitude
            for storm_id, amplitude in database.execute("""
                SELECT storm_id,recovery_amplitude_log_density
                FROM trial5_25storm_recovery_overview
            """)
        }
    assert sqlite_amplitudes == csv_amplitudes
