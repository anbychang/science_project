"""Plot the Phase 4 V2 shared-tau search from its SQLite results."""

import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter


DATA_DIR = Path("phases/phase4-v2/data/sqlite")
OUTPUT = Path("phases/phase4-v2/figures/shared_tau_rmse.png")


def load_scores(database_name: str, table_name: str) -> list[tuple[float, float]]:
    """Input: V2 SQLite name and table. Output: [(tau h, event-equal log RMSE)]."""
    source = DATA_DIR / database_name
    uri = f"file:{source.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        return database.execute(f"""
            SELECT tau_hours, event_equal_rmse_log_density
            FROM {table_name} ORDER BY tau_hours
        """).fetchall()


def main() -> None:
    """Input: V2 coarse/fine SQLite. Output: two-panel RMSE PNG under figures/."""
    coarse = load_scores("shared_tau_grid_v1.sqlite", "shared_tau_grid")
    fine = load_scores("shared_tau_fine_v1.sqlite", "shared_tau_fine")
    if len(coarse) != 151 or len(fine) != 31:
        raise ValueError("Expected 151 coarse and 31 fine tau candidates.")
    coarse_best = min(coarse, key=lambda row: row[1])
    fine_best = min(fine, key=lambda row: row[1])
    if coarse_best[0] != 4.8 or fine_best[0] != 4.75:
        raise ValueError("The selected tau changed; review the report first.")

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False})
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout="constrained")
    for axis, scores, best, title, marker_size in (
        (axes[0], coarse, coarse_best, "Coarse search: 0 to 15 h", 9),
        (axes[1], fine, fine_best, "Fine search: 4.6 to 4.9 h", 20),
    ):
        tau, rmse = zip(*scores)
        axis.plot(tau, rmse, color="#2067a7", linewidth=1.8)
        axis.scatter(tau, rmse, color="#2067a7", s=marker_size, zorder=3)
        axis.scatter([best[0]], [best[1]], color="#c44e25", s=64, zorder=5)
        axis.axvline(best[0], color="#c44e25", linewidth=1, linestyle="--", alpha=0.75)
        axis.set_title(title, loc="left", fontweight="bold")
        axis.set_xlabel("Shared tau (hours)")
        axis.set_ylabel("Event-equal log-density RMSE")
        axis.grid(color="#d8dfe5", linewidth=0.7, alpha=0.75)
        axis.text(0.97, 0.94, f"minimum: {best[0]:.2f} h\nRMSE: {best[1]:.9f}",
                  transform=axis.transAxes, ha="right", va="top",
                  bbox={"facecolor": "white", "edgecolor": "#d8dfe5", "alpha": 0.95})
    axes[0].set_xlim(0, 15)
    axes[1].set_xlim(4.6, 4.9)
    axes[1].yaxis.set_major_formatter(FormatStrFormatter("%.6f"))
    figure.suptitle("Phase 4 V2: fixed shared tau selection", fontsize=15, fontweight="bold")
    figure.supxlabel("Each candidate refits 25 event R values and one shared G; in-sample score.",
                     fontsize=9, color="#4c5661")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT, dpi=180, facecolor="white")
    plt.close(figure)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
