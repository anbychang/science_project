"""Check complete-orbit event merging without loading mission data."""

from satellite_orbit.phase2.prep_23_full_orbit import merge_orbit_windows


def candidate(storm_id: str, depth: int, first_orbit: int, count: int = 3) -> dict:
    """Input: event identity, SYM-H nT, first orbit and count. Output: test window."""
    orbits = [(index * 10, (index + 1) * 10, index, 1.0, 1)
              for index in range(first_orbit, first_orbit + count)]
    return {"storm_id": storm_id, "t0_us": first_orbit * 10 + 1,
            "symh_min_nt": depth, "compound": 0, "n_minima": 1,
            "orbits": orbits}


def test_overlapping_orbit_windows_merge_to_the_deeper_storm() -> None:
    """Input: overlapping windows. Output: one union keyed by deeper t0."""
    merged = merge_orbit_windows([candidate("A", -110, 0), candidate("B", -150, 2)])
    assert [(event["storm_id"], len(event["orbits"])) for event in merged] == [("B", 5)]


def test_touching_orbit_windows_remain_independent() -> None:
    """Input: adjacent non-overlapping windows. Output: two separate events."""
    merged = merge_orbit_windows([candidate("A", -110, 0), candidate("B", -150, 3)])
    assert [event["storm_id"] for event in merged] == ["A", "B"]


def test_connected_overlap_merges_all_members() -> None:
    """Input: overlap chain. Output: one unique orbit union."""
    merged = merge_orbit_windows([
        candidate("A", -110, 0), candidate("B", -150, 2), candidate("C", -120, 4)
    ])
    assert [orbit[2] for orbit in merged[0]["orbits"]] == list(range(7))
