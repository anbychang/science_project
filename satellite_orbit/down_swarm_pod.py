"""Download raw Swarm-A orbit files from ESA."""

import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


ESA_SERVER = "https://swarm-diss.eo.esa.int/"
SWARM_A_POD_FOLDER = "swarm/Level2daily/Latest_baselines/POD/RD/Sat_A"


def find_swarm_a_pod_file(day_utc):
    """Input: {day_utc: "YYYY-MM-DD"}
    Output: {name, path, size, ...}"""
    day_code = day_utc.replace("-", "")
    position = 0

    while True:
        list_url = (
            f"{ESA_SERVER}?do=list&maxfiles=500&pos={position}"
            f"&file={quote(SWARM_A_POD_FOLDER)}"
        )

        with urlopen(list_url) as response:
            file_list = json.load(response)["results"]

        for source_file in file_list:
            name = source_file["name"]
            time_range = name.split("__")[1].split("_")

            # The second time in the name is the main file date.
            if time_range[1].startswith(day_code):
                return source_file

        if len(file_list) < 500:
            break

        position += len(file_list)

    raise ValueError(f"No Swarm-A POD file found for {day_utc}.")


def download_swarm_a_pod(day_utc, data_folder="data"):
    """Input: {day_utc: "YYYY-MM-DD", data_folder}
    Output: data/SW_OPER_SP3ACOM_2__....ZIP"""
    source_file = find_swarm_a_pod_file(day_utc)

    output_path = Path(data_folder) / source_file["name"]
    if output_path.exists():
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    download_url = (
        f"{ESA_SERVER}?do=download&file={quote(source_file['path'])}"
    )
    with urlopen(download_url) as response:
        output_path.write_bytes(response.read())

    return output_path
