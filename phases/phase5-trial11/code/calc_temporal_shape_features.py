"""Build event-context M1 features without using L2 values."""

import math
from collections import defaultdict
from statistics import median


MICROSECONDS_PER_DAY = 86_400_000_000


def build_feature_rows(triplets: list[dict], event_times: dict) -> list[dict]:
    """Input: [valid M1 orbit triplet], {storm: t0_us}. Output: [four-feature orbit row]."""
    by_storm = defaultdict(list)
    for row in triplets:
        by_storm[row["storm_id"]].append(row)
    if set(by_storm) != set(event_times):
        raise ValueError("Event times must cover every storm exactly.")
    feature_rows = []
    for storm_id, rows in sorted(by_storm.items()):
        event_median = median(row["features"][0] for row in rows)
        for row in rows:
            log_m1, past_change, curvature = row["features"]
            centered_slope = past_change + curvature / 2
            days_from_t0 = (row["time_us"] - event_times[storm_id]) / MICROSECONDS_PER_DAY
            features = (days_from_t0, log_m1, log_m1 - event_median, centered_slope)
            if not all(math.isfinite(value) for value in features):
                raise ValueError("Temporal M1 features must be finite.")
            feature_rows.append({**row, "features": features})
    return feature_rows
