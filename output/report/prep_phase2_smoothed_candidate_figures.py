"""Draw all final P2.6 candidate-window event figures."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from satellite_orbit.phase2.calc_centered_mean import centered_mean


DATABASE = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_6_final.sqlite")
OUTPUT = Path("output/image/Phase2/P2.6")


def draw_figures(database_path: Path = DATABASE, output_directory: Path = OUTPUT) -> int:
    """Input: final P2.6 SQLite and image directory. Output: saved event PNG count."""
    database_uri = f"file:{database_path.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as database:
        events = database.execute("""
            SELECT qc.storm_id,analysis.t0_time_us,qc.sme_peak_t_rel_h,
                   qc.density_peak_t_rel_h,qc.sme_to_density_lag_h
            FROM storm_minute_peak_qc_v4 qc
            JOIN storm_minute_analysis_v2 analysis USING (storm_id)
            GROUP BY qc.storm_id
            ORDER BY analysis.t0_time_us
        """).fetchall()
        filenames = [
            datetime.fromtimestamp(row[1] / 1_000_000, timezone.utc).strftime("%Y-%m-%d.png")
            for row in events
        ]
        if len(set(filenames)) != len(filenames):
            raise ValueError("Two storms share the same UTC date filename.")
        existing_figures = [name for name in filenames if (output_directory / name).exists()]
        if existing_figures:
            raise FileExistsError(f"Refusing to overwrite {output_directory / existing_figures[0]}")
        output_directory.mkdir(parents=True, exist_ok=True)
        for event, filename in zip(events, filenames, strict=True):
            rows = database.execute("""
                SELECT source_time_us,t_rel_h,sme_raw_nt,sme_smooth_nt,
                       log_ratio_raw,log_ratio_smooth
                FROM storm_minute_smooth_v4
                WHERE storm_id=? ORDER BY source_time_us
            """, (event[0],)).fetchall()
            symh_rows = database.execute("""
                SELECT source_time_us,symh_nt
                FROM storm_minute_analysis_v2
                WHERE storm_id=? ORDER BY source_time_us
            """, (event[0],)).fetchall()
            symh_smooth = centered_mean(
                [row[0] for row in symh_rows],
                [row[1] for row in symh_rows],
                450_000_000,
            )
            symh_by_time = {
                row[0]: (row[1], smooth)
                for row, smooth in zip(symh_rows, symh_smooth, strict=True)
            }
            hours = [row[1] for row in rows]
            figure, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True,
                                       constrained_layout=True)
            for axis, raw_index, smooth_index, color, label in (
                (axes[0], 2, 3, "#d97706", "SME (nT)"),
                (axes[1], 4, 5, "#2563eb", "ln(rho L2 / rho MSIS)"),
            ):
                axis.plot(hours, [row[raw_index] for row in rows], color=color,
                          alpha=0.3, linewidth=0.7, label="raw")
                axis.plot(hours, [row[smooth_index] for row in rows], color=color,
                          linewidth=1.5, label="smoothed")
                axis.axvline(0, color="black", linestyle="--", linewidth=0.8)
                axis.set_ylabel(label)
                axis.grid(axis="y", alpha=0.3)
                axis.legend(loc="upper right")
            axes[2].plot(
                hours, [symh_by_time[row[0]][0] for row in rows],
                color="#b91c1c", alpha=0.3, linewidth=0.7, label="raw",
            )
            axes[2].plot(
                hours, [symh_by_time[row[0]][1] for row in rows],
                color="#b91c1c", linewidth=1.5, label="15-minute centered mean",
            )
            axes[2].axvline(0, color="black", linestyle="--", linewidth=0.8)
            axes[2].set_ylabel("SYM-H (nT)")
            axes[2].grid(axis="y", alpha=0.3)
            axes[2].legend(loc="upper right")
            axes[0].axvline(event[2], color="#d97706", linestyle=":")
            axes[1].axvline(event[3], color="#2563eb", linestyle=":")
            axes[2].set_xlim(-12, 24)
            axes[2].set_xlabel("Hours relative to raw SYM-H minimum t0")
            figure.suptitle(
                f"P2.6 final {event[0]} | smooth SME {event[2]:+.2f} h | "
                f"smooth density {event[3]:+.2f} h | lag {event[4]:+.2f} h"
            )
            figure.savefig(output_directory / filename, dpi=180)
            plt.close(figure)
    return len(events)


if __name__ == "__main__":
    print(f"saved {draw_figures()} figures in {OUTPUT}")
