"""Prepare directly available new geomagnetic driver features for Phase4 Trial5."""

import csv
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase4.code.calc_phase4_trial5_drivers import backward_rate


ROOT = Path("phases/phase4")
SOURCE = ROOT / "data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite"
P2_SOURCE = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
OUTPUT = ROOT / "data/sqlite/swarm_a_phase4_trial5_driver_features_v5.sqlite"
AUDIT = ROOT / "data/analysis/phase4_trial5_driver_feature_audit.csv"
ALGORITHM_VERSION = "phase4_trial5_driver_features_v5"


def load_trial1_rows() -> list[dict]:
    """Input: read-only Phase4 Trial1 SQLite. Output: [{anchor, baseline, residual fields}]."""
    with closing(sqlite3.connect(f"file:{SOURCE.resolve().as_posix()}?mode=ro", uri=True)) as database:
        cursor = database.execute("""
            SELECT storm_id,time_us,h_tau_phase_nt,h_24h_phase_nt,sme_phase_nt,symh_phase_nt,
                   rho_l2_phase_kg_m3,rho_trial4_phase_kg_m3,residual_log_density,
                   r_fit,tau_hours,gain_per_nt
            FROM phase4_trial4_gpr_prediction ORDER BY storm_id,time_us
        """)
        fields = [column[0] for column in cursor.description]
        rows = [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]
    if len(rows) != 2295 or len({row["storm_id"] for row in rows}) != 25:
        raise ValueError("Trial5 requires 2,295 anchors from 25 storms.")
    return rows


def load_new_drivers() -> dict[tuple[str, int], tuple[float, float, float]]:
    """Input: read-only P2.6 minute features. Output: {(storm,time): SYM-H rate, ap, F10.7}."""
    with closing(sqlite3.connect(f"file:{P2_SOURCE.resolve().as_posix()}?mode=ro", uri=True)) as database:
        records = database.execute("""
            SELECT storm_id,source_time_us,symh_nt,ap_step,f107_sfu
            FROM storm_minute_feature_v5 ORDER BY storm_id,source_time_us
        """).fetchall()
    output = {}
    start = 0
    while start < len(records):
        storm_id = records[start][0]
        end = start
        while end < len(records) and records[end][0] == storm_id:
            end += 1
        event = records[start:end]
        times = np.array([row[1] for row in event], dtype=np.int64)
        symh = np.array([row[2] for row in event], dtype=float)
        rates = backward_rate(times, symh)
        for row, rate in zip(event, rates, strict=True):
            if math.isfinite(rate) and row[3] is not None and row[4] is not None:
                output[(row[0], row[1])] = (float(rate), float(row[3]), float(row[4]))
        start = end
    return output


def attach_new_drivers(rows: list[dict], drivers: dict[tuple[str, int], tuple[float, float, float]]) -> None:
    """Input: Trial1 anchor rows, P2 driver mapping. Output: rows gain direct driver fields."""
    for row in rows:
        try:
            symh_rate_nt_s, ap_step, f107_sfu = drivers[(row["storm_id"], row["time_us"])]
        except KeyError as error:
            raise ValueError(
                f"Trial5 is missing P2 drivers for {row['storm_id']}:{row['time_us']}"
            ) from error
        row["symh_rate_nt_s"] = symh_rate_nt_s
        row["ap_step"] = ap_step
        row["f107_sfu"] = f107_sfu


def write_sqlite(rows: list[dict]) -> None:
    """Input: Trial5 featured anchor rows. Output: atomic Trial5 feature SQLite database."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="phase4_trial5_features.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE phase4_trial5_driver_feature (
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL,
                    h_tau_phase_nt REAL NOT NULL, h_24h_phase_nt REAL NOT NULL,
                    sme_phase_nt REAL NOT NULL, symh_phase_nt REAL NOT NULL,
                    symh_rate_nt_s REAL NOT NULL, ap_step REAL NOT NULL, f107_sfu REAL NOT NULL,
                    rho_l2_phase_kg_m3 REAL NOT NULL, rho_trial4_phase_kg_m3 REAL NOT NULL,
                    residual_log_density REAL NOT NULL, r_fit REAL NOT NULL, tau_hours REAL NOT NULL,
                    gain_per_nt REAL NOT NULL, algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id,time_us)
                );
                CREATE TABLE phase4_trial5_metadata (name TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            fields = [
                "storm_id", "time_us", "h_tau_phase_nt", "h_24h_phase_nt", "sme_phase_nt",
                "symh_phase_nt", "symh_rate_nt_s", "ap_step", "f107_sfu",
                "rho_l2_phase_kg_m3", "rho_trial4_phase_kg_m3", "residual_log_density",
                "r_fit", "tau_hours", "gain_per_nt",
            ]
            database.executemany(
                "INSERT INTO phase4_trial5_driver_feature VALUES (" + ",".join("?" for _ in range(16)) + ")",
                (tuple(row[field] for field in fields) + (ALGORITHM_VERSION,) for row in rows),
            )
            metadata = {
                "new_features": "symh_rate_nt_s backward difference, ap_step, f107_sfu",
                "p2_source": str(P2_SOURCE),
                "trial1_source": str(SOURCE),
            }
            database.executemany("INSERT INTO phase4_trial5_metadata VALUES (?,?)", metadata.items())
            count = database.execute("SELECT count(*) FROM phase4_trial5_driver_feature").fetchone()[0]
            if count != 2295 or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Trial5 feature SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def write_audit(rows: list[dict]) -> None:
    """Input: Trial5 featured anchor rows. Output: per-feature finite range CSV."""
    feature_names = ("symh_rate_nt_s", "ap_step", "f107_sfu")
    audit_rows = []
    for name in feature_names:
        values = np.array([row[name] for row in rows])
        audit_rows.append({
            "feature_name": name,
            "anchor_count": len(values),
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "unique_value_count": len(np.unique(values)),
        })
    with AUDIT.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)


def main() -> None:
    """Input: fixed Trial1 anchors and P2.6 drivers. Output: non-overwriting Trial5 feature output."""
    if OUTPUT.exists() or AUDIT.exists():
        raise FileExistsError("Trial5 feature outputs already exist.")
    rows = load_trial1_rows()
    attach_new_drivers(rows, load_new_drivers())
    write_sqlite(rows)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    write_audit(rows)
    print("Saved Phase4 Trial5 direct driver features for 2,295 anchors")


if __name__ == "__main__":
    main()
