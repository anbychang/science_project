"""Rebuild each Trial4 anchor's paired day-side sample fraction."""

import csv
import math
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from phases.phase0.code.calculation.density.calc_msis_p2_4 import (
    load_msis_weather, sample_drivers,
)
from phases.phase0.code.data.density.load_dnsapod import load_dnsapod
from phases.phase2.code.prep_24_density_t0_phase import (
    DensityPaths, checked_manifest, minute_label, minute_targets, required_days,
)
from phases.phase3.code.calc_h_tau import phase_support

from calc_trial6_daylight import day_flags


ROOT = Path("phases/phase5-trial6")
SOURCE = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
QUIET = Path("phases/phase4/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite")
ANCHORS = Path("phases/phase5-trial1/data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite")
OUTPUT = ROOT / "data/sqlite/swarm_a_trial6_day_fraction.sqlite"
AUDIT = ROOT / "data/analysis/trial6_feature_audit.csv"
VERSION = "phase4_trial6_day_fraction_v1"
EXPECTED_ANCHORS = 2295


def read_only(path: Path) -> sqlite3.Connection:
    """Input: SQLite path. Output: read-only connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def load_minute_series() -> dict[str, dict]:
    """Input: frozen P2 and quiet SQLite. Output: {storm: minute phase/count arrays}."""
    with closing(read_only(SOURCE)) as source, closing(read_only(QUIET)) as quiet:
        phase_rows = source.execute("""
            SELECT storm_id,source_time_us,u_rel_rad
            FROM storm_minute_feature_v5 ORDER BY storm_id,source_time_us
        """).fetchall()
        count_rows = quiet.execute("""
            SELECT storm_id,time_us,paired_sample_count
            FROM phase3_quiet_density_minute ORDER BY storm_id,time_us
        """).fetchall()
    if len(phase_rows) != len(count_rows):
        raise ValueError("Phase 2 and quiet-MSIS minute counts differ.")
    grouped: dict[str, dict] = {}
    for phase_row, count_row in zip(phase_rows, count_rows, strict=True):
        storm_id, time_us, phase = phase_row
        if (storm_id, time_us) != count_row[:2]:
            raise ValueError(f"Minute keys differ: {storm_id}:{time_us}")
        series = grouped.setdefault(storm_id, {"time_us": [], "phase": [], "count": []})
        series["time_us"].append(time_us)
        series["phase"].append(phase)
        series["count"].append(count_row[2])
    return grouped


def collect_native_counts() -> dict[tuple[str, int], tuple[int, int]]:
    """Input: native ZIPs and P2 minute keys. Output: {(storm,minute): (paired,day)}."""
    with closing(read_only(SOURCE)) as source:
        targets = minute_targets(source)
        days = required_days(source)
    paths = DensityPaths()
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    counts: dict[tuple[str, int], list[int]] = {}
    files = checked_manifest(paths, days)
    for file_number, zip_path in enumerate(files, 1):
        selected = []
        selected_keys = []
        for sample in load_dnsapod(zip_path)["samples"]:
            minute_us = minute_label(sample["time_us"])
            storm_ids = targets.get(minute_us)
            if not storm_ids or sample["rho_l2_kg_m3"] is None:
                continue
            if sample_drivers(sample["time_us"], weather) is None:
                continue
            selected.append(sample)
            selected_keys.append((minute_us, storm_ids))
        for (minute_us, storm_ids), is_day in zip(
            selected_keys, day_flags(selected), strict=True
        ):
            for storm_id in storm_ids:
                pair = counts.setdefault((storm_id, minute_us), [0, 0])
                pair[0] += 1
                pair[1] += int(is_day)
        if file_number % 25 == 0 or file_number == len(files):
            print(f"Checked native day side {file_number}/{len(files)} days", flush=True)
    return {key: (values[0], values[1]) for key, values in counts.items()}


def build_rows(series_by_storm: dict, native: dict) -> list[dict]:
    """Input: {storm: minute arrays}, native counts. Output: aligned anchor records."""
    with closing(read_only(ANCHORS)) as source:
        anchors = source.execute("""
            SELECT storm_id,time_us,rho_l2_phase_kg_m3,
                   rho_trial4_phase_kg_m3,residual_log_density
            FROM phase4_trial4_gpr_prediction ORDER BY storm_id,time_us
        """).fetchall()
    if len(anchors) != EXPECTED_ANCHORS:
        raise ValueError(f"Expected {EXPECTED_ANCHORS} anchors, found {len(anchors)}.")
    by_storm: dict[str, list[tuple]] = {}
    for anchor in anchors:
        by_storm.setdefault(anchor[0], []).append(anchor)
    if set(by_storm) != set(series_by_storm):
        raise ValueError("Anchor and minute storm IDs differ.")
    rows = []
    for storm_id, storm_anchors in by_storm.items():
        series = series_by_storm[storm_id]
        times = np.array(series["time_us"], dtype=np.int64)
        phase = np.array(series["phase"], dtype=float)
        paired = np.array(series["count"], dtype=np.int16)
        native_pair = np.array([native.get((storm_id, int(time)), (0, 0))[0]
                                for time in times], dtype=np.int16)
        day = np.array([native.get((storm_id, int(time)), (0, 0))[1]
                        for time in times], dtype=np.int16)
        if not np.array_equal(native_pair, paired):
            mismatch = int(np.flatnonzero(native_pair != paired)[0])
            raise ValueError(f"Native pairing differs: {storm_id}:{times[mismatch]}")
        support = phase_support(phase, paired)
        day_cumulative = np.r_[0, np.cumsum(day)]
        index_by_time = {int(time): index for index, time in enumerate(times)}
        start_us = storm_anchors[0][1]
        for anchor in storm_anchors:
            _, time_us, rho_l2, rho_trial4, residual = anchor
            index = index_by_time[time_us]
            if not support["valid"][index]:
                raise ValueError(f"Anchor support invalid: {storm_id}:{time_us}")
            if not math.isclose(math.log(rho_l2 / rho_trial4), residual, abs_tol=1e-9):
                raise ValueError(f"Trial4 residual differs: {storm_id}:{time_us}")
            count = int(support["paired"][index])
            day_count = int(day_cumulative[support["right"][index]]
                            - day_cumulative[support["left"][index]])
            rows.append({
                "storm_id": storm_id,
                "time_us": time_us,
                "elapsed_hours": (time_us - start_us) / 3_600_000_000,
                "day_count": day_count,
                "paired_count": count,
                "day_fraction": day_count / count,
                "support_start_us": int(times[support["left"][index]]),
                "support_end_us": int(times[support["right"][index] - 1]),
                "rho_l2_phase_kg_m3": rho_l2,
                "rho_trial4_phase_kg_m3": rho_trial4,
                "residual_log_density": residual,
            })
    return rows


def save(rows: list[dict]) -> None:
    """Input: [anchor records]. Output: new derived SQLite and feature audit CSV."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists() or AUDIT.exists():
        raise FileExistsError("Trial6 day fraction output already exists.")
    handle, name = tempfile.mkstemp(prefix="trial6_day.", suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.execute("""
                CREATE TABLE trial6_anchor_feature (
                    storm_id TEXT NOT NULL,time_us INTEGER NOT NULL,
                    elapsed_hours REAL NOT NULL,day_count INTEGER NOT NULL,
                    paired_count INTEGER NOT NULL,day_fraction REAL NOT NULL,
                    support_start_us INTEGER NOT NULL,support_end_us INTEGER NOT NULL,
                    rho_l2_phase_kg_m3 REAL NOT NULL,
                    rho_trial4_phase_kg_m3 REAL NOT NULL,
                    residual_log_density REAL NOT NULL,algorithm_version TEXT NOT NULL,
                    PRIMARY KEY(storm_id,time_us)
                )
            """)
            fields = list(rows[0])
            database.executemany(
                "INSERT INTO trial6_anchor_feature VALUES (" + ",".join("?" for _ in range(12)) + ")",
                (tuple(row[field] for field in fields) + (VERSION,) for row in rows),
            )
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Trial6 feature SQLite integrity check failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    audit = []
    for storm_id in sorted({row["storm_id"] for row in rows}):
        selected = [row for row in rows if row["storm_id"] == storm_id]
        audit.append({"storm_id": storm_id, "anchor_count": len(selected),
                      "min_day_fraction": min(row["day_fraction"] for row in selected),
                      "max_day_fraction": max(row["day_fraction"] for row in selected),
                      "mean_day_fraction": sum(row["day_fraction"] for row in selected) / len(selected)})
    with AUDIT.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(audit[0]))
        writer.writeheader()
        writer.writerows(audit)


def main() -> None:
    """Input: frozen Trial4, P2, quiet-MSIS, DNSAPOD. Output: Trial6 day fractions."""
    if OUTPUT.exists() or AUDIT.exists():
        raise FileExistsError("Trial6 day fraction output already exists.")
    rows = build_rows(load_minute_series(), collect_native_counts())
    save(rows)
    print(f"Saved {len(rows)} Trial6 orbit anchors", flush=True)


if __name__ == "__main__":
    main()
