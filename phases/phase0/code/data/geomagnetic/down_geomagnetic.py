"""Download raw SYM-H and AE data from WDC Kyoto."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlretrieve

WDC_DATA_URL = "https://wdc.kugi.kyoto-u.ac.jp/hapi/data"
DEFAULT_DATA_FOLDER = Path("phases/phase0/data/raw/geomagnetic")
MAX_DOWNLOAD_DAYS = 180

DATASETS = {
    "sym_h": ("min_asysym", "symHValue,versionCode"),
    "ae": ("min_ae", "aeValue,versionCode"),
}


def _read_day(day_text):
    """Input: YYYY-MM-DD
    Output: UTC datetime at 00:00:00"""
    day = datetime.strptime(day_text, "%Y-%m-%d")
    return day.replace(tzinfo=timezone.utc)


def _hapi_time(time_utc):
    """Input: UTC datetime
    Output: YYYY-MM-DDTHH:MM:SSZ"""
    return time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _observation_days(file_path):
    """Input: downloaded geomagnetic CSV path
    Output: (first UTC day, last UTC day)"""
    first_time = None
    last_time = None

    with Path(file_path).open(encoding="utf-8") as file:
        for line in file:
            row_text = line.strip()
            if not row_text or row_text.startswith("#"):
                continue
            time_text = row_text.split(",", maxsplit=1)[0]
            observation_time = datetime.fromisoformat(time_text.replace("Z", "+00:00"))
            if first_time is None:
                first_time = observation_time
            last_time = observation_time

    if first_time is None or last_time is None:
        raise ValueError(f"No geomagnetic observation was downloaded to {file_path}.")
    return first_time.date(), last_time.date()


def _check_download_coverage(file_path, first_day, last_day):
    """Input: downloaded CSV path and requested UTC day range
    Output: None when the file covers the requested range"""
    downloaded_first_day, downloaded_last_day = _observation_days(file_path)
    requested_first_day = _read_day(first_day).date()
    requested_last_day = _read_day(last_day).date()
    if downloaded_first_day > requested_first_day:
        raise ValueError(
            f"{file_path} starts at {downloaded_first_day}, not {requested_first_day}. "
            "Download a shorter date range."
        )
    if downloaded_last_day < requested_last_day:
        raise ValueError(
            f"{file_path} ends at {downloaded_last_day}, not {requested_last_day}. "
            "Download a shorter date range."
        )


def download_geomagnetic(first_day, last_day, data_folder=DEFAULT_DATA_FOLDER):
    """Input: {first_day, last_day, data_folder}
    Output: {sym_h: raw_csv_path, ae: raw_csv_path}"""
    start_time = _read_day(first_day)
    stop_time = _read_day(last_day) + timedelta(days=1)

    if stop_time <= start_time:
        raise ValueError("last_day must not be before first_day.")
    if stop_time - start_time > timedelta(days=MAX_DOWNLOAD_DAYS):
        raise ValueError(
            f"One download can contain at most {MAX_DOWNLOAD_DAYS} days."
        )

    data_folder = Path(data_folder)
    data_folder.mkdir(parents=True, exist_ok=True)
    downloaded_paths = {}

    for name, (dataset, parameters) in DATASETS.items():
        file_path = data_folder / f"{name}_{first_day}_{last_day}.csv"
        query = urlencode(
            {
                "dataset": dataset,
                "parameters": parameters,
                "start": _hapi_time(start_time),
                "stop": _hapi_time(stop_time),
                "format": "csv",
                "include": "header",
            }
        )

        if file_path.exists():
            try:
                _check_download_coverage(file_path, first_day, last_day)
            except ValueError:
                pass
            else:
                downloaded_paths[name] = file_path
                continue

        temporary_path = file_path.with_suffix(".download")
        try:
            urlretrieve(f"{WDC_DATA_URL}?{query}", temporary_path)
            _check_download_coverage(temporary_path, first_day, last_day)
            temporary_path.replace(file_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        downloaded_paths[name] = file_path

    return downloaded_paths


def download_geomagnetic_range(first_day, last_day, data_folder=DEFAULT_DATA_FOLDER):
    """Input: requested UTC date range and local folder.
    Output: [{sym_h: path, ae: path}, ...] in <= 180-day source requests."""
    requested_last_day = _read_day(last_day).date()
    chunk_first_day = _read_day(first_day).date()
    downloaded_chunks = []

    while chunk_first_day <= requested_last_day:
        chunk_last_day = min(
            chunk_first_day + timedelta(days=MAX_DOWNLOAD_DAYS - 1),
            requested_last_day,
        )
        downloaded_chunks.append(
            download_geomagnetic(
                chunk_first_day.isoformat(),
                chunk_last_day.isoformat(),
                data_folder,
            )
        )
        chunk_first_day = chunk_last_day + timedelta(days=1)

    return downloaded_chunks


def main():
    """Input: python -m ... FIRST_DAY LAST_DAY
    Output: printed {sym_h_path, ae_path}"""
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python -m phases.phase0.code.data.geomagnetic.down_geomagnetic FIRST_DAY LAST_DAY"
        )

    file_paths = download_geomagnetic(sys.argv[1], sys.argv[2])
    print(f"SYM-H: {file_paths['sym_h']}")
    print(f"AE:    {file_paths['ae']}")


if __name__ == "__main__":
    main()
