"""Check that Phase 7 accepts a separate three-event external set."""

from phases.phase7.code import load_phase7_two_storms as phase7_sources


def test_load_events_accepts_three_complete_windows(monkeypatch) -> None:
    """Input: three frozen P2R IDs. Output: three complete event records."""
    selected_ids = (
        "S20221107T1720",
        "S20230227T1212",
        "S20230324T0521",
    )
    monkeypatch.setattr(phase7_sources, "STORM_IDS", selected_ids)

    events = phase7_sources.load_events()

    assert tuple(event.storm_id for event in events) == selected_ids
