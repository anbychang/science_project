import sqlite3

from phases.phase6.code.calc_phase6_3_ridge_decay import (
    JoinedMinute,
    create_tables,
    store_decay,
)


def event_minutes() -> list[JoinedMinute]:
    """Input: none. Output: two three-minute synthetic storm windows."""
    rows = []
    for storm_index, storm_id in enumerate(("S1", "S2")):
        for minute_index in range(3):
            rows.append(JoinedMinute(
                storm_id=storm_id,
                time_us=(storm_index * 10 + minute_index) * 60_000_000,
                chunk_id=1,
                semi_major_axis_m=6_800_000.0 - minute_index,
                ridge_density_kg_m3=1.0e-12,
            ))
    return rows


def test_uses_fixed_beff() -> None:
    """Input: synthetic storms. Output: stored rows retain the supplied B_eff."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    minute_count, summary = store_decay(connection, iter(event_minutes()), 0.01)
    values = connection.execute(
        "SELECT DISTINCT b_eff_m2_kg FROM phase6_3_ridge_decay_minute_v1",
    ).fetchall()

    assert (minute_count, summary.event_count) == (6, 2)
    assert values == [(0.01,)]


def test_each_storm_restarts_from_zero() -> None:
    """Input: two storms. Output: each Ridge decay begins at zero."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    store_decay(connection, iter(event_minutes()), 0.01)

    starts = connection.execute("""
        SELECT storm_id,predicted_ridge_delta_a_m
        FROM phase6_3_ridge_decay_minute_v1
        WHERE time_us IN (
            SELECT MIN(time_us)
            FROM phase6_3_ridge_decay_minute_v1
            GROUP BY storm_id
        )
        ORDER BY storm_id
    """).fetchall()

    assert starts == [("S1", 0.0), ("S2", 0.0)]


def test_time_gap_starts_a_new_block() -> None:
    """Input: one storm with a missing minute. Output: no integration crosses gap."""
    rows = [
        JoinedMinute("S1", 0, 1, 6_800_000.0, 1.0e-12),
        JoinedMinute("S1", 60_000_000, 1, 6_799_999.0, 1.0e-12),
        JoinedMinute("S1", 180_000_000, 1, 6_799_998.0, 1.0e-12),
        JoinedMinute("S1", 240_000_000, 1, 6_799_997.0, 1.0e-12),
    ]
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    store_decay(connection, iter(rows), 0.01)

    restart = connection.execute("""
        SELECT predicted_ridge_delta_a_m
        FROM phase6_3_ridge_decay_minute_v1
        WHERE time_us = 180000000
    """).fetchone()
    block_count = connection.execute(
        "SELECT block_count FROM phase6_3_ridge_decay_event_v1",
    ).fetchone()

    assert restart == (0.0,)
    assert block_count == (2,)


def test_summary_matches_event_errors() -> None:
    """Input: synthetic storms. Output: summary matches stored event errors."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    _, summary = store_decay(connection, iter(event_minutes()), 0.01)
    errors = [
        row[0]
        for row in connection.execute(
            "SELECT ridge_error_m FROM phase6_3_ridge_decay_event_v1",
        )
    ]

    assert summary.mean_error_m == sum(errors) / len(errors)
    assert summary.mean_absolute_error_m == sum(map(abs, errors)) / len(errors)
