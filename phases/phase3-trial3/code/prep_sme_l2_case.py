"""Plot observed SME and L2 density for one storm without fitting a model."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as dates
import matplotlib.pyplot as plt


PHASE2 = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
PHASE3 = Path(
    "phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite"
)
FIGURE = Path("phases/phase3-trial3/figures/s20250101_sme_l2.png")
STORM_ID = "S20250101T1640"
DAY_US = 86_400_000_000


def utc_times(rows: list[tuple]) -> list[datetime]:
    """Input: [(time_us, value), ...]. Output: [UTC datetime, ...]."""
    return [datetime.fromtimestamp(row[0] / 1_000_000, timezone.utc) for row in rows]


def load_curves() -> tuple[int, list[tuple], list[tuple], list[tuple]]:
    """Input: frozen P2/P3 SQLite. Output: t0 and [SME], [raw L2], [phase L2]."""
    prediction_uri = f"file:{PHASE3.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(prediction_uri, uri=True)) as database:
        event = database.execute(
            "SELECT t0_time_us FROM phase3_25storm_overview WHERE storm_id=?",
            (STORM_ID,),
        ).fetchone()
        if event is None:
            raise ValueError(f"Missing event: {STORM_ID}")
        t0 = event[0]
        phase_l2 = database.execute(
            "SELECT time_us,rho_l2_phase_kg_m3 FROM phase3_prediction_minute "
            "WHERE storm_id=? ORDER BY time_us",
            (STORM_ID,),
        ).fetchall()

    source_uri = f"file:{PHASE2.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as database:
        sme = database.execute(
            "SELECT time_us,sme_nt FROM geomag_1min_v2 "
            "WHERE time_us BETWEEN ? AND ? AND sme_valid=1 ORDER BY time_us",
            (t0 - 2 * DAY_US, t0 + 4 * DAY_US),
        ).fetchall()
        raw_l2 = database.execute(
            "SELECT source_time_us,rho_l2_kg_m3 FROM storm_density_1min_v5 "
            "WHERE storm_id=? AND rho_l2_kg_m3 IS NOT NULL "
            "ORDER BY source_time_us",
            (STORM_ID,),
        ).fetchall()
    return t0, sme, raw_l2, phase_l2


def draw_case() -> Path:
    """Input: frozen P2/P3 SQLite. Output: two-panel SME/L2 PNG path."""
    t0, sme, raw_l2, phase_l2 = load_curves()
    if not sme or not raw_l2 or not phase_l2:
        raise ValueError("A required time series is empty")
    event_time = datetime.fromtimestamp(t0 / 1_000_000, timezone.utc)
    figure, (sme_axis, l2_axis) = plt.subplots(
        2, 1, figsize=(13, 7.2), sharex=True, constrained_layout=True
    )
    sme_axis.plot(utc_times(sme), [row[1] for row in sme],
                  color="#147d84", linewidth=0.65, label="SME (1 min)")
    sme_axis.axhline(65, color="#a65d27", linewidth=1, linestyle=":",
                     label="65 nT reference")
    sme_axis.set_ylabel("SME (nT)")
    sme_axis.legend(loc="upper right")

    l2_axis.plot(utc_times(raw_l2), [row[1] * 1e12 for row in raw_l2],
                 color="#9a9a9a", linewidth=0.55, alpha=0.7,
                 label="L2 native 1-min pairs")
    l2_axis.plot(utc_times(phase_l2), [row[1] * 1e12 for row in phase_l2],
                 color="#174d9d", linewidth=1.2,
                 label="L2 centered u±π phase mean")
    l2_axis.set_ylabel("L2 density (10$^{-12}$ kg/m$^3$)")
    l2_axis.set_xlabel("UTC")
    l2_axis.legend(loc="upper right")

    for axis in (sme_axis, l2_axis):
        axis.axvline(event_time, color="#9d2222", linewidth=1.1,
                     linestyle="--", label="Event t0")
        axis.grid(alpha=0.2)
    l2_axis.xaxis.set_major_locator(dates.DayLocator())
    l2_axis.xaxis.set_major_formatter(dates.DateFormatter("%m-%d", tz=timezone.utc))
    figure.suptitle("2025-01-01 storm: observed SME and Swarm-A L2 density")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)
    return FIGURE


if __name__ == "__main__":
    print(draw_case())
