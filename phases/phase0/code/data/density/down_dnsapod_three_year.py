"""Download the full three-year Swarm-A DNSAPOD pilot source range."""

import json
from datetime import date, datetime, timedelta, timezone
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


FIRST_DAY = date(2023, 7, 1)
LAST_DAY = date(2026, 6, 30)


def required_days(first_day: date, last_day: date) -> set[str]:
    """Input: inclusive UTC date bounds. Output: {YYYYMMDD, ...}."""
    if first_day > last_day:
        raise ValueError("First day must not follow last day.")
    return {
        (first_day + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range((last_day - first_day).days + 1)
    }


def download_three_year(first_day: date, last_day: date, output_folder: Path) -> Path:
    """Input: UTC day bounds and raw folder. Output: verified ZIPs and new manifest."""
    output_folder = Path(output_folder)
    manifest_path = output_folder / f"manifest_dnsapod_{first_day:%Y%m%d}_{last_day:%Y%m%d}.json"
    if manifest_path.exists():
        raise FileExistsError(manifest_path)

    days = required_days(first_day, last_day)
    source_files = select_source_files(list_pod_source_files(), days)
    output_folder.mkdir(parents=True, exist_ok=True)
    records = []
    downloaded_count = 0
    for index, source_file in enumerate(source_files, start=1):
        local_path = output_folder / source_file["name"]
        if not local_path.exists():
            downloaded_count += 1
        download_source_file(source_file, output_folder)
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
        if index % 25 == 0 or index == len(source_files):
            print(f"[{index}/{len(source_files)}] new ZIPs: {downloaded_count}", flush=True)

    manifest = {
        "source": SOURCE_SERVER,
        "collection": "SW_OPER_DNSAPOD_2_",
        "first_day_utc": first_day.isoformat(),
        "last_day_utc": last_day.isoformat(),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": records,
    }
    write_new(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return manifest_path


def main() -> None:
    """Input: fixed three-year pilot range. Output: raw ZIPs and manifest."""
    print(download_three_year(FIRST_DAY, LAST_DAY, OUTPUT_FOLDER))


if __name__ == "__main__":
    main()
