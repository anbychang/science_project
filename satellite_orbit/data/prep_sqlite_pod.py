"""Write raw Swarm POD files into SQLite."""

from pathlib import Path

from satellite_orbit.data.load_swarm_pod import load_swarm_pod
from satellite_orbit.data.prep_sqlite_common import file_signature, time_to_us


def weather_block_time(time_utc):
    """Input: UTC datetime
    Output: start time of its 3-hour weather block"""
    start_hour = time_utc.hour - time_utc.hour % 3
    return time_utc.replace(hour=start_hour, minute=0, second=0, microsecond=0)


def pod_row(state, source_id):
    """Input: {ITRF state, source id}
    Output: one swarm_a_states table row"""
    position = state["position_m"]
    velocity = state["velocity_m_s"]
    return (
        time_to_us(state["time"]), float(position[0]), float(position[1]),
        float(position[2]), float(velocity[0]), float(velocity[1]),
        float(velocity[2]), time_to_us(weather_block_time(state["time"])), source_id,
    )


def prepare_source_file(connection, zip_path):
    """Input: {SQLite connection, POD ZIP path}
    Output: source id, or None when this file is already stored unchanged"""
    zip_path = Path(zip_path)
    signature = file_signature(zip_path)
    old_row = connection.execute(
        "SELECT source_id, signature FROM source_files WHERE file_name = ?",
        (zip_path.name,),
    ).fetchone()

    if old_row is not None and old_row[1] == signature:
        return None
    if old_row is None:
        cursor = connection.execute(
            "INSERT INTO source_files (file_name, signature) VALUES (?, ?)",
            (zip_path.name, signature),
        )
        return cursor.lastrowid

    source_id = old_row[0]
    connection.execute("DELETE FROM swarm_a_states WHERE source_id = ?", (source_id,))
    connection.execute(
        "UPDATE source_files SET signature = ? WHERE source_id = ?",
        (signature, source_id),
    )
    return source_id


def write_pod_file(connection, zip_path, weather_times):
    """Input: {SQLite connection, POD ZIP path, weather times}
    Output: number of stored orbit states"""
    source_id = prepare_source_file(connection, zip_path)
    if source_id is None:
        return 0

    rows = [
        pod_row(state, source_id)
        for state in load_swarm_pod(zip_path)
        if time_to_us(weather_block_time(state["time"])) in weather_times
    ]

    connection.executemany(
        "INSERT OR REPLACE INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def write_pod_folder(connection, pod_folder, weather_times):
    """Input: {SQLite connection, POD folder, weather times}
    Output: (changed POD files, stored orbit states)"""
    zip_paths = sorted(Path(pod_folder).rglob("*.ZIP"))
    changed_files = 0
    stored_states = 0

    for file_number, zip_path in enumerate(zip_paths, start=1):
        row_count = write_pod_file(connection, zip_path, weather_times)
        if row_count > 0:
            changed_files += 1
            stored_states += row_count
        if file_number % 100 == 0 or file_number == len(zip_paths):
            connection.commit()
            print(f"POD files: {file_number}/{len(zip_paths)}", flush=True)

    return changed_files, stored_states
