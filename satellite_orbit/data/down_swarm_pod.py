"""Download raw Swarm-A POD files from ESA."""

import json
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, urlretrieve

ESA_SERVER = "https://swarm-diss.eo.esa.int/"
ESA_POD_FOLDER = "swarm/Level2daily/Latest_baselines/POD/RD/Sat_A"
DEFAULT_FIRST_DAY = "2022-01-01"
DEFAULT_DATA_FOLDER = "data/swarm_a_pod"


def list_swarm_pod_files():
    """Output: every Swarm-A POD file listed by ESA."""
    list_url = f"{ESA_SERVER}?do=list&maxfiles=10000&file={quote(ESA_POD_FOLDER)}"

    with urlopen(list_url) as response:
        return json.load(response)["results"]


def get_file_day(source_file):
    """Output: data day as YYYYMMDD."""
    name = source_file["name"]
    end_time = name.split("__")[1].split("_")[1]
    return end_time[:8]


def get_file_version(source_file):
    """Output: ESA product version as an integer."""
    name = source_file["name"]
    version = name.rsplit("_", 1)[1].split(".")[0]
    return int(version)


def select_latest_files(source_files, first_day):
    """Input: all files and first YYYY-MM-DD
    Output: one latest-version file per day"""
    first_day = first_day.replace("-", "")
    latest_by_day = {}

    for source_file in source_files:
        day = get_file_day(source_file)
        if day < first_day:
            continue

        old_file = latest_by_day.get(day)
        if old_file is None:
            latest_by_day[day] = source_file
        elif get_file_version(source_file) > get_file_version(old_file):
            latest_by_day[day] = source_file

    selected_files = list(latest_by_day.values())
    selected_files.sort(key=get_file_day)
    return selected_files


def download_file(source_file, data_folder):
    """Output: local ZIP path."""
    data_folder = Path(data_folder)
    output_path = data_folder / source_file["name"]

    correct_size = output_path.exists() and output_path.stat().st_size == source_file["size"]
    if correct_size:
        return output_path

    data_folder.mkdir(parents=True, exist_ok=True)
    download_url = f"{ESA_SERVER}?do=download&file={quote(source_file['path'])}"
    urlretrieve(download_url, output_path)
    return output_path


def download_swarm_a_pod(day, data_folder=DEFAULT_DATA_FOLDER):
    """Input: one day as YYYY-MM-DD
    Output: that day's latest-version ZIP path"""
    source_files = list_swarm_pod_files()
    selected_files = select_latest_files(source_files, day)
    requested_day = day.replace("-", "")

    for source_file in selected_files:
        if get_file_day(source_file) == requested_day:
            return download_file(source_file, data_folder)

    raise ValueError(f"No Swarm-A POD file found for {day}.")


def download_swarm_a_pod_since(
    first_day,
    data_folder=DEFAULT_DATA_FOLDER,
):
    """Input: first day as YYYY-MM-DD
    Output: local ZIP paths from that day onward"""
    source_files = list_swarm_pod_files()
    selected_files = select_latest_files(source_files, first_day)
    downloaded_paths = []

    for index, source_file in enumerate(selected_files, start=1):
        output_path = download_file(source_file, data_folder)
        downloaded_paths.append(output_path)
        print(f"[{index}/{len(selected_files)}] {output_path}")

    return downloaded_paths


def main():
    first_day = DEFAULT_FIRST_DAY
    if len(sys.argv) >= 2:
        first_day = sys.argv[1]

    file_paths = download_swarm_a_pod_since(first_day)
    print(f"Complete: {len(file_paths)} files since {first_day}.")


if __name__ == "__main__":
    main()
