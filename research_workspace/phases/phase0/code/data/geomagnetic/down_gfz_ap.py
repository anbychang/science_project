"""Download definitive three-hour ap values from GFZ."""

import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


API_URL = "https://kp.gfz.de/app/json/"
DEFAULT_DATES = (date(2023, 7, 1), date(2026, 6, 30))
DEFAULT_OUTPUT_FOLDER = Path("research_workspace/phases/phase0/data/raw/geomagnetic")
SLOT_DURATION = timedelta(hours=3)


def api_url(first_day: date, last_day: date) -> str:
    """Input: inclusive UTC dates. Output: GFZ definitive ap URL."""
    query = urlencode(
        {
            "start": f"{first_day.isoformat()}T00:00:00Z",
            "end": f"{last_day.isoformat()}T23:59:59Z",
            "index": "ap",
            "status": "def",
        }
    )
    return f"{API_URL}?{query}"


def validate_ap(payload: bytes, first_day: date, last_day: date) -> int:
    """Input: GFZ JSON and inclusive UTC dates. Output: verified 3-hour slot count."""
    document = json.loads(payload)
    timestamps = document["datetime"]
    values = document["ap"]
    statuses = document["status"]
    expected_count = ((last_day - first_day).days + 1) * 8
    if not (len(timestamps) == len(values) == len(statuses) == expected_count):
        raise ValueError("GFZ ap does not cover every expected three-hour slot.")

    first_slot = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    for index, (timestamp, value, status) in enumerate(zip(timestamps, values, statuses)):
        actual = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if actual != first_slot + index * SLOT_DURATION:
            raise ValueError(f"GFZ ap slot {index} has an unexpected UTC start.")
        if status != "def" or value is None or not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError(f"GFZ ap slot {index} is not a valid definitive value.")
    return expected_count


def write_new(path: Path, payload: bytes) -> None:
    """Input: target path and bytes. Output: new local file without overwrite."""
    if path.exists():
        raise FileExistsError(path)
    temporary_path = path.with_suffix(path.suffix + ".part")
    created_temporary = False
    try:
        with temporary_path.open("xb") as output:
            created_temporary = True
            output.write(payload)
        os.rename(temporary_path, path)
    finally:
        if created_temporary:
            temporary_path.unlink(missing_ok=True)


def download_ap(first_day: date, last_day: date, output_folder: Path) -> Path:
    """Input: inclusive UTC dates and folder. Output: raw GFZ JSON and manifest path."""
    if first_day > last_day:
        raise ValueError("The first UTC day must not be after the last UTC day.")
    stem = f"gfz_ap_{first_day.isoformat()}_{last_day.isoformat()}"
    raw_path = output_folder / f"{stem}.json"
    manifest_path = output_folder / f"{stem}.manifest.json"
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError(f"GFZ ap output already exists: {stem}")

    url = api_url(first_day, last_day)
    with urlopen(url, timeout=60) as response:
        payload = response.read()
    slot_count = validate_ap(payload, first_day, last_day)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "source_url": url,
        "retrieved_at_utc": retrieved_at,
        "raw_file": raw_path.name,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "slot_count": slot_count,
        "first_slot_start_utc": f"{first_day.isoformat()}T00:00:00Z",
        "last_slot_start_utc": f"{last_day.isoformat()}T21:00:00Z",
        "status": "def",
    }
    output_folder.mkdir(parents=True, exist_ok=True)
    write_new(raw_path, payload)
    write_new(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return manifest_path


def main() -> None:
    """Input: optional FIRST_DAY LAST_DAY. Output: GFZ ap files in shared raw."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 2):
        raise SystemExit("Usage: python -m research_workspace.phases.phase0.code.data.geomagnetic.down_gfz_ap [FIRST_DAY LAST_DAY]")
    dates = tuple(date.fromisoformat(value) for value in arguments) if arguments else DEFAULT_DATES
    print(download_ap(*dates, DEFAULT_OUTPUT_FOLDER))


if __name__ == "__main__":
    main()
