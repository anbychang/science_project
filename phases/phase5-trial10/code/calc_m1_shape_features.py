"""Build three M1-only features at a valid orbit anchor."""

import math
from itertools import groupby


def shape_features(previous: dict, current: dict, following: dict) -> tuple[float, ...]:
    """Input: three consecutive {rho_m1_kg_m3} anchors. Output: [log level, past slope, centered curvature]."""
    densities = [row["rho_m1_kg_m3"] for row in (previous, current, following)]
    if any(density <= 0 or not math.isfinite(density) for density in densities):
        raise ValueError("M1 densities must be positive and finite.")
    before, now, after = (math.log(density) for density in densities)
    return now, now - before, after - 2 * now + before


def build_triplets(anchors: list[dict]) -> list[dict]:
    """Input: [{storm_id, grid_index, M1, L2}, ...]. Output: valid center-orbit training rows."""
    triplets = []
    ordered = sorted(anchors, key=lambda row: (row["storm_id"], row["grid_index"]))
    for storm_id, storm_rows in groupby(ordered, key=lambda row: row["storm_id"]):
        rows = list(storm_rows)
        for previous, current, following in zip(rows, rows[1:], rows[2:]):
            if (current["grid_index"] != previous["grid_index"] + 1
                    or following["grid_index"] != current["grid_index"] + 1):
                continue
            if current["rho_l2_kg_m3"] <= 0:
                raise ValueError("L2 training labels must be positive.")
            triplets.append({
                "storm_id": storm_id,
                "time_us": current["time_us"],
                "grid_index": current["grid_index"],
                "rho_m1_kg_m3": current["rho_m1_kg_m3"],
                "rho_l2_kg_m3": current["rho_l2_kg_m3"],
                "features": shape_features(previous, current, following),
                "target_log_residual": math.log(
                    current["rho_l2_kg_m3"] / current["rho_m1_kg_m3"]),
            })
    return triplets
