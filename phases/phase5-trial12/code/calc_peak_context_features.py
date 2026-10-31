"""Build whole-storm M1 peak and cumulative-excess features."""

import math
from collections import defaultdict
from statistics import median


MICROSECONDS_PER_DAY = 86_400_000_000


def build_feature_rows(triplets: list[dict]) -> list[dict]:
    """Input: [valid M1 orbit triplet]. Output: [four-feature peak-context orbit row]."""
    by_storm = defaultdict(list)
    for row in triplets:
        by_storm[row["storm_id"]].append(row)
    feature_rows = []
    for storm_id, unsorted in sorted(by_storm.items()):
        rows = sorted(unsorted, key=lambda row: row["grid_index"])
        log_values = [row["features"][0] for row in rows]
        event_median = median(log_values)
        peak_row = max(rows, key=lambda row: row["features"][0])
        peak_log_m1 = peak_row["features"][0]
        previous = None
        cumulative_excess = 0.0
        for row in rows:
            log_m1 = row["features"][0]
            if previous is not None and row["grid_index"] == previous["grid_index"] + 1:
                days = (row["time_us"] - previous["time_us"]) / MICROSECONDS_PER_DAY
                previous_excess = max(previous["features"][0] - event_median, 0.0)
                current_excess = max(log_m1 - event_median, 0.0)
                cumulative_excess += (previous_excess + current_excess) * days / 2
            days_from_peak = (row["time_us"] - peak_row["time_us"]) / MICROSECONDS_PER_DAY
            features = (log_m1, log_m1 - peak_log_m1,
                        days_from_peak, cumulative_excess)
            if not all(math.isfinite(value) for value in features):
                raise ValueError("Peak-context M1 features must be finite.")
            feature_rows.append({**row, "features": features})
            previous = row
    return feature_rows
