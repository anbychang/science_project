"""Draw three Phase 2 storm comparisons from the read-only P2.4 checkpoint."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DATABASE_PATH = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_4_density_v3.sqlite")
IMAGE_DIRECTORY = Path("output/image")
STORM_IDS = ("S20231105T1654", "S20240511T0214", "S20260120T1152")
MICROSECONDS_PER_HOUR = 3_600_000_000
DENSITY_SCALE = 1e12
FIGURE_DPI = 180


def read_storm(connection: sqlite3.Connection, storm_id: str) -> dict:
    """Input: P2.4 connection and storm ID. Output: minute and orbit plot arrays."""
    catalog = connection.execute(
        "SELECT t0_time_us,symh_min_nt,n_valid_orbits,n_orbits,status "
        "FROM storm_catalog_v3 WHERE storm_id=?", (storm_id,)
    ).fetchone()
    if catalog is None or catalog[4] != "used":
        raise ValueError(f"Storm is absent or fails P2.4 coverage: {storm_id}")

    minutes = connection.execute("""
        SELECT feature.t_rel_h,feature.sme_nt,feature.symh_nt,density.log_ratio_obs
        FROM storm_minute_feature_v3 AS feature
        JOIN storm_density_1min_v3 AS density
          ON density.storm_id=feature.storm_id
         AND density.source_time_us=feature.source_time_us
        WHERE feature.storm_id=? ORDER BY feature.source_time_us
    """, (storm_id,)).fetchall()
    orbits = connection.execute("""
        SELECT orbit.orbit_start_time_us,orbit.orbit_end_time_us,
               orbit.phase_weighted_mean_semi_major_axis_m,
               SUM(density.rho_l2_kg_m3 * density.paired_sample_count)
                 / NULLIF(SUM(density.paired_sample_count),0),
               SUM(density.rho_msis_kg_m3 * density.paired_sample_count)
                 / NULLIF(SUM(density.paired_sample_count),0)
        FROM storm_event_orbit_v3 AS orbit
        LEFT JOIN storm_density_1min_v3 AS density
          ON density.storm_id=orbit.storm_id AND density.orbit_id=orbit.orbit_id
        WHERE orbit.storm_id=?
        GROUP BY orbit.orbit_id ORDER BY orbit.orbit_start_time_us
    """, (storm_id,)).fetchall()
    if not minutes or not orbits:
        raise ValueError(f"Storm lacks plot data: {storm_id}")

    minute_values = np.asarray(minutes, dtype=float)
    orbit_values = np.asarray(orbits, dtype=float)
    orbit_hour = ((orbit_values[:, 0] + orbit_values[:, 1]) / 2 - catalog[0]) \
        / MICROSECONDS_PER_HOUR
    orbit_l2 = orbit_values[:, 3]
    orbit_msis = orbit_values[:, 4]
    return {
        "storm_id": storm_id,
        "t0_us": catalog[0],
        "symh_min_nt": catalog[1],
        "valid_orbits": catalog[2],
        "total_orbits": catalog[3],
        "minute_hour": minute_values[:, 0],
        "sme_nt": minute_values[:, 1],
        "symh_nt": minute_values[:, 2],
        "minute_ratio": np.exp(minute_values[:, 3]),
        "orbit_hour": orbit_hour,
        "orbit_l2": orbit_l2,
        "orbit_msis": orbit_msis,
        "orbit_ratio": orbit_l2 / orbit_msis,
        "orbit_a_delta_m": orbit_values[:, 2] - orbit_values[0, 2],
    }


def save_storm_figure(storm: dict, image_path: Path) -> None:
    """Input: storm plot arrays and PNG path. Output: labeled five-panel PNG."""
    plt.rcParams["font.family"] = "Microsoft JhengHei"
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(5, 1, figsize=(14, 13), sharex=True)
    colors = {"sme": "#1565A8", "symh": "#B33A3A", "l2": "#1565A8",
              "msis": "#B87319", "ratio": "#24815D", "orbit": "#5B4D9A"}

    axes[0].plot(storm["minute_hour"], storm["sme_nt"], color=colors["sme"],
                 linewidth=0.55)
    axes[0].set_ylabel("SME (nT)")

    axes[1].plot(storm["minute_hour"], storm["symh_nt"], color=colors["symh"],
                 linewidth=0.65)
    axes[1].set_ylabel("SYM-H (nT)")

    axes[2].plot(storm["orbit_hour"], storm["orbit_l2"] * DENSITY_SCALE,
                 color=colors["l2"], linewidth=1.7, marker=".", markersize=3,
                 label="DNSAPOD L2")
    axes[2].plot(storm["orbit_hour"], storm["orbit_msis"] * DENSITY_SCALE,
                 color=colors["msis"], linewidth=1.7, marker=".", markersize=3,
                 label="NRLMSIS 2.0")
    axes[2].set_ylabel("每圈密度 (1e-12 kg/m^3)")
    axes[2].legend(loc="upper right", frameon=False, ncol=2)

    axes[3].plot(storm["minute_hour"], storm["minute_ratio"],
                 color=colors["ratio"], linewidth=0.45, alpha=0.28,
                 label="每分鐘")
    axes[3].plot(storm["orbit_hour"], storm["orbit_ratio"],
                 color=colors["ratio"], linewidth=1.9, label="每圈配對平均")
    axes[3].axhline(1, color="0.35", linewidth=0.9, linestyle=":")
    axes[3].set_ylabel("L2 / MSIS")
    axes[3].legend(loc="upper right", frameon=False, ncol=2)

    axes[4].plot(storm["orbit_hour"], storm["orbit_a_delta_m"],
                 color=colors["orbit"], linewidth=1.7, marker=".", markersize=3)
    axes[4].set_ylabel("圈平均 a - 首圈 (m)")
    axes[4].set_xlabel("距 SYM-H 最低點 t0 (小時)")

    for axis in axes:
        axis.axvline(0, color="0.2", linewidth=1, linestyle="--")
        axis.grid(alpha=0.18)
        axis.set_xlim(-50, 100)
    axes[-1].set_xticks((-48, -24, 0, 24, 48, 72, 96))

    t0_utc = datetime.fromtimestamp(storm["t0_us"] / 1_000_000, timezone.utc)
    figure.suptitle(
        f"{storm['storm_id']} | t0 {t0_utc:%Y-%m-%d %H:%M} UTC | "
        f"SYM-H 最低 {storm['symh_min_nt']} nT | 合格圈 "
        f"{storm['valid_orbits']}/{storm['total_orbits']}",
        fontsize=15,
    )
    figure.text(0.5, 0.013, "密度為同位置配對樣本的每圈平均；半長軸是描述性摘要，非已校準的阻力衰減。",
                ha="center", fontsize=10)
    figure.tight_layout(rect=(0, 0.025, 1, 0.975))
    figure.savefig(image_path, dpi=FIGURE_DPI)
    plt.close(figure)


def main() -> None:
    """Input: frozen P2.4 SQLite. Output: three storm PNG figures."""
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(DATABASE_PATH)
    IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{DATABASE_PATH.resolve().as_posix()}?mode=ro",
                         uri=True) as connection:
        for storm_id in STORM_IDS:
            image_path = IMAGE_DIRECTORY / f"phase2-{storm_id.lower()}-indicators.png"
            save_storm_figure(read_storm(connection, storm_id), image_path)
            print(image_path)


if __name__ == "__main__":
    main()
