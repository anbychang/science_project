"""Audit POD discontinuity metrics without changing quality results."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from satellite_orbit.calculation.pod.calc_pod_residual import centered_residuals

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
AUDIT_SOURCE_IDS = (1, 200, 400, 600, 800, 1000, 1200, 1400, 1600, 1685)
UTC = timezone.utc


def audit_residuals(connection, source_ids=AUDIT_SOURCE_IDS):
    """Input: SQLite connection and source IDs
    Output: {sample, position_curvature_m, velocity_residual_m_s}"""
    curvature_values = []
    velocity_values = []
    for source_id in source_ids:
        for residual in source_residuals(connection, source_id):
            curvature_values.append(residual["position_curvature_m"])
            velocity_values.append(residual["velocity_residual_m_s"])
    return {
        "sample_source_ids": tuple(source_ids),
        "position_curvature_m": distribution(curvature_values),
        "velocity_residual_m_s": distribution(velocity_values),
    }


def source_residuals(connection, source_id):
    """Input: SQLite connection and one source ID
    Output: iterable of continuous three-state residuals"""
    rows = connection.execute(
        """
        SELECT
            states.time_us, states.x_m, states.y_m, states.z_m,
            states.vx_m_s, states.vy_m_s, states.vz_m_s,
            states.source_id, provenance.sp3_frame_label
        FROM swarm_a_states AS states
        JOIN swarm_a_pod_quality AS quality USING (time_us)
        JOIN source_files USING (source_id)
        JOIN swarm_a_pod_source_provenance AS provenance USING (source_id)
        WHERE states.source_id = ? AND quality.is_usable = 1
        ORDER BY states.time_us
        """,
        (source_id,),
    )
    trio = []
    for row in rows:
        trio.append(state_from_row(row))
        if len(trio) < 3:
            continue
        residual = centered_residuals(trio)
        if residual is not None:
            yield residual
        trio.pop(0)


def state_from_row(row):
    """Input: one raw SQLite POD row with frame metadata
    Output: {time, frame, position_m, velocity_m_s, source_id}"""
    return {
        "time": datetime.fromtimestamp(row[0] / 1_000_000, UTC),
        "frame": row[8],
        "position_m": list(row[1:4]),
        "velocity_m_s": list(row[4:7]),
        "source_id": row[7],
    }


def distribution(values):
    """Input: non-empty numeric values
    Output: {count, median, mad, p99, p999, max}"""
    if not values:
        raise ValueError("Residual audit has no valid three-state windows.")
    ordered_values = sorted(values)
    center = median(ordered_values)
    deviations = [abs(value - center) for value in ordered_values]
    return {
        "count": len(ordered_values),
        "median": center,
        "mad": median(deviations),
        "p99": percentile(ordered_values, 0.99),
        "p999": percentile(ordered_values, 0.999),
        "max": ordered_values[-1],
    }


def percentile(sorted_values, fraction):
    """Input: sorted values and inclusive percentile fraction
    Output: nearest-rank value"""
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between zero and one.")
    index = round((len(sorted_values) - 1) * fraction)
    return sorted_values[index]


def main():
    """Input: python -m satellite_orbit.data.pod.prep_pod_maneuver_audit
    Output: fixed-sample read-only residual distribution"""
    with sqlite3.connect(DEFAULT_DATABASE) as connection:
        print(audit_residuals(connection))


if __name__ == "__main__":
    main()
