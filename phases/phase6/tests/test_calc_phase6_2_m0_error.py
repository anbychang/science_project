import sqlite3

from phases.phase6.code.calc_phase6_2_m0_error import (
    JoinedMinute,
    create_tables,
    store_decay,
)


def event_minutes() -> list[JoinedMinute]:
    """Input: none. Output: two three-minute continuous synthetic storm windows."""
    rows = []
    for storm_index, storm_id in enumerate(("S1", "S2")):
        for minute_index in range(3):
            rows.append(JoinedMinute(
                storm_id=storm_id,
                time_us=(storm_index * 10 + minute_index) * 60_000_000,
                chunk_id=1,
                semi_major_axis_m=6_800_000.0 - minute_index,
                m0_density_kg_m3=1.0e-12,
            ))
    return rows


def test_fixed_beff_is_applied_without_refit():
    """Input: two storm windows and fixed B_eff. Output: every row keeps that B_eff."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)

    minute_count, summary = store_decay(connection, iter(event_minutes()), 0.01)
    beff_values = connection.execute(
        "SELECT DISTINCT b_eff_m2_kg FROM phase6_2_m0_decay_minute_v1",
    ).fetchall()

    assert (minute_count, summary.event_count) == (6, 2)
    assert beff_values == [(0.01,)]


def test_each_storm_restarts_from_zero():
    """Input: two magnetic-storm windows. Output: each M0 decay starts at zero."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    store_decay(connection, iter(event_minutes()), 0.01)

    starts = connection.execute("""
        SELECT storm_id,predicted_m0_delta_a_m
        FROM phase6_2_m0_decay_minute_v1
        WHERE time_us IN (
            SELECT MIN(time_us)
            FROM phase6_2_m0_decay_minute_v1
            GROUP BY storm_id
        )
        ORDER BY storm_id
    """).fetchall()

    assert starts == [("S1", 0.0), ("S2", 0.0)]


def test_summary_matches_event_errors():
    """Input: synthetic event results. Output: summary metrics match stored errors."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    _, summary = store_decay(connection, iter(event_minutes()), 0.01)
    errors = [
        row[0]
        for row in connection.execute(
            "SELECT m0_error_m FROM phase6_2_m0_error_event_v1",
        )
    ]

    assert summary.mean_error_m == sum(errors) / len(errors)
    assert summary.mean_absolute_error_m == sum(map(abs, errors)) / len(errors)
