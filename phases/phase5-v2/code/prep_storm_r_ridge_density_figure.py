"""Plot L2, fitted-tau/R V1, and Ridge-R density for 25 storms."""

import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path("phases/phase5-v2")
SOURCE = ROOT / "data/sqlite/storm_r_ridge_density_v1.sqlite"
OUTPUT = ROOT / "figures/ridge_density_25_storms_5x5_v3.png"
HOUR_US = 3_600_000_000
DENSITY_SCALE = 1e12


def load_events() -> list[dict]:
    """Input: density comparison SQLite. Output: 25 aligned minute series with scores."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        scores = database.execute("""
            SELECT storm_id,v1_rmse_log_density,ridge_rmse_log_density
            FROM event_density_score ORDER BY storm_id
        """).fetchall()
        if len(scores) != 25:
            raise ValueError("Expected 25 storm density scores.")
        events = []
        for storm_id, v1_score, ridge_score in scores:
            minutes = database.execute("""
                SELECT time_us,t0_time_us,rho_l2_phase_kg_m3,
                       rho_phase4_v1_phase_kg_m3,rho_ridge_phase_kg_m3
                FROM density_comparison WHERE storm_id=? ORDER BY time_us
            """, (storm_id,)).fetchall()
            if not minutes:
                raise ValueError(f"Missing density minutes: {storm_id}")
            values = np.asarray(minutes, dtype=float)
            events.append({"storm_id": storm_id,
                           "hours": (values[:, 0] - values[:, 1]) / HOUR_US,
                           "densities": values[:, 2:] * DENSITY_SCALE,
                           "scores": (v1_score, ridge_score)})
    return events


def draw_figure(events: list[dict]) -> None:
    """Input: 25 aligned event series. Output: one 5x5 PNG figure."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "Microsoft JhengHei"
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(5, 5, figsize=(25, 20), dpi=180)
    styles = (
        ("L2 觀測", "#202020", "-", 0.65, 0.55),
        ("V1：同場擬合 τ_k、R_k", "#0072B2", "-", 1.15, 0.90),
        ("Ridge：估計 R_k", "#D55E00", "-", 1.30, 0.95),
    )
    for panel, event in zip(axes.flat, events, strict=True):
        hours = event["hours"]
        densities = event["densities"]
        for index, (label, color, line_style, width, alpha) in enumerate(styles):
            panel.plot(hours, densities[:, index], color=color, linestyle=line_style,
                       linewidth=width, alpha=alpha, label=label,
                       zorder=2 if index == 0 else 3 + index)
        panel.axvline(0, color="#888888", linestyle=":", linewidth=0.8)
        panel.set_xlim(-48, 97)
        panel.set_ylim(0, float(np.max(densities)) * 1.08)
        panel.set_xticks((-48, 0, 48, 96))
        panel.grid(axis="y", color="#dddddd", linewidth=0.5)
        v1, ridge = event["scores"]
        panel.set_title(f"{event['storm_id']}\nlog RMSE  V1 {v1:.2f}  Ridge {ridge:.2f}",
                        fontsize=10, pad=7)
        panel.tick_params(labelsize=8)
    figure.suptitle("25 場磁暴的相位平均密度：L2、擬合 τ_k/R_k、Ridge R_k",
                     fontsize=19, y=0.992)
    figure.legend(*axes.flat[0].get_legend_handles_labels(), loc="upper center",
                  bbox_to_anchor=(0.5, 0.965), ncol=3, frameon=False, fontsize=12)
    figure.text(0.5, 0.93,
                "Ridge 曲線以留出預測的 R_k 及固定 τ=4.75 h 計算；V1 曲線用同場 L2 回頭擬合 τ_k、R_k",
                ha="center", fontsize=11)
    figure.supxlabel("相對事件起點時間（小時）", fontsize=12, y=0.018)
    figure.supylabel("相位平均密度（1e-12 kg/m^3）；各格縱軸獨立", fontsize=12, x=0.012)
    figure.subplots_adjust(left=0.055, right=0.99, bottom=0.065, top=0.895,
                           wspace=0.27, hspace=0.46)
    figure.savefig(OUTPUT, dpi=180, facecolor="white")
    plt.close(figure)


def main() -> None:
    """Input: comparison SQLite. Output: 25-panel density PNG."""
    events = load_events()
    draw_figure(events)
    print(f"Saved {len(events)} density panels to {OUTPUT}")


if __name__ == "__main__":
    main()
