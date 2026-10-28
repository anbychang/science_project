"""Write raw Swarm POD files into SQLite."""

from pathlib import Path

from research_workspace.phases.phase0.code.data.database.prep_raw_identifiers import file_signature, time_to_us
from research_workspace.phases.phase0.code.data.pod.load_sp3_inventory import load_sp3_inventory
from research_workspace.phases.phase0.code.data.pod.load_swarm_pod import load_swarm_pod


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
        return connection.execute(
            "INSERT INTO source_files (file_name, signature) VALUES (?, ?)",
            (zip_path.name, signature),
        ).lastrowid

    raise ValueError(
        f"Raw POD source {zip_path.name} has a different signature. "
        "Rebuild a fresh database instead of replacing raw states."
    )


def write_pod_file(connection, zip_path, weather_times):
    """Input: {SQLite connection, POD ZIP path, weather times}
    Output: number of stored orbit states"""
    connection.execute("SAVEPOINT pod_import")
    try:
        source_id = prepare_source_file(connection, zip_path)
        if source_id is None:
            connection.execute("RELEASE pod_import")
            return 0

        states = load_swarm_pod(zip_path)
        inventory_count = load_sp3_inventory(zip_path)["epoch_count"]
        loaded_count = len(states)
        if loaded_count != inventory_count:
            raise ValueError(
                f"POD import count mismatch for {Path(zip_path).name}: "
                f"inventory={inventory_count}, loaded={loaded_count}."
            )

        rows = [
            pod_row(state, source_id)
            for state in states
            if time_to_us(weather_block_time(state["time"])) in weather_times
        ]
        kept_count = len(rows)
        changes_before_write = connection.total_changes
        connection.executemany(
            "INSERT OR IGNORE INTO swarm_a_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        inserted_count = connection.total_changes - changes_before_write
        if inserted_count != kept_count:
            raise ValueError(
                f"POD import count mismatch for {Path(zip_path).name}: "
                f"inventory={inventory_count}, loaded={loaded_count}, "
                f"kept={kept_count}, inserted={inserted_count}."
            )
    except Exception:
        connection.execute("ROLLBACK TO pod_import")
        connection.execute("RELEASE pod_import")
        raise
    connection.execute("RELEASE pod_import")
    return inserted_count


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
