import math
import sqlite3

import pytest

from phases.phase6.code.calc_phase6_1_beff import (
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    MINUTE_US,
    MinutePair,
    create_tables,
    finish_fit,
    store_integral,
)


def exact_minute_pairs(beta_eff: float) -> list[MinutePair]:
    """Input: positive B_eff. Output: exact minute pairs for the trapezoid estimator."""
    pairs = []
    semi_major_axis_m = 6_800_000.0
    density_kg_m3 = 2.0e-12
    for index in range(5):
        pairs.append(MinutePair(
            time_us=index * MINUTE_US,
            chunk_id=1,
            semi_major_axis_m=semi_major_axis_m,
            density_kg_m3=density_kg_m3,
        ))
        next_a_m = semi_major_axis_m
        for _ in range(6):
            next_a_m = semi_major_axis_m - beta_eff * density_kg_m3 * math.sqrt(
                EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * (semi_major_axis_m + next_a_m) / 2,
            ) * 60.0
        semi_major_axis_m = next_a_m
    return pairs


def test_minute_fit_recovers_one_beff():
    """Input: exact P6.1 minute curve. Output: fitted global B_eff matches source."""
    connection = sqlite3.connect(":memory:")
    create_tables(connection)

    _, _, _, numerator, denominator = store_integral(
        connection,
        iter(exact_minute_pairs(0.01)),
    )
    beta_eff = numerator / denominator
    _, rmse_m, _ = finish_fit(connection, beta_eff)

    assert beta_eff == pytest.approx(0.01, rel=1.0e-8)
    assert rmse_m < 1.0e-8


def test_missing_minute_starts_a_new_block():
    """Input: minute pairs with one gap. Output: no integration crosses the gap."""
    pairs = exact_minute_pairs(0.01)
    shifted = [
        MinutePair(
            time_us=pair.time_us + 10 * MINUTE_US,
            chunk_id=pair.chunk_id,
            semi_major_axis_m=pair.semi_major_axis_m,
            density_kg_m3=pair.density_kg_m3,
        )
        for pair in pairs
    ]
    connection = sqlite3.connect(":memory:")
    create_tables(connection)

    _, point_count, block_count, _, _ = store_integral(
        connection,
        iter([*pairs, *shifted]),
    )

    assert point_count == 8
    assert block_count == 2
