"""Load one local SYM-H or AE CSV file."""

import csv
from datetime import datetime
from pathlib import Path


def load_geomagnetic_file(file_path):
    """Input: SYM-H or AE CSV path
    Output: [{time, value_nt, version}, ...]"""
    observations = []

    with Path(file_path).open(encoding="utf-8", newline="") as file:
        for row in csv.reader(file):
            if not row or row[0].startswith("#"):
                continue
            value_nt = int(row[1])
            if value_nt == 99999:
                continue
            time_utc = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            observations.append(
                {
                    "time": time_utc,
                    "value_nt": value_nt,
                    "version": int(row[2]),
                }
            )

    return observations
