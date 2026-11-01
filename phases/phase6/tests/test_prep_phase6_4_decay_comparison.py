import sqlite3

from phases.phase6.code.prep_phase6_4_decay_comparison import (
    ComparisonMinute,
    create_tables,
    store_comparison_minutes,
)


def test_covered_decline_continues_after_a_gap() -> None:
    """Input: two blocks. Output: covered curves keep earlier block endpoints."""
    minutes = [
        ComparisonMinute("S1", 0, 1, 1, 100.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.1),
        ComparisonMinute("S1", 60, 1, 1, 98.0, -2.0, 1.0, 1.0, -3.0, -4.0, 0.1),
        ComparisonMinute("S1", 180, 2, 1, 97.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.1),
        ComparisonMinute("S1", 240, 2, 1, 96.0, -1.0, 1.0, 1.0, -2.0, -3.0, 0.1),
    ]
    connection = sqlite3.connect(":memory:")
    create_tables(connection)

    counts = store_comparison_minutes(connection, iter(minutes))
    covered = connection.execute("""
        SELECT observed_covered_delta_a_m,predicted_m0_covered_delta_a_m,
               predicted_ridge_covered_delta_a_m
        FROM phase6_4_decay_comparison_minute_v1
        WHERE time_us = 240
    """).fetchone()

    assert counts == (4, 1, 2)
    assert covered == (-3.0, -5.0, -7.0)


def test_new_storm_restarts_all_covered_curves() -> None:
    """Input: two storms. Output: POD and both model curves restart at zero."""
    minutes = [
        ComparisonMinute("S1", 0, 1, 1, 100.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.1),
        ComparisonMinute("S1", 60, 1, 1, 99.0, -1.0, 1.0, 1.0, -2.0, -3.0, 0.1),
        ComparisonMinute("S2", 120, 2, 1, 90.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.1),
    ]
    connection = sqlite3.connect(":memory:")
    create_tables(connection)

    store_comparison_minutes(connection, iter(minutes))
    restart = connection.execute("""
        SELECT observed_covered_delta_a_m,predicted_m0_covered_delta_a_m,
               predicted_ridge_covered_delta_a_m
        FROM phase6_4_decay_comparison_minute_v1
        WHERE storm_id = 'S2'
    """).fetchone()

    assert restart == (0.0, 0.0, 0.0)
