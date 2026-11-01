"""Plot the three-year POD semi-major axis and globally scaled L2 integral line."""

import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from phases.phase6.code.calc_phase6_l2_density_decay import read_only


SOURCE = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_l2_three_year_fit_v1.sqlite",
)
OUTPUT = Path("phases/phase6/figures/phase6_l2_three_year_pod_vs_integral.png")


def load_lines(connection: sqlite3.Connection) -> dict[int, list[tuple[datetime, float, float]]]:
    """Input: three-year fit SQLite. Output: block -> [{UTC, POD a, L2-predicted a}, ...]."""
    rows = connection.execute("""
        SELECT time_us,block_index,observed_a_m,predicted_a_m
        FROM phase6_l2_three_year_integral_v1
        ORDER BY time_us
    """)
    blocks: dict[int, list[tuple[datetime, float, float]]] = defaultdict(list)
    for time_us, block_index, observed_a_m, predicted_a_m in rows:
        blocks[int(block_index)].append((
            datetime.fromtimestamp(int(time_us) / 1_000_000, timezone.utc),
            float(observed_a_m) / 1_000,
            float(predicted_a_m) / 1_000,
        ))
    if not blocks:
        raise ValueError("Three-year fit has no integral lines to plot.")
    return dict(blocks)


def draw(blocks: dict[int, list[tuple[datetime, float, float]]]) -> None:
    """Input: continuous POD/L2 blocks. Output: one three-year comparison PNG."""
    figure, axis = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
    for index, rows in enumerate(blocks.values()):
        times = [row[0] for row in rows]
        axis.plot(
            times,
            [row[1] for row in rows],
            color="#111827",
            linewidth=1.1,
            label="POD phase-orbit mean a" if index == 0 else None,
        )
        axis.plot(
            times,
            [row[2] for row in rows],
            color="#d97706",
            linewidth=1.0,
            label="L2 integral with one global beta_eff" if index == 0 else None,
        )
    axis.set_title("Swarm-A: three-year POD semi-major axis and scaled L2 integral")
    axis.set_xlabel("UTC")
    axis.set_ylabel("Semi-major axis (km)")
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT, dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: fixed three-year fit SQLite. Output: POD/L2 comparison PNG."""
    with closing(read_only(SOURCE)) as database:
        blocks = load_lines(database)
    draw(blocks)
    print(OUTPUT)


if __name__ == "__main__":
    main()
