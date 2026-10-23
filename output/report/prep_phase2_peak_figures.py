"""Draw the Phase 2.6 peak comparison for every density-qualified storm."""

import math
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DENSITY_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_4_density_v3.sqlite")
GEOMAG_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_5_geomag_orbit_v1.sqlite")
PEAK_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_6_peak_order_v1.sqlite")
IMAGE_DIRECTORY = Path("output/image")
EVENT_DIRECTORY = IMAGE_DIRECTORY / "Phase2" / "P2.6"
EXAMPLE_STORM = "S20240511T0214"
HOUR_US = 3_600_000_000
PULSE_HOURS = 24
FIGURE_DPI = 180
UTC_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def utc_instant(time_us: int) -> datetime:
    """Input: Unix time in us. Output: UTC datetime without float rounding."""
    return UTC_EPOCH + timedelta(microseconds=time_us)


def event_filename(peak: dict) -> str:
    """Input: one P2.6 event. Output: its UTC t0-based PNG filename."""
    return utc_instant(int(peak["t0_time_us"])).strftime("%Y-%m-%dT%H-%MZ.png")


def orbit_ratio_by_id(database: sqlite3.Connection, storm_id: str) -> dict:
    """Input: P2.4 SQLite and storm ID. Output: {orbit_id: paired log density ratio}."""
    rows = database.execute("""
        SELECT orbit_id,SUM(rho_l2_kg_m3 * paired_sample_count),
               SUM(rho_msis_kg_m3 * paired_sample_count)
        FROM storm_density_1min_v3
        WHERE storm_id=? AND paired_sample_count>0 GROUP BY orbit_id
    """, (storm_id,))
    return {orbit_id: math.log(l2_total / msis_total)
            for orbit_id, l2_total, msis_total in rows
            if l2_total > 0 and msis_total > 0}


def save_main_pulse_figure(peak: dict, output_path: Path) -> None:
    """Input: one P2.6 event and PNG path. Output: saved figure."""
    storm_id = peak["storm_id"]
    t0_us = int(peak["t0_time_us"])
    with closing(sqlite3.connect(
        f"file:{DENSITY_DB.resolve().as_posix()}?mode=ro", uri=True
    )) as density, closing(sqlite3.connect(
        f"file:{GEOMAG_DB.resolve().as_posix()}?mode=ro", uri=True
    )) as geomag:
        ratios = orbit_ratio_by_id(density, storm_id)
        orbit_rows = [
            (midpoint_us, q_nt, ratios[orbit_id])
            for orbit_id, midpoint_us, q_nt in geomag.execute("""
                SELECT orbit_id,t_mid_time_us,q_sme_nt FROM storm_geomag_orbit_v1
                WHERE storm_id=? AND is_valid=1 ORDER BY t_mid_time_us
            """, (storm_id,))
            if orbit_id in ratios and abs(midpoint_us - t0_us) <= PULSE_HOURS * HOUR_US
        ]
        catalog = density.execute("""
            SELECT symh_min_nt FROM storm_catalog_v3
            WHERE storm_id=? AND status='used'
        """, (storm_id,)).fetchone()
        symh_rows = density.execute("""
            SELECT t_rel_h,symh_nt FROM storm_minute_feature_v3
            WHERE storm_id=? AND t_rel_h BETWEEN ? AND ? ORDER BY source_time_us
        """, (storm_id, -PULSE_HOURS, PULSE_HOURS)).fetchall()
    if not orbit_rows or not symh_rows or catalog is None:
        raise ValueError(f"Missing F2-3 data for {storm_id}")
    orbit_by_time = {row[0]: row for row in orbit_rows}
    sme_peak_us = int(peak["sme_peak_time_us"])
    density_peak_us = int(peak["density_peak_time_us"])
    if sme_peak_us not in orbit_by_time or density_peak_us not in orbit_by_time:
        raise ValueError(f"P2.6 peaks differ from source orbits for {storm_id}")
    sme_peak_nt = orbit_by_time[sme_peak_us][1]
    density_peak_log_ratio = orbit_by_time[density_peak_us][2]
    symh_min_nt = catalog[0]

    figure, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    orbit_hour = [(row[0] - t0_us) / HOUR_US for row in orbit_rows]
    axes[0].plot(orbit_hour, [row[1] for row in orbit_rows],
                 color="#1565A8", marker="o", markersize=3)
    axes[0].set_ylabel("每圈 SME 平均 (nT)")
    axes[1].plot(orbit_hour, [row[2] for row in orbit_rows],
                 color="#24815D", marker="o", markersize=3)
    axes[1].axhline(0, color="0.45", linestyle=":", linewidth=0.9)
    axes[1].set_ylabel("密度比 ln(L2 / MSIS)")
    axes[2].plot([row[0] for row in symh_rows], [row[1] for row in symh_rows],
                 color="#B33A3A", linewidth=0.8)
    axes[2].set_ylabel("SYM-H (nT)")
    axes[2].set_xlabel("距 SYM-H 最低點 t0 (小時)")

    sme_hour = float(peak["sme_peak_t_rel_h"])
    density_hour = float(peak["density_peak_t_rel_h"])
    axes[0].axvline(sme_hour, color="#1565A8", linestyle=":", linewidth=1.5)
    axes[1].axvline(density_hour, color="#24815D", linestyle=":", linewidth=1.5)
    axes[0].scatter(sme_hour, sme_peak_nt, color="#1565A8", s=65, zorder=3)
    axes[1].scatter(density_hour, density_peak_log_ratio,
                    color="#24815D", s=65, zorder=3)
    axes[2].scatter(0, symh_min_nt, color="#B33A3A", s=65, zorder=3)
    axes[0].set_title(
        f"SME 峰 {sme_peak_nt:.1f} nT | "
        f"{utc_instant(sme_peak_us):%Y-%m-%d %H:%M} UTC ({sme_hour:+.1f} h)",
        loc="left", fontsize=10,
    )
    axes[1].set_title(
        f"密度比峰 ln(L2/MSIS) = {density_peak_log_ratio:.3f} | "
        f"{utc_instant(density_peak_us):%Y-%m-%d %H:%M} UTC ({density_hour:+.1f} h)",
        loc="left", fontsize=10,
    )
    axes[2].set_title(
        f"SYM-H 最低 {symh_min_nt} nT | {utc_instant(t0_us):%Y-%m-%d %H:%M} UTC",
        loc="left", fontsize=10,
    )
    for axis in axes:
        axis.axvline(0, color="0.15", linestyle="--", linewidth=1)
        axis.set_xlim(-PULSE_HOURS, PULSE_HOURS)
        axis.grid(alpha=0.18)
    figure.suptitle(f"Phase 2.6 峰值比較 | {storm_id}", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def save_order_summary(peaks: list[dict], output_path: Path) -> None:
    """Input: P2.6 event records. Output: all-storm peak-timing scatter PNG."""
    figure, axis = plt.subplots(figsize=(9, 8))
    matches = [row for row in peaks if row["expected_order"] == 1]
    others = [row for row in peaks if row["expected_order"] != 1]
    for group, color, label in ((others, "#737E88", "其他順序"),
                                (matches, "#24815D", "SME → 密度 → SYM-H")):
        axis.scatter([float(row["sme_peak_t_rel_h"]) for row in group],
                     [float(row["density_peak_t_rel_h"]) for row in group],
                     c=color, s=54, label=f"{label} ({len(group)})")
    axis.plot((-24, 24), (-24, 24), color="0.5", linestyle=":", linewidth=1)
    axis.axhline(0, color="0.3", linewidth=0.9)
    axis.axvline(0, color="0.3", linewidth=0.9)
    axis.set(xlim=(-24, 24), ylim=(-24, 24),
             xlabel="每圈 SME 峰相對 t0 (小時)",
             ylabel="每圈 ln(L2 / MSIS) 峰相對 t0 (小時)")
    axis.set_aspect("equal", adjustable="box")
    axis.grid(alpha=0.18)
    axis.legend(frameon=False, loc="lower right")
    axis.set_title("Phase 2 峰值順序檢查：21 場密度合格事件", fontsize=14)
    figure.tight_layout()
    figure.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(figure)


def main() -> None:
    """Input: checked P2.4/P2.5/P2.6 SQLite. Output: 21 dated figures."""
    for source_path in (DENSITY_DB, GEOMAG_DB, PEAK_DB):
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
    plt.rcParams["font.family"] = "Microsoft JhengHei"
    plt.rcParams["axes.unicode_minus"] = False
    with closing(sqlite3.connect(
        f"file:{PEAK_DB.resolve().as_posix()}?mode=ro", uri=True
    )) as source:
        source.row_factory = sqlite3.Row
        peaks = [dict(row) for row in source.execute(
            "SELECT * FROM storm_peak_order_v1 ORDER BY t0_time_us"
        )]
    if len(peaks) != 21 or len({row["storm_id"] for row in peaks}) != 21:
        raise ValueError("P2.6 must contain 21 distinct density-qualified storms.")
    example = next((row for row in peaks if row["storm_id"] == EXAMPLE_STORM), None)
    if example is None:
        raise ValueError(f"P2.6 audit lacks {EXAMPLE_STORM}")
    if len({event_filename(row) for row in peaks}) != len(peaks):
        raise ValueError("Distinct P2.6 storms would overwrite the same dated figure.")
    IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    EVENT_DIRECTORY.mkdir(parents=True, exist_ok=False)
    for row in peaks:
        save_main_pulse_figure(row, EVENT_DIRECTORY / event_filename(row))
    example_path = IMAGE_DIRECTORY / "phase2-f2-3-2024-05-11.png"
    summary_path = IMAGE_DIRECTORY / "phase2-f2-3-order-summary.png"
    if not example_path.exists():
        save_main_pulse_figure(example, example_path)
    if not summary_path.exists():
        save_order_summary(peaks, summary_path)


if __name__ == "__main__":
    main()
