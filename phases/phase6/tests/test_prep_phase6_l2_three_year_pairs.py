from phases.phase6.code.prep_phase6_l2_three_year_pairs import (
    pair_day,
    source_day,
)
from phases.phase6.code.prep_phase6_quiet_audit import DensitySample, OrbitRow


def test_source_day_reads_dnsapod_name():
    """Input: one official DNSAPOD ZIP name. Output: its UTC source day."""
    day = source_day("SW_OPER_DNSAPOD_2__20240229T000000_20240229T235930_0301.ZIP")

    assert day.isoformat() == "2024-02-29"


def test_pair_day_keeps_nearest_density_within_one_minute():
    """Input: one orbit and two L2 samples. Output: nearest time-keyed pair."""
    orbit = OrbitRow(32_000_000, 0, 6_800_000.0)
    samples = [
        DensitySample(0, 1.0e-12, "day.zip"),
        DensitySample(30_000_000, 2.0e-12, "day.zip"),
    ]

    pairs = pair_day([(orbit, 4)], samples)

    assert len(pairs) == 1
    assert pairs[0].chunk_id == 4
    assert pairs[0].density.time_us == 30_000_000
