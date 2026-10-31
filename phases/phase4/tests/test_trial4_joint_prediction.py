"""Check the saved Trial4 joint-fit SQLite contract."""

import sqlite3
from pathlib import Path


TRIAL4_ROOT = Path(__file__).resolve().parents[1]
DATABASE = TRIAL4_ROOT / "data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite"
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
    """Input: Trial4 fit and prediction tables. Output: identical per-storm R and tau."""
    with read_database() as database:
        fit_parameters = {
            storm_id: (r_fit, tau_hours)
            for storm_id, r_fit, tau_hours in database.execute("""
                SELECT storm_id,r_fit,tau_hours FROM trial4_joint_fit_events
                WHERE model='D_free_r_tau'
            """)
        }
        sqlite_parameters = {
            storm_id: (r_fit, tau_hours)
            for storm_id, r_fit, tau_hours in database.execute("""
                SELECT storm_id,r_fit,tau_hours FROM trial4_25storm_overview
            """)
        }
    assert sqlite_parameters == fit_parameters


def test_phase4_stores_joint_fit_outputs_in_sqlite() -> None:
    """Input: Phase 4 D-model SQLite. Output: all joint-fit output tables exist."""
    with read_database() as database:
        tables = {
            row[0] for row in database.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN (
                    'trial4_joint_fit_models',
                    'trial4_joint_fit_events',
                    'trial4_joint_fit_iterations',
                    'trial4_25storm_overview'
                )
            """)
        }
    assert tables == {
        'trial4_joint_fit_models',
        'trial4_joint_fit_events',
        'trial4_joint_fit_iterations',
        'trial4_25storm_overview',
    }


def test_phase4_does_not_store_csv_outputs() -> None:
    """Input: Phase 4 analysis folder. Output: no CSV output files."""
    assert not list((TRIAL4_ROOT / 'data/analysis').glob('*.csv'))
