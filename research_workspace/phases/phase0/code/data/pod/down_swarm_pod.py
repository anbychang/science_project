"""Download raw Swarm-A POD files from ESA."""

import json
import sys
from pathlib import Path
from time import sleep
from urllib.error import ContentTooShortError
from urllib.parse import quote
from urllib.request import urlopen, urlretrieve

ESA_SERVER = "https://swarm-diss.eo.esa.int/"
ESA_POD_FOLDER = "swarm/Level2daily/Latest_baselines/POD/RD/Sat_A"
DEFAULT_FIRST_DAY = "2014-01-01"
PROJECT_LAST_DAY = "2026-06-30"
DEFAULT_DATA_FOLDER = "research_workspace/phases/phase0/data/raw/swarm_a_pod"
MAX_DOWNLOAD_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 5


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


def select_latest_files(source_files, first_day, last_day=PROJECT_LAST_DAY):
    """Input: ESA files and inclusive YYYY-MM-DD range.
    Output: one latest-version file per requested day."""
    first_day = first_day.replace("-", "")
    last_day = last_day.replace("-", "")
    latest_by_day = {}

    for source_file in source_files:
        day = get_file_day(source_file)
        if day < first_day or day > last_day:
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
    """Input: ESA source metadata and local folder.
    Output: complete local ZIP path."""
    data_folder = Path(data_folder)
    output_path = data_folder / source_file["name"]

    correct_size = output_path.exists() and output_path.stat().st_size == source_file["size"]
    if correct_size:
        return output_path

    data_folder.mkdir(parents=True, exist_ok=True)
    download_url = f"{ESA_SERVER}?do=download&file={quote(source_file['path'])}"
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            urlretrieve(download_url, output_path)
            if output_path.stat().st_size == source_file["size"]:
                return output_path
        except (ContentTooShortError, OSError):
            pass

        output_path.unlink(missing_ok=True)
        if attempt < MAX_DOWNLOAD_ATTEMPTS:
            sleep(RETRY_DELAY_SECONDS)

    raise ValueError(
        f"Incomplete POD download after {MAX_DOWNLOAD_ATTEMPTS} attempts: "
        f"{source_file['name']}."
    )


def download_swarm_a_pod(day, data_folder=DEFAULT_DATA_FOLDER):
    """Input: one day as YYYY-MM-DD
    Output: that day's latest-version ZIP path"""
    source_files = list_swarm_pod_files()
    selected_files = select_latest_files(source_files, day, day)
    requested_day = day.replace("-", "")

    for source_file in selected_files:
        if get_file_day(source_file) == requested_day:
            return download_file(source_file, data_folder)

    raise ValueError(f"No Swarm-A POD file found for {day}.")


def download_swarm_a_pod_since(
    first_day,
    data_folder=DEFAULT_DATA_FOLDER,
    last_day=PROJECT_LAST_DAY,
):
    """Input: inclusive first/last days and local folder.
    Output: local ZIP paths inside the project time range."""
    source_files = list_swarm_pod_files()
    selected_files = select_latest_files(source_files, first_day, last_day)
    downloaded_paths = []

    for index, source_file in enumerate(selected_files, start=1):
        output_path = download_file(source_file, data_folder)
        downloaded_paths.append(output_path)
        print(f"[{index}/{len(selected_files)}] {output_path}")

    return downloaded_paths


def main():
    """Input: python -m ... [FIRST_DAY] [LAST_DAY].
    Output: count of downloaded POD ZIP files."""
    first_day = DEFAULT_FIRST_DAY
    last_day = PROJECT_LAST_DAY
    if len(sys.argv) >= 2:
        first_day = sys.argv[1]
    if len(sys.argv) >= 3:
        last_day = sys.argv[2]
    if len(sys.argv) > 3:
        raise ValueError("Usage: [FIRST_DAY] [LAST_DAY]")

    file_paths = download_swarm_a_pod_since(first_day, last_day=last_day)
    print(f"Complete: {len(file_paths)} files from {first_day} to {last_day}.")


if __name__ == "__main__":
    main()
