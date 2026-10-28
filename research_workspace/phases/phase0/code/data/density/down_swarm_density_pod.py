"""Download Swarm-A POD density files for selected storm windows."""

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from shutil import copyfileobj
from time import sleep
from urllib.parse import quote
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile


SOURCE_FOLDER = "swarm/Level2daily/Entire_mission_data/DNS/POD/Sat_A"
SOURCE_SERVER = "https://swarm-diss.eo.esa.int/"
SOURCE_NAME = re.compile(
    r"SW_OPER_DNSAPOD_2__(\d{8})T\d{6}_\d{8}T\d{6}_(\d{4})\.ZIP"
)
STORM_DATABASE = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_storm_p2_2.sqlite")
OUTPUT_FOLDER = Path("research_workspace/phases/phase0/data/raw/swarm_density_pod")
MANIFEST_NAME = "manifest_p2_4_3year.json"
MICROSECONDS_PER_SECOND = 1_000_000
MAX_DOWNLOAD_ATTEMPTS = 3


def required_source_days(database_path: Path) -> set[str]:
    """Input: P2.2 SQLite path. Output: UTC YYYYMMDD days touching selected six-day windows."""
    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    try:
        storm_times_us = [
            row[0] for row in connection.execute(
                "SELECT t0_time_us FROM storm_candidate_v1 "
                "WHERE symh_screening_status = 'selected'"
            )
        ]
    finally:
        connection.close()
    if not storm_times_us:
        raise ValueError("P2.2 has no selected storms.")

    days = set()
    for storm_time_us in storm_times_us:
        storm_time = datetime.fromtimestamp(
            storm_time_us / MICROSECONDS_PER_SECOND, timezone.utc
        )
        window_start = storm_time - timedelta(hours=48)
        window_end = storm_time + timedelta(hours=96)
        day = window_start.date()
        while datetime.combine(day, time.min, timezone.utc) < window_end:
            days.add(day.strftime("%Y%m%d"))
            day += timedelta(days=1)
    return days


def list_pod_source_files() -> list[dict]:
    """Input: ESA POD directory. Output: source file records from ESA listing."""
    list_url = f"{SOURCE_SERVER}?do=list&maxfiles=10000&file={quote(SOURCE_FOLDER)}"
    with urlopen(list_url, timeout=60) as response:
        return json.load(response)["results"]


def select_source_files(source_files: list[dict], days: set[str]) -> list[dict]:
    """Input: ESA records and required UTC days. Output: latest POD ZIP per day."""
    latest_by_day = {}
    for source_file in source_files:
        match = SOURCE_NAME.fullmatch(source_file["name"])
        if match is None or match[1] not in days:
            continue
        previous = latest_by_day.get(match[1])
        if previous is None or match[2] > SOURCE_NAME.fullmatch(previous["name"])[2]:
            latest_by_day[match[1]] = source_file
    missing_days = days - latest_by_day.keys()
    if missing_days:
        raise ValueError(f"ESA has no DNSAPOD ZIP for {sorted(missing_days)}")
    return [latest_by_day[day] for day in sorted(days)]


def verify_zip(path: Path, expected_size: int) -> None:
    """Input: local ZIP path and ESA byte count. Output: valid ZIP or ValueError."""
    if path.stat().st_size != expected_size:
        raise ValueError(f"Wrong byte count: {path}")
    try:
        with ZipFile(path) as archive:
            if not archive.namelist() or archive.testzip() is not None:
                raise ValueError(f"Invalid ZIP contents: {path}")
    except BadZipFile as error:
        raise ValueError(f"Invalid ZIP: {path}") from error


def download_source_file(source_file: dict, output_folder: Path) -> Path:
    """Input: one ESA POD record and output folder. Output: verified local ZIP."""
    output_path = output_folder / source_file["name"]
    if output_path.exists():
        verify_zip(output_path, source_file["size"])
        return output_path

    download_url = f"{SOURCE_SERVER}?do=download&file={quote(source_file['path'])}"
    partial_path = output_folder / f"{source_file['name']}.part"
    for attempt in range(MAX_DOWNLOAD_ATTEMPTS):
        try:
            with urlopen(download_url, timeout=90) as response:
                with partial_path.open("wb") as output:
                    copyfileobj(response, output)
            verify_zip(partial_path, source_file["size"])
            os.replace(partial_path, output_path)
            return output_path
        except (OSError, ValueError):
            partial_path.unlink(missing_ok=True)
            if attempt + 1 == MAX_DOWNLOAD_ATTEMPTS:
                raise
            sleep(2)
    raise AssertionError("Unreachable download retry state.")


def sha256_file(path: Path) -> str:
    """Input: local file path. Output: SHA-256 hex digest."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(source_files: list[dict], output_folder: Path) -> Path:
    """Input: selected ESA records and verified ZIP folder. Output: JSON manifest path."""
    manifest_path = output_folder / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"Manifest already exists: {manifest_path}")
    records = []
    for source_file in source_files:
        local_path = output_folder / source_file["name"]
        records.append({
            "name": source_file["name"],
            "source_path": source_file["path"],
            "source_mtime_utc": datetime.fromtimestamp(
                source_file["mtime"], timezone.utc
            ).isoformat(),
            "downloaded_at_utc": datetime.fromtimestamp(
                local_path.stat().st_mtime, timezone.utc
            ).isoformat(),
            "size_bytes": source_file["size"],
            "sha256": sha256_file(local_path),
        })
    manifest = {
        "source": SOURCE_SERVER,
        "collection": "SW_OPER_DNSAPOD_2_",
        "storm_database": STORM_DATABASE.as_posix(),
        "storm_database_sha256": sha256_file(STORM_DATABASE),
        "selected_storm_status": "selected",
        "window_before_hours": 48,
        "window_after_hours": 96,
        "files": records,
    }
    temporary_path = output_folder / f"{MANIFEST_NAME}.part"
    with temporary_path.open("w", encoding="utf-8") as output:
        json.dump(manifest, output, ensure_ascii=False, indent=2)
        output.write("\n")
    os.replace(temporary_path, manifest_path)
    return manifest_path


def main() -> None:
    """Input: P2.2 selected storms and ESA listing. Output: ZIP files and manifest."""
    if (OUTPUT_FOLDER / MANIFEST_NAME).exists():
        raise FileExistsError(f"Manifest already exists: {OUTPUT_FOLDER / MANIFEST_NAME}")
    days = required_source_days(STORM_DATABASE)
    source_files = select_source_files(list_pod_source_files(), days)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    for index, source_file in enumerate(source_files, start=1):
        download_source_file(source_file, OUTPUT_FOLDER)
        print(f"[{index}/{len(source_files)}] {source_file['name']}", flush=True)
    manifest_path = write_manifest(source_files, OUTPUT_FOLDER)
    print(f"Complete: {len(source_files)} DNSAPOD ZIPs; {manifest_path}")


if __name__ == "__main__":
    main()
