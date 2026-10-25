import math
import sqlite3

import pytest

from satellite_orbit.phase2.prep_23_t0_phase_window import (
    PHASE_ORBITS_AFTER,
    PHASE_ORBITS_BEFORE,
    PhaseWindow,
    phase_series,
    phase_window,
)


def phase_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Input: in-memory SQLite. Output: uniformly sampled Phase 1 rows."""
    connection.execute("CREATE TABLE phase (time_us,chunk_id,mean_argument_of_perigee_rad,mean_anomaly_rad)")
    phase_step = math.tau / 10
    connection.executemany(
        "INSERT INTO phase VALUES (?,?,?,?)",
        ((index * 10_000_000, 1, 0.0, (index * phase_step + phase_step / 2) % math.tau)
         for index in range(1_200)),
    )
    return connection.execute("SELECT * FROM phase ORDER BY time_us").fetchall()


def event_row(connection: sqlite3.Connection) -> sqlite3.Row:
    """Input: in-memory SQLite. Output: one P2.2 event row."""
    connection.execute("CREATE TABLE event (storm_id,t0_time_us,symh_min_nt,compound,n_minima)")
    connection.execute("INSERT INTO event VALUES ('S',4000000000,-120,0,1)")
    return connection.execute("SELECT * FROM event").fetchone()


def test_phase_window_uses_t0_phase_not_u_zero() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    rows = phase_rows(connection)
    window = phase_window(event_row(connection), phase_series(rows))

    assert isinstance(window, PhaseWindow)
    assert window.start_phase_rad == pytest.approx(
        window.t0_phase_rad - PHASE_ORBITS_BEFORE * math.tau
    )
    assert window.end_phase_rad == pytest.approx(
        window.t0_phase_rad + PHASE_ORBITS_AFTER * math.tau
    )
    assert window.start_us % 10_000_000 == 0
    assert window.end_us % 10_000_000 == 0
    connection.close()
