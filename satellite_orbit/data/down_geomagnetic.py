"""Download raw SYM-H and AE data from WDC Kyoto."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlretrieve

WDC_DATA_URL = "https://wdc.kugi.kyoto-u.ac.jp/hapi/data"
DEFAULT_DATA_FOLDER = Path("data/geomagnetic")

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


def download_geomagnetic(first_day, last_day, data_folder=DEFAULT_DATA_FOLDER):
    """Input: {first_day, last_day, data_folder}
    Output: {sym_h: raw_csv_path, ae: raw_csv_path}"""
    start_time = _read_day(first_day)
    stop_time = _read_day(last_day) + timedelta(days=1)

    if stop_time <= start_time:
        raise ValueError("last_day must not be before first_day.")
    if stop_time - start_time > timedelta(days=366):
        raise ValueError("One download can contain at most 366 days.")

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

        if not file_path.exists():
            urlretrieve(f"{WDC_DATA_URL}?{query}", file_path)

        downloaded_paths[name] = file_path

    return downloaded_paths


def main():
    """Input: python -m ... FIRST_DAY LAST_DAY
    Output: printed {sym_h_path, ae_path}"""
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python -m satellite_orbit.data.down_geomagnetic FIRST_DAY LAST_DAY"
        )

    file_paths = download_geomagnetic(sys.argv[1], sys.argv[2])
    print(f"SYM-H: {file_paths['sym_h']}")
    print(f"AE:    {file_paths['ae']}")


if __name__ == "__main__":
    main()
