"""Audit the twelve-year Phase 2R source snapshot without changing raw files."""

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from phases.phase0.code.data.geomagnetic.down_supermag_sme import sha256_file
from phases.phase2.code.prep_20_source_audit import (
    audit_gfz,
    audit_kyoto,
    audit_weather,
)
from phases.phase2.code.prep_21_geomag_1min import sme_rows


FIRST_DAY = date(2014, 7, 1)
LAST_DAY = date(2026, 6, 30)
REPLICATION_DATES = (FIRST_DAY, LAST_DAY)
DEFAULT_OUTPUT = Path("phases/phase2r/data/sqlite/phase2r_p2r_0_source_audit.json")


@dataclass(frozen=True)
class AuditPaths:
    """Input: raw source paths. Output: immutable Phase 2R audit path record."""

    sme_folder: Path = Path("phases/phase0/data/raw/sme")
    geomagnetic_folder: Path = Path("phases/phase0/data/raw/geomagnetic")
    solar_file: Path = Path("phases/phase0/data/raw/space_weather/SW-All.csv")


def utc_days(date_range: tuple[date, date]):
    """Input: inclusive UTC date bounds. Output: ordered UTC days."""
    first_day, last_day = date_range
    if first_day > last_day:
        raise ValueError("First UTC day must not follow last UTC day.")
    for offset in range((last_day - first_day).days + 1):
        yield first_day + timedelta(days=offset)


def manifest_records(manifest_path: Path) -> dict[str, dict]:
    """Input: full SME manifest. Output: {file_name: source_record}."""
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = {}
    for record in document["files"]:
        file_name = record["file_name"]
        if file_name in records:
            raise ValueError(f"Duplicate SME manifest record: {file_name}")
        records[file_name] = record
    return records


def audit_sme(folder: Path, date_range: tuple[date, date]) -> dict:
    """Input: SME folder and UTC dates. Output: selected-range coverage audit."""
    manifest_path = folder / "manifest_p2_0_sme.json"
    records = manifest_records(manifest_path)
    invalid_spans = []
    current_start = None
    last_invalid = None
    invalid_count = 0
    low_station_count = 0
    station_min = None
    station_max = None
    day_count = 0

    for day in utc_days(date_range):
        day_count += 1
        file_name = f"SME_{day:%Y%m%d}.csv"
        record = records.get(file_name)
        path = folder / file_name
        if record is None or not path.is_file() or sha256_file(path) != record["sha256"]:
            raise ValueError(f"SME source or digest mismatch: {file_name}")
        row_count = 0
        for row_count, row in enumerate(sme_rows(path, day), start=1):
            time_us, value, stations, valid = row[:4]
            second = time_us // 1_000_000
            if not valid:
                invalid_count += 1
                if current_start is None:
                    current_start = second
                last_invalid = second
                continue
            if current_start is not None:
                invalid_spans.append({
                    "start_unix_s": current_start,
                    "end_unix_s": last_invalid,
                })
                current_start = None
            low_station_count += stations <= 3
            station_min = stations if station_min is None else min(station_min, stations)
            station_max = stations if station_max is None else max(station_max, stations)
        if row_count != 1440:
            raise ValueError(f"SME day has incomplete UTC grid: {file_name}")

    if current_start is not None:
        invalid_spans.append({
            "start_unix_s": current_start,
            "end_unix_s": last_invalid,
        })
    minute_slots = day_count * 1440
    return {
        "manifest_sha256": sha256_file(manifest_path),
        "manifest_files": len(records),
        "day_files": day_count,
        "minute_slots": minute_slots,
        "valid_minutes": minute_slots - invalid_count,
        "invalid_minutes": invalid_count,
        "invalid_spans": invalid_spans,
        "valid_station_min": station_min,
        "valid_station_max": station_max,
        "valid_minutes_with_at_most_3_stations": low_station_count,
    }


def build_audit(paths: AuditPaths = AuditPaths(),
                date_range: tuple[date, date] = REPLICATION_DATES) -> dict:
    """Input: Phase 2R raw paths and UTC dates. Output: verified source audit."""
    weather_audit, weather_rows = audit_weather(paths.solar_file, date_range)
    return {
        "date_range_utc": [day.isoformat() for day in date_range],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "replication": "phase2_final_same_method_12year",
        "sme": audit_sme(paths.sme_folder, date_range),
        "symh": audit_kyoto(paths.geomagnetic_folder, "sym_h", date_range),
        "ae": audit_kyoto(paths.geomagnetic_folder, "ae", date_range),
        "gfz_ap": audit_gfz(paths.geomagnetic_folder, date_range, weather_rows),
        "celestrak": weather_audit,
    }


def write_source_audit(output_path: Path = DEFAULT_OUTPUT,
                       paths: AuditPaths = AuditPaths()) -> dict:
    """Input: raw source paths and new JSON path. Output: written audit record."""
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(output_path)
    report = build_audit(paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return report


def main() -> None:
    """Input: optional output JSON. Output: Phase 2R source audit."""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        raise SystemExit(
            "Usage: python -m phases.phase2r.code.prep_2r0_source_audit [OUTPUT_JSON]"
        )
    output_path = Path(arguments[0]) if arguments else DEFAULT_OUTPUT
    report = write_source_audit(output_path)
    print({"output": output_path.as_posix(), "date_range_utc": report["date_range_utc"]})


if __name__ == "__main__":
    main()
