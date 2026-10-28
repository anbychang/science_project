"""Tests for Phase 2R DNSAPOD day selection."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from phases.phase2r.code.down_2r4_dnsapod import required_days


def utc_us(stamp: str) -> int:
    """Input: UTC ISO stamp. Output: Unix microseconds."""
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return int(moment.timestamp() * 1_000_000)


def test_required_days_uses_actual_event_minutes(tmp_path):
    """Input: event minutes crossing midnight. Output: both UTC source days."""
    database_path = tmp_path / "events.sqlite"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE storm_minute_feature_v5 (source_time_us INTEGER)")
        connection.executemany(
            "INSERT INTO storm_minute_feature_v5 VALUES (?)",
            (
                (utc_us("2015-03-17T23:59:00Z"),),
                (utc_us("2015-03-18T00:00:00Z"),),
            ),
        )
        connection.commit()
    assert required_days(database_path) == {"20150317", "20150318"}
