import sqlite3

from phases.phase6.code.prep_phase6_1_l2_minute_pairs import (
    create_tables,
    minute_label,
    store_complete_pairs,
)


def test_half_minute_rounds_to_next_minute():
    """Input: epochs around 30 seconds. Output: Phase 2-compatible minute labels."""
    assert minute_label(29_999_999) == 0
    assert minute_label(30_000_000) == 60_000_000


def test_only_complete_single_chunk_minutes_are_paired():
    """Input: complete and incomplete staging rows. Output: only one valid minute pair."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    connection.executemany(
        "INSERT INTO density_minute_stage VALUES (?,?,?,?,?)",
        [
            (0, 4.0e-12, 2, "a.zip", "a.zip"),
            (60_000_000, 2.0e-12, 1, "a.zip", "a.zip"),
        ],
    )
    connection.executemany(
        "INSERT INTO pod_minute_stage VALUES (?,?,?,?)",
        [
            (0, 1, 40_800_000.0, 6),
            (60_000_000, 1, 40_800_000.0, 6),
        ],
    )

    pair_count = store_complete_pairs(connection)
    row = connection.execute(
        "SELECT time_us,mean_semi_major_axis_m,rho_l2_kg_m3 "
        "FROM phase6_1_l2_pod_minute_pair_v1",
    ).fetchone()

    assert pair_count == 1
    assert row == (0, 6_800_000.0, 2.0e-12)
