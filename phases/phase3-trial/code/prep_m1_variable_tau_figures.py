"""Plot the M1-based variable orbit tau trial from its SQLite output."""

import sqlite3
from contextlib import closing
from itertools import groupby
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DATABASE = Path("phases/phase3-trial/data/sqlite/swarm_a_m1_variable_orbit_tau_phase2_v2.sqlite")
FIGURES = Path("phases/phase3-trial/figures")


def read_orbit_tau() -> list[tuple[str, int, float]]:
    """Input: variable-tau trial SQLite. Output: [(storm ID, orbit index, tau h)]."""
    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        return database.execute(
            "SELECT storm_id,orbit_index,fitted_tau_hours "
            "FROM m1_variable_tau_orbit ORDER BY storm_id,orbit_index"
        ).fetchall()


def plot_event_panels(rows: list[tuple[str, int, float]]) -> None:
    """Input: [(storm ID, orbit index, tau h)]. Output: 25-panel PNG."""
    events = [(storm_id, list(group)) for storm_id, group in groupby(rows, key=lambda row: row[0])]
    if len(events) != 25:
        raise ValueError(f"Expected 25 events, got {len(events)}")
    figure, axes = plt.subplots(5, 5, figsize=(18, 15), sharex=True, sharey=True)
    for axis, (storm_id, event_rows) in zip(axes.flat, events, strict=True):
        orbit = [row[1] for row in event_rows]
        tau = [row[2] for row in event_rows]
        axis.step(orbit, tau, where="mid", linewidth=0.8, color="#315f87")
        axis.axhline(4.65, color="#777777", linestyle="--", linewidth=0.7)
        for value, color in ((0.0, "#bd3b31"), (10.0, "#d78822")):
            selected = [(x, y) for x, y in zip(orbit, tau, strict=True) if y == value]
            axis.scatter([point[0] for point in selected],
                         [point[1] for point in selected], s=5, color=color, zorder=3)
        axis.set_title(f"{storm_id[1:9]} {storm_id[10:14]}", fontsize=9)
        axis.set_ylim(-0.3, 10.3)
        axis.set_yticks((0, 2, 4, 6, 8, 10))
        axis.grid(alpha=0.2)
    figure.supxlabel("Orbit index from Phase 2 u", fontsize=11, y=0.055)
    figure.supylabel("Fitted tau (hours)", fontsize=11)
    figure.suptitle("M1 quiet MSIS: independently fitted tau for each orbit", fontsize=14)
    figure.text(0.5, 0.022,
                "Gray dash: fixed M1 tau = 4.65 h; red: 0 h; orange: 10 h. In-sample fit.",
                ha="center", fontsize=10)
    figure.tight_layout(rect=(0.025, 0.10, 1, 0.96))
    figure.savefig(FIGURES / "m1_variable_tau_25_events.png", dpi=180)
    plt.close(figure)


def plot_distribution(rows: list[tuple[str, int, float]]) -> None:
    """Input: [(storm ID, orbit index, tau h)]. Output: histogram PNG."""
    values = [row[2] for row in rows]
    figure, axis = plt.subplots(figsize=(10, 4.5))
    counts, _, patches = axis.hist(values, bins=[-0.25 + 0.5 * index for index in range(22)],
                                  edgecolor="white", linewidth=0.5)
    patches[0].set_facecolor("#bd3b31")
    patches[-1].set_facecolor("#d78822")
    for patch in patches[1:-1]:
        patch.set_facecolor("#315f87")
    axis.axvline(4.65, color="#555555", linestyle="--", linewidth=1.2)
    axis.set_xticks(range(11))
    axis.set_xlabel("Fitted tau (hours)")
    axis.set_ylabel("Orbit segments")
    axis.set_title("M1 quiet MSIS: distribution of orbit time constants")
    axis.grid(axis="y", alpha=0.2)
    axis.set_axisbelow(True)
    axis.text(0.02, 0.95,
              f"0 h: {int(counts[0])}; 10 h: {int(counts[-1])}; boundaries: "
              f"{100 * (counts[0] + counts[-1]) / len(values):.1f}%",
              transform=axis.transAxes, va="top")
    figure.tight_layout()
    figure.savefig(FIGURES / "m1_variable_tau_distribution.png", dpi=180)
    plt.close(figure)


def main() -> None:
    """Input: saved M1-based trial SQLite. Output: two diagnostic PNGs."""
    rows = read_orbit_tau()
    FIGURES.mkdir(parents=True, exist_ok=True)
    plot_event_panels(rows)
    plot_distribution(rows)


if __name__ == "__main__":
    main()
