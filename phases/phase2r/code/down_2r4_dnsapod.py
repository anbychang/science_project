"""Download DNSAPOD days required by the Phase 2R event-minute windows."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from phases.phase0.code.data.density.down_swarm_density_pod import (
    SOURCE_SERVER,
    download_source_file,
    list_pod_source_files,
    select_source_files,
    sha256_file,
)
from phases.phase0.code.data.geomagnetic.down_gfz_ap import write_new


EPOCH_DAY = date(1970, 1, 1)
MICROSECONDS_PER_DAY = 86_400_000_000


@dataclass(frozen=True)
class DownloadPaths:
    """Input: P2R.3 and raw folder. Output: immutable DNSAPOD manifest path record."""

    event_database: Path = Path("phases/phase2r/data/sqlite/swarm_a_phase2r_p2r_3_t0_phase_v1.sqlite")
    output_folder: Path = Path("phases/phase0/data/raw/swarm_density_pod")
    manifest_name: str = "manifest_dnsapod_phase2r_event_days.json"


def required_days(database_path: Path) -> set[str]:
    """Input: P2R.3 minute SQLite. Output: required DNSAPOD UTC days."""
    uri = f"file:{Path(database_path).resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        day_numbers = connection.execute(
            "SELECT DISTINCT source_time_us / ? FROM storm_minute_feature_v5 "
            "ORDER BY source_time_us / ?",
            (MICROSECONDS_PER_DAY, MICROSECONDS_PER_DAY),
        ).fetchall()
    if not day_numbers:
        raise ValueError("P2R.3 has no event minutes.")
    return {
        (EPOCH_DAY + timedelta(days=int(row[0]))).strftime("%Y%m%d")
        for row in day_numbers
    }


def manifest_document(paths: DownloadPaths, source_files: list[dict]) -> dict:
    """Input: verified local ZIP records. Output: Phase 2R DNSAPOD manifest record."""
    records = []
    for source_file in source_files:
        local_path = paths.output_folder / source_file["name"]
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
    return {
        "source": SOURCE_SERVER,
        "collection": "SW_OPER_DNSAPOD_2_",
        "selection": "Phase 2R storm_minute_feature_v5 UTC days",
        "event_database": paths.event_database.as_posix(),
        "event_database_sha256": sha256_file(paths.event_database),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": records,
    }


def download_required_density(paths: DownloadPaths = DownloadPaths()) -> Path:
    """Input: P2R.3 and ESA listing. Output: verified ZIPs and new manifest."""
    manifest_path = paths.output_folder / paths.manifest_name
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    days = required_days(paths.event_database)
    source_files = select_source_files(list_pod_source_files(), days)
    paths.output_folder.mkdir(parents=True, exist_ok=True)
    downloaded_count = 0
    for index, source_file in enumerate(source_files, start=1):
        local_path = paths.output_folder / source_file["name"]
        if not local_path.exists():
            downloaded_count += 1
        download_source_file(source_file, paths.output_folder)
        if index % 25 == 0 or index == len(source_files):
            print(f"[{index}/{len(source_files)}] new ZIPs: {downloaded_count}", flush=True)
    document = manifest_document(paths, source_files)
    write_new(manifest_path, (json.dumps(document, indent=2) + "\n").encode("utf-8"))
    return manifest_path


def main() -> None:
    """Input: fixed P2R.3 path. Output: required DNSAPOD ZIPs and manifest."""
    print(download_required_density())


if __name__ == "__main__":
    main()
