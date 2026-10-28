"""Download raw F10.7 and Ap data."""

from pathlib import Path
from urllib.request import urlretrieve

SOURCE_URL = "https://celestrak.org/SpaceData/SW-All.csv"
DEFAULT_FILE = Path("research_workspace/phases/phase0/data/raw/space_weather/SW-All.csv")


def download_space_weather(file_path=DEFAULT_FILE):
    """Input: file path
    Output: existing or newly downloaded raw CSV path"""
    file_path = Path(file_path)

    if file_path.exists():
        return file_path

    file_path.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(SOURCE_URL, file_path)
    return file_path
