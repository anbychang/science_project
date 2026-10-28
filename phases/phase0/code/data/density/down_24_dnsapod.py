"""Complete DNSAPOD day files for the current Phase 2 storm windows."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from phases.phase0.code.data.density.down_swarm_density_pod import (
    OUTPUT_FOLDER,
    SOURCE_SERVER,
    download_source_file,
    list_pod_source_files,
    select_source_files,
    sha256_file,
)
from phases.phase0.code.data.geomagnetic.down_gfz_ap import write_new


INPUT_DB = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_3_v2.sqlite")
MANIFEST_NAME = "manifest_p2_4_v2.json"
MICROSECONDS_PER_SECOND = 1_000_000


def required_days(database_path: Path) -> set[str]:
    """Input: P2.3 SQLite. Output: UTC days intersecting current storm windows."""
    with closing(sqlite3.connect(f"file:{database_path.resolve().as_posix()}?mode=ro", uri=True)) as db:
        windows = db.execute(
            "SELECT window_start_time_us, window_end_time_us FROM storm_event_v2"
        ).fetchall()
    if not windows:
        raise ValueError("P2.3 has no storm windows.")
    days = set()
    for start_us, end_us in windows:
        day = datetime.fromtimestamp(start_us / MICROSECONDS_PER_SECOND, timezone.utc).date()
        while datetime.combine(day, time.min, timezone.utc).timestamp() * MICROSECONDS_PER_SECOND < end_us:
            days.add(day.strftime("%Y%m%d"))
            day += timedelta(days=1)
    return days


def download_current_windows(database_path: Path = INPUT_DB,
                             output_folder: Path = OUTPUT_FOLDER) -> dict:
    """Input: P2.3 SQLite and ZIP folder. Output: verified ZIPs and new manifest."""
    database_path = Path(database_path)
    output_folder = Path(output_folder)
    manifest_path = output_folder / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    database_hash = sha256_file(database_path)
    source_files = select_source_files(list_pod_source_files(), required_days(database_path))
    output_folder.mkdir(parents=True, exist_ok=True)
    records = []
    for index, source_file in enumerate(source_files, start=1):
        local_path = download_source_file(source_file, output_folder)
        records.append({
            "name": local_path.name,
            "source_path": source_file["path"],
            "source_mtime_utc": datetime.fromtimestamp(
                source_file["mtime"], timezone.utc
            ).isoformat(),
            "local_mtime_utc": datetime.fromtimestamp(
                local_path.stat().st_mtime, timezone.utc
            ).isoformat(),
            "size_bytes": source_file["size"],
            "sha256": sha256_file(local_path),
        })
        print(f"[{index}/{len(source_files)}] {local_path.name}", flush=True)
    if sha256_file(database_path) != database_hash:
        raise ValueError("P2.3 changed while DNSAPOD files were checked.")
    manifest = {
        "source": SOURCE_SERVER,
        "collection": "SW_OPER_DNSAPOD_2_",
        "storm_database": database_path.as_posix(),
        "storm_database_sha256": database_hash,
        "required_utc_days": len(source_files),
        "files": records,
    }
    write_new(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return {"days": len(source_files), "manifest": str(manifest_path)}


def main() -> None:
    """Input: default current P2.3. Output: DNSAPOD ZIPs and manifest."""
    print(download_current_windows())


if __name__ == "__main__":
    main()
