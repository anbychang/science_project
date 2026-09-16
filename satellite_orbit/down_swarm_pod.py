"""Download raw Swarm-A orbit files from ESA."""

import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


ESA_SERVER = "https://swarm-diss.eo.esa.int/"
SWARM_A_POD_FOLDER = "swarm/Level2daily/Latest_baselines/POD/RD/Sat_A"
FILES_PER_PAGE = 10000


def list_swarm_a_pod_files():
    """Input: {}
    Output: [{name, path, size, ...}, ...]"""
    source_files = []
    position = 0

    while True:
        list_url = (
            f"{ESA_SERVER}?do=list&maxfiles={FILES_PER_PAGE}&pos={position}"
            f"&file={quote(SWARM_A_POD_FOLDER)}"
        )

        with urlopen(list_url) as response:
            file_list = json.load(response)["results"]

        source_files.extend(file_list)

        if len(file_list) < FILES_PER_PAGE:
            break

        position += len(file_list)

    return source_files


def get_file_day(source_file):
    """Input: {name, path, size, ...}
    Output: "YYYYMMDD"""
    name = source_file["name"]
    time_range = name.split("__")[1].split("_")
    return time_range[1][:8]


def get_file_version(source_file):
    """Input: {name, path, size, ...}
    Output: version number"""
    name = source_file["name"]
    version_text = name.rsplit("_", 1)[1].split(".")[0]
    return int(version_text)


def select_latest_files(source_files, first_day_utc):
    """Input: {source_files, first_day_utc: "YYYY-MM-DD"}
    Output: one latest file per day"""
    first_day = first_day_utc.replace("-", "")
    latest_by_day = {}

    for source_file in source_files:
        day = get_file_day(source_file)
        if day < first_day:
            continue

        current_file = latest_by_day.get(day)
        if current_file is None:
            latest_by_day[day] = source_file
            continue

        if get_file_version(source_file) > get_file_version(current_file):
            latest_by_day[day] = source_file

    selected_files = list(latest_by_day.values())
    selected_files.sort(key=get_file_day)
    return selected_files


def find_swarm_a_pod_file(day_utc):
    """Input: {day_utc: "YYYY-MM-DD"}
    Output: latest {name, path, size, ...}"""
    source_files = list_swarm_a_pod_files()
    selected_files = select_latest_files(source_files, day_utc)
    requested_day = day_utc.replace("-", "")

    for source_file in selected_files:
        if get_file_day(source_file) == requested_day:
            return source_file

    raise ValueError(f"No Swarm-A POD file found for {day_utc}.")


def download_source_file(source_file, output_folder):
    """Input: {source_file, output_folder}
    Output: {path, downloaded}"""
    output_path = Path(output_folder) / source_file["name"]

    if output_path.exists():
        if output_path.stat().st_size != source_file["size"]:
            raise ValueError(f"Wrong file size: {output_path}")
        return output_path, False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = Path(f"{output_path}.part")

    download_url = (
        f"{ESA_SERVER}?do=download&file={quote(source_file['path'])}"
    )
    with urlopen(download_url) as response:
        with partial_path.open("wb") as output_file:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output_file.write(chunk)

    if partial_path.stat().st_size != source_file["size"]:
        raise ValueError(f"Incomplete download: {partial_path}")

    partial_path.replace(output_path)
    return output_path, True


def download_swarm_a_pod(day_utc, data_folder="data"):
    """Input: {day_utc: "YYYY-MM-DD", data_folder}
    Output: data/SW_OPER_SP3ACOM_2__....ZIP"""
    source_file = find_swarm_a_pod_file(day_utc)

    output_path, downloaded = download_source_file(source_file, data_folder)
    return output_path


def download_swarm_a_pod_since(
    first_day_utc,
    data_folder="data/swarm_a_pod",
):
    """Input: {first_day_utc: "YYYY-MM-DD", data_folder}
    Output: [downloaded ZIP paths, ...]"""
    source_files = list_swarm_a_pod_files()
    selected_files = select_latest_files(source_files, first_day_utc)
    downloaded_paths = []

    total_files = len(selected_files)
    for index, source_file in enumerate(selected_files, start=1):
        day = get_file_day(source_file)
        year_folder = Path(data_folder) / day[:4]
        output_path, downloaded = download_source_file(
            source_file,
            year_folder,
        )

        status = "downloaded" if downloaded else "exists"
        print(f"[{index}/{total_files}] {status}: {output_path}")
        downloaded_paths.append(output_path)

    return downloaded_paths
