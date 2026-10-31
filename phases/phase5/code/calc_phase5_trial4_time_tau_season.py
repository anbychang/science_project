"""Build time, Trial4 tau, and seasonal GPR features for Phase5 Trial4."""

from datetime import datetime, timezone
import math

import numpy as np


FEATURE_NAMES = (
    "relative_time_hours",
    "tau_hours",
    "season_sin",
    "season_cos",
)
MICROSECONDS_PER_HOUR = 3_600_000_000


def storm_event_time_us(storm_id: str) -> int:
    """Input: storm ID SYYYYMMDDTHHMM. Output: storm event UTC epoch in microseconds."""
    try:
        event_time = datetime.strptime(storm_id[1:], "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError(f"Invalid Trial4 storm ID: {storm_id}") from error
    return int(event_time.timestamp() * 1_000_000)


def seasonal_coordinates(time_us: int) -> tuple[float, float]:
    """Input: UTC epoch in microseconds. Output: cyclic annual sine and cosine coordinates."""
    instant = datetime.fromtimestamp(time_us / 1_000_000, tz=timezone.utc)
    year_start = datetime(instant.year, 1, 1, tzinfo=timezone.utc)
    next_year = datetime(instant.year + 1, 1, 1, tzinfo=timezone.utc)
    fraction = (instant - year_start).total_seconds() / (next_year - year_start).total_seconds()
    angle = 2.0 * math.pi * fraction
    return math.sin(angle), math.cos(angle)


def feature_matrix(rows: list[dict]) -> np.ndarray:
    """Input: [{storm_id, time_us, tau_hours}]. Output: [anchors x time/tau/season features]."""
    values = []
    for row in rows:
        season_sin, season_cos = seasonal_coordinates(row["time_us"])
        relative_time_hours = (
            row["time_us"] - storm_event_time_us(row["storm_id"])
        ) / MICROSECONDS_PER_HOUR
        values.append([relative_time_hours, row["tau_hours"], season_sin, season_cos])
    features = np.array(values)
    if not np.isfinite(features).all():
        raise ValueError("Trial4 time/tau/season features must be finite.")
    return features
