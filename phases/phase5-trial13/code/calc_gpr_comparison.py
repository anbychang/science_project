"""Compare held-out density errors while keeping each storm as one unit."""

import math

import numpy as np


BOOTSTRAP_SEED = 20261031
BOOTSTRAP_SAMPLES = 10000


def event_sums(samples: list[tuple]) -> dict:
    """Input: [(grid_index, L2 kg/m3, estimate kg/m3)]. Output: event error sums."""
    if not samples:
        raise ValueError("Each storm needs at least one scored orbit.")
    ordered = sorted(samples)
    grids = np.array([row[0] for row in ordered])
    actual = np.array([row[1] for row in ordered])
    estimate = np.array([row[2] for row in ordered])
    if np.any(actual <= 0) or np.any(estimate <= 0):
        raise ValueError("Densities must be positive.")
    errors = np.log(actual / estimate)
    if not np.isfinite(errors).all():
        raise ValueError("Log-density errors must be finite.")
    consecutive = np.diff(grids) == 1
    changes = np.diff(errors)[consecutive]
    return {
        "count": len(errors),
        "total_sse": float(np.sum(errors ** 2)),
        "shape_sse": float(np.sum((errors - np.mean(errors)) ** 2)),
        "change_sse": float(np.sum(changes ** 2)),
        "change_count": len(changes),
    }


def rmse(events: list[dict], metric: str) -> float:
    """Input: [event error sums], metric name. Output: pooled log-density RMSE."""
    count_field = "change_count" if metric == "change" else "count"
    count = sum(event[count_field] for event in events)
    if count == 0:
        raise ValueError("Metric needs at least one observation.")
    return math.sqrt(sum(event[f"{metric}_sse"] for event in events) / count)


def bootstrap_delta(pairs: list[tuple[dict, dict]], metric: str) -> tuple[float, float]:
    """Input: [(baseline event, GP event)], metric. Output: 95% storm-bootstrap CI for GP minus M1 RMSE."""
    count_field = "change_count" if metric == "change" else "count"
    baseline_sse = np.array([pair[0][f"{metric}_sse"] for pair in pairs])
    gp_sse = np.array([pair[1][f"{metric}_sse"] for pair in pairs])
    counts = np.array([pair[0][count_field] for pair in pairs])
    if any(pair[0][count_field] != pair[1][count_field] for pair in pairs):
        raise ValueError("Baseline and GP must use the same scored orbits.")
    indices = np.random.default_rng(BOOTSTRAP_SEED).integers(
        0, len(pairs), size=(BOOTSTRAP_SAMPLES, len(pairs)))
    totals = counts[indices].sum(axis=1)
    if np.any(totals == 0):
        raise ValueError("A bootstrap sample has no scored observations.")
    differences = (np.sqrt(gp_sse[indices].sum(axis=1) / totals)
                   - np.sqrt(baseline_sse[indices].sum(axis=1) / totals))
    lower, upper = np.quantile(differences, [0.025, 0.975])
    return float(lower), float(upper)
