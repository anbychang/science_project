"""Check the saved Trial4 joint-fit SQLite contract."""

import csv
import sqlite3
from pathlib import Path


TRIAL4_ROOT = Path(__file__).resolve().parents[1]
DATABASE = TRIAL4_ROOT / "data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite"
EVENT_CSV = TRIAL4_ROOT / "data/analysis/trial4_joint_fit_tau15_events.csv"
EXPECTED_STORM_COUNT = 25
EXPECTED_MINUTE_COUNT = 214_907


def read_database() -> sqlite3.Connection:
    """Input: saved Trial4 SQLite path. Output: open read-only SQLite connection."""
    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def test_sqlite_preserves_all_trial4_minutes_and_storms() -> None:
    """Input: Trial4 SQLite. Output: expected table counts and integrity status."""
    with read_database() as database:
        minute_count = database.execute(
            "SELECT count(*) FROM trial4_joint_fit_minute"
        ).fetchone()[0]
        storm_count = database.execute(
            "SELECT count(*) FROM trial4_25storm_overview"
        ).fetchone()[0]
        integrity = database.execute("PRAGMA integrity_check").fetchone()[0]
    assert minute_count == EXPECTED_MINUTE_COUNT
    assert storm_count == EXPECTED_STORM_COUNT
    assert integrity == "ok"


def test_sqlite_overview_matches_minute_rows_and_parameter_bounds() -> None:
    """Input: Trial4 SQLite. Output: aligned event counts and valid fit limits."""
    with read_database() as database:
        mismatch_count = database.execute("""
            SELECT count(*) FROM trial4_25storm_overview AS overview
            WHERE valid_phase_minutes <> (
                SELECT count(*) FROM trial4_joint_fit_minute AS minute
                WHERE minute.storm_id=overview.storm_id
            )
        """).fetchone()[0]
        invalid_count = database.execute("""
            SELECT count(*) FROM trial4_joint_fit_minute
            WHERE r_fit <= 0 OR r_fit >= 2 OR tau_hours < 0 OR tau_hours > 15
               OR gain_per_nt <= 0
        """).fetchone()[0]
    assert mismatch_count == 0
    assert invalid_count == 0


def test_sqlite_overview_uses_saved_d_model_parameters() -> None:
    """Input: Trial4 D CSV and SQLite. Output: identical per-storm R and tau."""
    with EVENT_CSV.open(encoding="utf-8-sig", newline="") as source:
        csv_parameters = {
            row["storm_id"]: (float(row["r_fit"]), float(row["tau_hours"]))
            for row in csv.DictReader(source)
            if row["model"] == "D_free_r_tau"
        }
    with read_database() as database:
        sqlite_parameters = {
            storm_id: (r_fit, tau_hours)
            for storm_id, r_fit, tau_hours in database.execute("""
                SELECT storm_id,r_fit,tau_hours FROM trial4_25storm_overview
            """)
        }
    assert sqlite_parameters == csv_parameters
