"""Report semi-major-axis distributions around SP3 frame transitions."""

import sqlite3
from pathlib import Path
from statistics import median

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
SOURCES_PER_SIDE = 3


def find_frame_transitions(connection):
    """Input: SQLite connection with ordered source_files rows
    Output: [{old_source_id, new_source_id, old_frame, new_frame}, ...]"""
    rows = connection.execute(
        "SELECT source_id, sp3_frame_label "
        "FROM swarm_a_pod_source_provenance ORDER BY source_id"
    )
    previous = None
    transitions = []
    for source_id, frame_label in rows:
        if previous is not None and frame_label != previous[1]:
            transitions.append(
                {
                    "old_source_id": previous[0],
                    "new_source_id": source_id,
                    "old_frame": previous[1],
                    "new_frame": frame_label,
                }
            )
        previous = (source_id, frame_label)
    return transitions


def median_semi_major_axis(connection, first_source_id, last_source_id):
    """Input: inclusive source-id range
    Output: {row_count, median_semi_major_axis_m}"""
    values = [
        row[0]
        for row in connection.execute(
            """
            SELECT elements.semi_major_axis_m
            FROM swarm_a_states AS states
            JOIN swarm_a_orbital_elements AS elements USING (time_us)
            JOIN swarm_a_pod_quality AS quality USING (time_us)
            WHERE states.source_id BETWEEN ? AND ?
              AND quality.is_usable = 1
              AND elements.semi_major_axis_m IS NOT NULL
            ORDER BY elements.semi_major_axis_m
            """,
            (first_source_id, last_source_id),
        )
    ]
    if not values:
        raise ValueError("Frame-transition sample has no usable orbital elements.")
    return {"row_count": len(values), "median_semi_major_axis_m": median(values)}


def transition_report(connection, sources_per_side=SOURCES_PER_SIDE):
    """Input: SQLite connection and positive sample size
    Output: [{transition, before, after, median_difference_m}, ...]"""
    if sources_per_side < 1:
        raise ValueError("sources_per_side must be positive.")
    reports = []
    for transition in find_frame_transitions(connection):
        before = median_semi_major_axis(
            connection,
            transition["old_source_id"] - sources_per_side + 1,
            transition["old_source_id"],
        )
        after = median_semi_major_axis(
            connection,
            transition["new_source_id"],
            transition["new_source_id"] + sources_per_side - 1,
        )
        reports.append(
            {
                **transition,
                "before": before,
                "after": after,
                "median_difference_m": (
                    after["median_semi_major_axis_m"]
                    - before["median_semi_major_axis_m"]
                ),
            }
        )
    return reports


def main():
    """Input: python -m satellite_orbit.data.pod.prep_pod_frame_transition_report
    Output: one read-only frame-transition report per line"""
    with sqlite3.connect(DEFAULT_DATABASE) as connection:
        for report in transition_report(connection):
            print(report)


if __name__ == "__main__":
    main()
