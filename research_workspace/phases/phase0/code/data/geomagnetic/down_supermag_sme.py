"""Download daily one-minute SME records from the SuperMAG web service."""

import csv
import hashlib
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from time import sleep
from urllib.parse import urlencode
from urllib.request import urlopen


API_URL = "https://supermag.jhuapl.edu/services/indices.php"
DEFAULT_OUTPUT_FOLDER = Path("research_workspace/phases/phase0/data/raw/sme")
DEFAULT_DATES = (date(2014, 1, 1), date(2026, 6, 30))
MANIFEST_NAME = "manifest_p2_0_sme.json"
MAX_ATTEMPTS = 3


def day_url(day: date, user_id: str) -> str:
    """Input: UTC day and SuperMAG user ID. Output: one-day index API URL."""
    query = urlencode(
        {
            "start": datetime.combine(day, time.min).strftime("%Y-%m-%dT%H:%M"),
            "extent": 86_400,
            "logon": user_id,
            "indices": "sme,num",
        }
    )
    return f"{API_URL}?{query}"


def api_records(payload: bytes) -> list[dict]:
    """Input: SuperMAG API response bytes. Output: one-minute index mappings."""
    text = payload.decode("utf-8").strip()
    if text == "OK":
        raise ValueError("SuperMAG returned no records after OK.")
    if text.startswith("OK\n"):
        text = text.split("\n", maxsplit=1)[1].strip()
    decoded = json.loads(text)
    if isinstance(decoded, dict):
        decoded = decoded.get("data", decoded.get("results", []))
    if not isinstance(decoded, list) or not all(isinstance(row, dict) for row in decoded):
        raise ValueError("SuperMAG response has no record list.")
    if not decoded:
        raise ValueError("SuperMAG returned an empty record list.")
    return decoded


def record_value(record: dict, names: tuple[str, ...]):
    """Input: API record and candidate names. Output: found value or None."""
    lowercase = {name.lower(): value for name, value in record.items()}
    for name in names:
        if name.lower() in lowercase:
            return lowercase[name.lower()]
    return None


def sme_rows(records: list[dict]) -> list[tuple[object, object, object]]:
    """Input: SuperMAG API records. Output: [(tval, SME, SMEnum), ...]."""
    rows = []
    for record in records:
        tval = record_value(record, ("tval", "time"))
        sme = record_value(record, ("SME",))
        station_count = record_value(record, ("SMEnum", "num"))
        if tval is None or sme is None:
            raise ValueError("SuperMAG record is missing tval or SME.")
        rows.append((tval, sme, station_count))
    return rows


def write_day(path: Path, rows: list[tuple[object, object, object]]) -> None:
    """Input: new CSV path and SME rows. Output: atomic daily raw CSV file."""
    temporary_path = path.with_suffix(".part")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(("tval", "SME", "SMEnum"))
            writer.writerows(rows)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def download_day(day: date, user_id: str, output_folder: Path) -> dict:
    """Input: UTC day, SuperMAG user ID, output folder. Output: daily file provenance."""
    path = output_folder / f"SME_{day:%Y%m%d}.csv"
    if path.exists():
        return {"file_name": path.name, "row_count": row_count(path), "downloaded_at_utc": None}

    for attempt in range(MAX_ATTEMPTS):
        try:
            with urlopen(day_url(day, user_id), timeout=60) as response:
                rows = sme_rows(api_records(response.read()))
            write_day(path, rows)
            return {
                "file_name": path.name,
                "row_count": len(rows),
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            if attempt + 1 == MAX_ATTEMPTS:
                raise
            sleep(2)
    raise AssertionError("Unreachable download retry state.")


def row_count(path: Path) -> int:
    """Input: SME CSV path. Output: verified data-row count."""
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["tval", "SME", "SMEnum"]:
            raise ValueError(f"Unexpected SME columns: {path}")
        count = sum(1 for _ in reader)
    if not count:
        raise ValueError(f"SME file has no rows: {path}")
    return count


def sha256_file(path: Path) -> str:
    """Input: local file path. Output: SHA-256 hex digest."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(records: list[dict], output_folder: Path) -> Path:
    """Input: daily provenance records and raw folder. Output: immutable JSON manifest."""
    manifest_path = output_folder / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"SME manifest already exists: {manifest_path}")
    files = []
    for record in records:
        path = output_folder / record["file_name"]
        files.append(
            {
                **record,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "source": API_URL,
        "collection": "SuperMAG SME",
        "requested_indices": ["sme", "num"],
        "time_system": "UTC",
        "files": files,
    }
    temporary_path = output_folder / f"{MANIFEST_NAME}.part"
    try:
        with temporary_path.open("w", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary_path, manifest_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return manifest_path


def download_range(date_range: tuple[date, date], user_id: str, output_folder: Path) -> Path:
    """Input: inclusive UTC dates, user ID, output folder. Output: completed manifest path."""
    first_day, last_day = date_range
    if first_day > last_day:
        raise ValueError("The first UTC day must not be after the last UTC day.")
    if not user_id.strip():
        raise ValueError("Set SUPERMAG_USER_ID before downloading SME.")
    output_folder = Path(output_folder)
    manifest_path = output_folder / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"SME manifest already exists: {manifest_path}")
    output_folder.mkdir(parents=True, exist_ok=True)
    records = []
    day = first_day
    while day <= last_day:
        record = download_day(day, user_id, output_folder)
        records.append(record)
        print(f"{day.isoformat()}: {record['row_count']} SME rows", flush=True)
        day += timedelta(days=1)
    return write_manifest(records, output_folder)


def main() -> None:
    """Input: SUPERMAG_USER_ID and optional UTC dates. Output: raw files and manifest."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 3):
        raise SystemExit(
            "Usage: python -m research_workspace.phases.phase0.code.data.geomagnetic.down_supermag_sme "
            "[FIRST_DAY LAST_DAY OUTPUT_FOLDER]"
        )
    if arguments:
        first_day, last_day, output_folder = arguments
        date_range = (date.fromisoformat(first_day), date.fromisoformat(last_day))
    else:
        date_range = DEFAULT_DATES
        output_folder = DEFAULT_OUTPUT_FOLDER
    manifest_path = download_range(date_range, os.environ.get("SUPERMAG_USER_ID", ""), Path(output_folder))
    print(f"Complete: {manifest_path}")


if __name__ == "__main__":
    main()
