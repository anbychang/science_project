"""Audit the three-year Phase 2 source snapshot without changing raw files."""

import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from phases.phase0.code.data.geomagnetic.down_gfz_ap import validate_ap
from phases.phase0.code.data.geomagnetic.down_supermag_sme import sha256_file


PILOT_DATES = (date(2023, 7, 1), date(2026, 6, 30))
OUTPUT_PATH = Path("phases/phase2/data/sqlite/phase2_p2_0_source_audit.json")
MINUTES_PER_DAY = 1440


def utc_second(day: date) -> int:
    """Input: UTC day. Output: Unix second at that day's start."""
    return int(datetime.combine(day, time.min, tzinfo=timezone.utc).timestamp())


def audit_sme(folder: Path, date_range: tuple[date, date]) -> dict:
    """Input: SME raw folder and UTC dates. Output: coverage and integrity record."""
    manifest_path = folder / "manifest_p2_0_sme.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest["files"]
    first_day, last_day = date_range
    expected_days = (last_day - first_day).days + 1
    if len(files) != expected_days:
        raise ValueError("SME manifest does not cover every expected day.")

    invalid_spans = []
    current_start = None
    last_invalid = None
    invalid_count = 0
    low_station_count = 0
    station_min = None
    station_max = None
    for offset, source in enumerate(files):
        day = first_day + timedelta(days=offset)
        day_start = utc_second(day)
        file_name = f"SME_{day:%Y%m%d}.csv"
        path = folder / file_name
        if source["file_name"] != file_name or sha256_file(path) != source["sha256"]:
            raise ValueError(f"SME source or digest mismatch: {file_name}")
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != ["tval", "SME", "SMEnum"]:
                raise ValueError(f"Unexpected SME columns: {file_name}")
            row_count = 0
            for row_count, row in enumerate(reader, 1):
                second = int(float(row["tval"]))
                if float(row["tval"]) != second or second != day_start + 60 * (row_count - 1):
                    raise ValueError(f"Unexpected SME UTC minute: {file_name}:{row_count}")
                value = float(row["SME"])
                stations = int(row["SMEnum"])
                invalid = value == 999999.0 and stations == 0
                if (value == 999999.0) != (stations == 0):
                    raise ValueError(f"Ambiguous SME fill or station count: {file_name}:{row_count}")
                if invalid:
                    invalid_count += 1
                    if current_start is None:
                        current_start = second
                    last_invalid = second
                else:
                    if not math.isfinite(value) or value < 0 or value >= 999998 or stations < 1:
                        raise ValueError(f"Unexpected SME value: {file_name}:{row_count}")
                    if current_start is not None:
                        invalid_spans.append({"start_unix_s": current_start, "end_unix_s": last_invalid})
                        current_start = None
                    low_station_count += stations <= 3
                    station_min = stations if station_min is None else min(station_min, stations)
                    station_max = stations if station_max is None else max(station_max, stations)
        if row_count != MINUTES_PER_DAY or source["row_count"] != row_count:
            raise ValueError(f"SME day has incomplete UTC grid: {file_name}")
    if current_start is not None:
        invalid_spans.append({"start_unix_s": current_start, "end_unix_s": last_invalid})
    return {
        "manifest_sha256": sha256_file(manifest_path),
        "day_files": expected_days,
        "minute_slots": expected_days * MINUTES_PER_DAY,
        "valid_minutes": expected_days * MINUTES_PER_DAY - invalid_count,
        "invalid_minutes": invalid_count,
        "invalid_spans": invalid_spans,
        "valid_station_min": station_min,
        "valid_station_max": station_max,
        "valid_minutes_with_at_most_3_stations": low_station_count,
    }


def audit_kyoto(folder: Path, prefix: str, date_range: tuple[date, date]) -> dict:
    """Input: Kyoto CSV folder, index prefix, UTC dates. Output: minute audit."""
    first_day, last_day = date_range
    first_stamp = f"{first_day.isoformat()}T00:00:00Z"
    last_stamp = f"{(last_day + timedelta(days=1)).isoformat()}T00:00:00Z"
    records = {}
    versions = Counter()
    duplicate_count = 0
    files = {}
    for path in sorted(folder.glob(f"{prefix}_*.csv")):
        source_start, source_end = path.stem.split("_")[-2:]
        if source_end < first_day.isoformat() or source_start > last_day.isoformat():
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            header = json.loads(handle.readline()[1:])
            if header["cadence"] != "PT1M" or header["timeStampLocation"] != "center":
                raise ValueError(f"Unexpected Kyoto time metadata: {path.name}")
            files[path.name] = {
                "sha256": sha256_file(path),
                "modification_date": header["modificationDate"],
            }
            for stamp, value, version in csv.reader(handle):
                if not first_stamp <= stamp < last_stamp:
                    continue
                if len(stamp) != 20 or stamp[17:] != "00Z":
                    raise ValueError(f"Kyoto observation is off the UTC minute grid: {stamp}")
                if int(value) == 99999:
                    continue
                record = (int(value), int(version))
                if stamp in records:
                    duplicate_count += 1
                    if records[stamp] != record:
                        raise ValueError(f"Conflicting Kyoto duplicate: {path.name}:{stamp}")
                else:
                    records[stamp] = record
                    versions[version] += 1
    expected_minutes = ((last_day - first_day).days + 1) * MINUTES_PER_DAY
    if len(records) > expected_minutes:
        raise ValueError(f"Too many Kyoto minutes for {prefix}.")
    return {
        "source_sha256": files,
        "observed_minutes": len(records),
        "expected_minutes": expected_minutes,
        "missing_or_fill_minutes": expected_minutes - len(records),
        "matching_duplicate_rows": duplicate_count,
        "versions": dict(sorted(versions.items())),
    }


def audit_weather(path: Path, date_range: tuple[date, date]) -> tuple[dict, dict]:
    """Input: CelesTrak CSV and UTC dates. Output: audit and daily source rows."""
    first_day, last_day = date_range
    daily = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            day = date.fromisoformat(row["DATE"])
            if first_day <= day <= last_day:
                if day in daily:
                    raise ValueError(f"Duplicate CelesTrak day: {day}")
                if not row["F10.7_OBS"] or any(not row[f"AP{index}"] for index in range(1, 9)):
                    raise ValueError(f"Missing CelesTrak driver on {day}.")
                daily[day] = row
    expected_days = (last_day - first_day).days + 1
    if len(daily) != expected_days:
        raise ValueError("CelesTrak weather days are incomplete.")
    types = Counter(row["F10.7_DATA_TYPE"] for row in daily.values())
    non_observed = [day.isoformat() for day, row in sorted(daily.items()) if row["F10.7_DATA_TYPE"] != "OBS"]
    return {
        "sha256": sha256_file(path),
        "days": len(daily),
        "f107_data_types": dict(sorted(types.items())),
        "non_observed_f107_days": non_observed,
    }, daily


def audit_gfz(folder: Path, date_range: tuple[date, date], weather: dict) -> dict:
    """Input: GFZ raw folder, UTC dates, CelesTrak days. Output: ap audit."""
    first_day, last_day = date_range
    stem = f"gfz_ap_{first_day.isoformat()}_{last_day.isoformat()}"
    raw_path = folder / f"{stem}.json"
    manifest_path = folder / f"{stem}.manifest.json"
    raw = raw_path.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError("GFZ ap raw digest does not match its manifest.")
    slot_count = validate_ap(raw, first_day, last_day)
    source = json.loads(raw)
    mismatches = 0
    for timestamp, value in zip(source["datetime"], source["ap"]):
        day = date.fromisoformat(timestamp[:10])
        slot = int(timestamp[11:13]) // 3 + 1
        mismatches += float(value) != float(weather[day][f"AP{slot}"])
    return {
        "raw_sha256": digest,
        "manifest_sha256": sha256_file(manifest_path),
        "slot_count": slot_count,
        "status": "def",
        "celestrak_ap_mismatch_slots": mismatches,
    }


def build_audit(date_range: tuple[date, date]) -> dict:
    """Input: inclusive UTC dates. Output: verified Phase 2 source audit record."""
    weather, daily = audit_weather(Path("phases/phase0/data/raw/space_weather/SW-All.csv"), date_range)
    return {
        "date_range_utc": [day.isoformat() for day in date_range],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sme": audit_sme(Path("phases/phase0/data/raw/sme"), date_range),
        "symh": audit_kyoto(Path("phases/phase0/data/raw/geomagnetic"), "sym_h", date_range),
        "ae": audit_kyoto(Path("phases/phase0/data/raw/geomagnetic"), "ae", date_range),
        "gfz_ap": audit_gfz(Path("phases/phase0/data/raw/geomagnetic"), date_range, daily),
        "celestrak": weather,
    }


def main() -> None:
    """Input: optional output JSON path. Output: three-year source-audit JSON."""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise SystemExit("Usage: python -m phases.phase2.code.prep_20_source_audit [OUTPUT_JSON]")
    output_path = Path(arguments[0]) if arguments else OUTPUT_PATH
    if output_path.exists():
        raise FileExistsError(output_path)
    report = build_audit(PILOT_DATES)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(output_path)


if __name__ == "__main__":
    main()
