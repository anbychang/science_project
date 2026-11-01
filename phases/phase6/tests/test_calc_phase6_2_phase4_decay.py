import sqlite3

import pytest

from phases.phase6.code.calc_phase6_2_phase4_decay import (
    JoinedMinute,
    create_tables,
    store_decay,
)


def event_minutes() -> list[JoinedMinute]:
    """Input: none. Output: two three-minute continuous synthetic events."""
    rows = []
    for storm_index, storm_id in enumerate(("S1", "S2")):
        for minute_index in range(3):
            rows.append(JoinedMinute(
                storm_id=storm_id,
                time_us=(storm_index * 10 + minute_index) * 60_000_000,
                chunk_id=1,
                semi_major_axis_m=6_800_000.0 - minute_index,
                l2_phase_density_kg_m3=2.0e-12,
                phase4_density_kg_m3=1.0e-12,
            ))
    return rows


def test_fixed_beff_is_applied_without_refit():
    """Input: two synthetic events and fixed B_eff. Output: Phase 4 decay uses that value."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)

    minute_count, event_count = store_decay(connection, iter(event_minutes()), 0.01)
    beff_values = connection.execute(
        "SELECT DISTINCT b_eff_m2_kg FROM phase6_2_phase4_decay_minute_v1",
    ).fetchall()

    assert (minute_count, event_count) == (6, 2)
    assert beff_values == [(0.01,)]


def test_phase4_half_density_produces_half_l2_decay():
    """Input: Phase 4 density at half L2. Output: endpoint decay is exactly one half."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    store_decay(connection, iter(event_minutes()), 0.01)

    l2_delta, phase4_delta = connection.execute("""
        SELECT predicted_l2_covered_delta_a_m,predicted_phase4_covered_delta_a_m
        FROM phase6_2_phase4_decay_event_v1
        WHERE storm_id='S1'
    """).fetchone()

    assert phase4_delta == pytest.approx(l2_delta / 2.0)


def test_each_storm_restarts_from_zero():
    """Input: two magnetic-storm windows. Output: each storm starts at zero decay."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    store_decay(connection, iter(event_minutes()), 0.01)

    starts = connection.execute("""
        SELECT storm_id,predicted_phase4_delta_a_m
        FROM phase6_2_phase4_decay_minute_v1
        WHERE time_us IN (
            SELECT MIN(time_us)
            FROM phase6_2_phase4_decay_minute_v1
            GROUP BY storm_id
        )
        ORDER BY storm_id
    """).fetchall()

    assert starts == [("S1", 0.0), ("S2", 0.0)]
