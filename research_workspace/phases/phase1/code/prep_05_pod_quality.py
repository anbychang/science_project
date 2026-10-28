"""Mark basic POD quality and safe calculation chunks without changing raw data."""

import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path

from research_workspace.phases.phase0.code.data.database.prep_raw_schema import connect_database

DEFAULT_DATABASE = Path("research_workspace/phases/phase1/data/sqlite/swarm_a_data.sqlite")
BATCH_SIZE = 10_000
MICROSECONDS_PER_SECOND = 1_000_000
QUALITY_COLUMNS = {"time_us", "is_usable", "rejection_reason", "chunk_id"}
UTC = timezone.utc
OFFICIAL_SWARM_A_ORBIT_EVENTS = (
    (
        "SWA_ORBIT_CONTROL_2022-01-13",
        "orbit_control_manoeuvre",
        int(datetime(2022, 1, 13, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
        int(datetime(2022, 1, 14, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
    ),
    (
        "SWA_C_ORBIT_RAISE_2022",
        "orbit_raise_campaign",
        int(datetime(2022, 5, 3, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
        int(datetime(2022, 7, 9, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
    ),
    (
        "SWA_CAM_2023-01-06",
        "collision_avoidance_manoeuvre",
        int(datetime(2023, 1, 6, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
        int(datetime(2023, 1, 7, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
    ),
    (
        "SWA_C_ORBIT_RAISE_2023_PHASE_II",
        "orbit_raise_campaign",
        int(datetime(2023, 4, 26, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
        int(datetime(2023, 6, 8, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
    ),
    (
        "SWA_C_ORBIT_RAISE_2026",
        "orbit_raise_campaign",
        int(datetime(2026, 7, 21, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
        int(datetime(2026, 8, 1, tzinfo=UTC).timestamp() * MICROSECONDS_PER_SECOND),
    ),
)
EVENT_REJECTION_REASONS = {
    "orbit_control_manoeuvre": "official_orbit_control_manoeuvre",
    "orbit_raise_campaign": "planned_orbit_raise_campaign",
    "collision_avoidance_manoeuvre": "official_collision_avoidance_manoeuvre",
}
QUALITY_POLICY_VERSION = "official_swarm_a_orbit_event_exclusion_v1"
DOWNSTREAM_DERIVED_TABLES = (
    "swarm_a_mean_orbital_elements",
    "swarm_a_orbit_10min",
    "swarm_a_orbit_decay_10min",
    "swarm_a_analysis_10min",
)


def official_orbit_event_at(time_us):
    """Input: Unix microseconds
    Output: (official event ID, event kind), or None outside known events"""
    for event_id, event_kind, start_time_us, stop_time_us in OFFICIAL_SWARM_A_ORBIT_EVENTS:
        if start_time_us <= time_us < stop_time_us:
            return event_id, event_kind
    return None


def planned_orbit_raise_campaign_id(time_us):
    """Input: Unix microseconds
    Output: official campaign ID, or None outside campaign intervals"""
    event = official_orbit_event_at(time_us)
    if event is None or event[1] != "orbit_raise_campaign":
        return None
    return event[0]


def create_quality_table(connection):
    """Input: SQLite connection
    Output: POD quality table exists"""
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(swarm_a_pod_quality)")
    }
    if existing_columns and existing_columns != QUALITY_COLUMNS:
        connection.execute("DROP TABLE swarm_a_pod_quality")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_a_pod_quality (
            time_us INTEGER PRIMARY KEY,
            is_usable INTEGER NOT NULL,
            rejection_reason TEXT,
            chunk_id INTEGER,
            FOREIGN KEY (time_us) REFERENCES swarm_a_states(time_us)
        )
        """
    )


def require_no_downstream_output(connection):
    """Input: SQLite connection
    Output: quality rebuild is safe to start without stale derived rows"""
    populated_tables = []
    for table_name in DOWNSTREAM_DERIVED_TABLES:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        if table_exists and connection.execute(
            f"SELECT 1 FROM {table_name} LIMIT 1"
        ).fetchone():
            populated_tables.append(table_name)
    if populated_tables:
        raise ValueError(
            "POD quality rebuild would invalidate downstream output: "
            f"{', '.join(populated_tables)}. "
            "Use a new target with write_phase1_rebuild."
        )


def write_quality_metadata(connection):
    """Input: SQLite connection
    Output: reproducible official-event quality policy metadata"""
    event_rows = [
        {
            "event_id": event_id,
            "event_kind": event_kind,
            "start_time_us": start_time_us,
            "stop_time_us": stop_time_us,
        }
        for event_id, event_kind, start_time_us, stop_time_us in OFFICIAL_SWARM_A_ORBIT_EVENTS
    ]
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("p1_4_quality_policy_version", QUALITY_POLICY_VERSION),
            ("p1_4_official_orbit_events", json.dumps(event_rows, sort_keys=True)),
        ],
    )


def quality_row(row, previous_time_us):
    """Input: one POD row and the previous time
    Output: (time_us, is_usable, rejection_reason, chunk_id)"""
    time_us = row["time_us"]
    orbit_event = official_orbit_event_at(time_us)
    if orbit_event is not None:
        return time_us, 0, EVENT_REJECTION_REASONS[orbit_event[1]], None
    state_values = [
        row["x_m"],
        row["y_m"],
        row["z_m"],
        row["vx_m_s"],
        row["vy_m_s"],
        row["vz_m_s"],
    ]

    if previous_time_us is not None and time_us <= previous_time_us:
        return time_us, 0, "time_not_increasing", None
    if not all(value is not None and isfinite(value) for value in state_values):
        return time_us, 0, "non_finite_state", None
    if row["orbital_rejection_reason"] is not None:
        return time_us, 0, "invalid_orbital_energy", None
    if row["semi_major_axis_m"] is None:
        return time_us, 0, "missing_orbital_element", None
    if not isfinite(row["semi_major_axis_m"]) or row["semi_major_axis_m"] <= 0.0:
        return time_us, 0, "invalid_orbital_element", None
    return time_us, 1, None, None


def quality_source_rows(connection, after_time_us=None):
    """Input: SQLite connection
    Output: POD rows with their orbital-element result"""
    return connection.execute(
        """
        SELECT
            state.time_us,
            state.x_m,
            state.y_m,
            state.z_m,
            state.vx_m_s,
            state.vy_m_s,
            state.vz_m_s,
            state.source_id,
            source.file_name,
            provenance.sp3_frame_label,
            provenance.cadence_s,
            element.semi_major_axis_m,
            element.rejection_reason AS orbital_rejection_reason
        FROM swarm_a_states AS state
        LEFT JOIN source_files AS source
            ON source.source_id = state.source_id
        LEFT JOIN swarm_a_pod_source_provenance AS provenance
            ON provenance.source_id = state.source_id
        LEFT JOIN swarm_a_orbital_elements AS element
            ON element.time_us = state.time_us
        WHERE state.time_us > COALESCE(?, -1)
        ORDER BY state.time_us
        """
        ,
        (after_time_us,),
    )


def product_stream(file_name):
    """Input: source ZIP file name
    Output: stable product stream before the ``__`` separator or None"""
    if file_name is None:
        return None
    stream, separator, _ = file_name.partition("__")
    if not separator or not stream:
        return None
    return stream


def row_provenance(row):
    """Input: POD row joined to its source-file metadata
    Output: {stream, frame, cadence_us} or None when chunk safety is unknown"""
    stream = product_stream(row["file_name"])
    frame = row["sp3_frame_label"]
    cadence_s = row["cadence_s"]
    if (
        stream is None
        or frame is None
        or not frame
        or cadence_s is None
        or not isfinite(cadence_s)
        or cadence_s <= 0
    ):
        return None
    cadence_us = round(cadence_s * MICROSECONDS_PER_SECOND)
    if cadence_us <= 0:
        return None
    return {"stream": stream, "frame": frame, "cadence_us": cadence_us}


def starts_new_chunk(row, previous_quality_row):
    """Input: current and previous POD quality context
    Output: True when a new safe calculation chunk starts"""
    if previous_quality_row is None:
        return True
    if not previous_quality_row["is_usable"]:
        return True
    current_provenance = row_provenance(row)
    previous_provenance = previous_quality_row["provenance"]
    if current_provenance is None or previous_provenance is None:
        return True
    if current_provenance != previous_provenance:
        return True
    return row["time_us"] - previous_quality_row["time_us"] != current_provenance["cadence_us"]


def write_pod_quality(database_path=DEFAULT_DATABASE, resume=False):
    """Input: SQLite database path
    Output: {raw_rows, usable_rows, chunk_count, rejection_counts}"""
    database_path = Path(database_path)
    raw_rows = 0
    usable_rows = 0
    rejection_counts = {}

    with closing(connect_database(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        require_no_downstream_output(connection)
        create_quality_table(connection)
        previous_quality_row, chunk_id = resume_context(connection) if resume else (None, 0)
        if not resume:
            connection.execute("DELETE FROM swarm_a_pod_quality")
        source_rows = quality_source_rows(
            connection,
            None if previous_quality_row is None else previous_quality_row["time_us"],
        )

        try:
            while True:
                batch = source_rows.fetchmany(BATCH_SIZE)
                if not batch:
                    break

                quality_rows = []
                for row in batch:
                    time_us = row["time_us"]
                    result = quality_row(
                        row,
                        (
                            None
                            if previous_quality_row is None
                            else previous_quality_row["time_us"]
                        ),
                    )
                    is_usable = result[1] == 1
                    if is_usable:
                        if starts_new_chunk(row, previous_quality_row):
                            chunk_id += 1
                        result = result[:3] + (chunk_id,)
                    quality_rows.append(result)
                    previous_quality_row = {
                        "time_us": time_us,
                        "is_usable": is_usable,
                        "provenance": row_provenance(row),
                    }
                    raw_rows += 1
                    if is_usable:
                        usable_rows += 1
                    else:
                        rejection_reason = result[2]
                        rejection_counts[rejection_reason] = (
                            rejection_counts.get(rejection_reason, 0) + 1
                        )

                connection.executemany(
                    "INSERT OR REPLACE INTO swarm_a_pod_quality VALUES (?, ?, ?, ?)",
                    quality_rows,
                )
                connection.commit()
        finally:
            source_rows.close()
        write_quality_metadata(connection)
        connection.commit()

    return {
        "raw_rows": raw_rows,
        "usable_rows": usable_rows,
        "chunk_count": chunk_id,
        "rejection_counts": rejection_counts,
    }


def resume_context(connection):
    """Input: SQLite connection with partial quality output
    Output: (previous quality context, last chunk ID)"""
    last_quality = connection.execute(
        """
        SELECT time_us, is_usable, chunk_id
        FROM swarm_a_pod_quality
        ORDER BY time_us DESC LIMIT 1
        """
    ).fetchone()
    if last_quality is None:
        return None, 0
    connection.row_factory = sqlite3.Row
    last_row = quality_source_rows(connection, last_quality[0] - 1).fetchone()
    if last_row is None or last_row["time_us"] != last_quality[0]:
        raise ValueError("Cannot resume without the last raw POD state.")
    return (
        {
            "time_us": last_quality[0],
            "is_usable": last_quality[1] == 1,
            "provenance": row_provenance(last_row),
        },
        last_quality[2] or 0,
    )


def main():
    """Input: python -m research_workspace.phases.phase1.code.prep_05_pod_quality
    Output: POD quality summary"""
    result = write_pod_quality(resume="--resume" in sys.argv)
    print(f"POD rows checked: {result['raw_rows']}")
    print(f"Usable POD rows: {result['usable_rows']}")
    print(f"Safe calculation chunks: {result['chunk_count']}")
    for reason, count in result["rejection_counts"].items():
        print(f"{reason}: {count}")


if __name__ == "__main__":
    main()
