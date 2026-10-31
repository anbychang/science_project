"""Draw held-out error comparison for Phase5 Trial6."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path("phases/phase5-trial6")
SOURCE = ROOT / "data/analysis/trial6_event_metrics.csv"
OUTPUT = ROOT / "figures/trial6_event_rmse.png"


def main() -> None:
    """Input: Trial6 event metrics CSV. Output: event RMSE comparison PNG."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    with SOURCE.open(encoding="utf-8-sig", newline="") as source:
        rows = [row for row in csv.DictReader(source) if row["storm_id"] != "all_storms"]
    labels = [row["storm_id"].removeprefix("S") for row in rows]
    positions = np.arange(len(rows))
    figure, axis = plt.subplots(figsize=(12, 9))
    for name, label, color, marker in (
        ("trial4", "Trial4", "#555555", "o"),
        ("interpolation", "Interpolation", "#1261a0", "s"),
        ("ridge_time", "Ridge: time", "#bc6c25", "^"),
        ("ridge_time_day", "Ridge: time + day fraction", "#7b3294", "x"),
    ):
        axis.scatter([float(row[f"{name}_rmse"]) for row in rows], positions,
                     s=26, label=label, color=color, marker=marker)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlabel("Held-out log-density RMSE")
    axis.set_ylabel("Storm ID")
    axis.grid(axis="x", alpha=0.25)
    axis.legend(loc="lower right")
    figure.tight_layout()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT, dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    main()
