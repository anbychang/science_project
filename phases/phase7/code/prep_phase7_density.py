"""Build Phase 3-5 density outputs for the configured Phase 7 storm set."""

import json
import math
import os
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase0.code.calculation.density.calc_msis_p2_4 import load_msis_weather
from phases.phase0.code.data.density.down_swarm_density_pod import SOURCE_NAME, sha256_file
from phases.phase3.code.calc_h_tau import filtered_sme, phase_support, phase_weighted_mean
from phases.phase3.code.prep_quiet_msis import pair_quiet_day, source_event_rows
from phases.phase7.code.load_phase7_two_storms import (
    GFZ_AP,
    MINUTE_US,
    PHASE2R,
    RUN_LABEL,
    RUN_ROOT,
    STORM_IDS,
    EventMetadata,
    FixedModel,
    QuietSelection,
    load_events,
    load_fixed_model,
    load_geomag_and_ap,
    quiet_solar_flux,
    required_source_days,
    ridge_prediction,
    select_quiet_runs,
)


SOLAR = Path("phases/phase0/data/raw/space_weather/SW-All.csv")
DNSAPOD_FOLDER = Path("phases/phase0/data/raw/swarm_density_pod")
MANIFEST = RUN_ROOT / "data" / "raw" / f"manifest_dnsapod_{RUN_LABEL}.json"
OUTPUT = RUN_ROOT / "data" / "sqlite" / "swarm_a_phase7_density_v1.sqlite"
ALGORITHM_VERSION = f"phase7_{RUN_LABEL}_density_v1"
SME_REFERENCE_NT = 65.0


def labels_by_minute(
    event_rows: dict[str, list[tuple]], selections: list[QuietSelection]
) -> dict[int, tuple[str, ...]]:
    """Input: event minutes and quiet selections. Output: {minute_us: target labels}."""
    labels: dict[int, list[str]] = defaultdict(list)
    for storm_id, rows in event_rows.items():
        for row in rows:
            labels[int(row[0])].append(storm_id)
    for selection in selections:
        bounds = (
            ("pre", selection.pre_start_time_us, selection.pre_end_exclusive_time_us),
            ("post", selection.post_start_time_us, selection.post_end_exclusive_time_us),
        )
        for kind, start_us, end_us in bounds:
            label = f"{selection.storm_id}:{kind}"
            for time_us in range(start_us, end_us, MINUTE_US):
                labels[time_us].append(label)
    return {time_us: tuple(values) for time_us, values in labels.items()}


def verified_source_files(days: set[str]) -> list[Path]:
    """Input: required UTC days. Output: hash-checked DNSAPOD ZIP paths."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = {}
    for record in manifest["files"]:
        match = SOURCE_NAME.fullmatch(record["name"])
        if match is None or match[1] in records:
            raise ValueError(f"Invalid Phase 7 DNSAPOD manifest row: {record['name']}")
        records[match[1]] = record
    if set(records) != days:
        raise ValueError("Phase 7 DNSAPOD manifest day set differs from selected inputs.")
    files = []
    for day in sorted(days):
        path = DNSAPOD_FOLDER / records[day]["name"]
        if sha256_file(path) != records[day]["sha256"]:
            raise ValueError(f"DNSAPOD source hash changed: {path}")
        files.append(path)
    return files


def calculate_density_totals(
    source_files: list[Path], targets: dict[int, tuple[str, ...]]
) -> dict[tuple[str, int], list[float]]:
    """Input: verified DNSAPOD ZIPs and minute labels. Output: L2/quiet sums by target."""
    weather = load_msis_weather(GFZ_AP, SOLAR)
    totals: dict[tuple[str, int], list[float]] = {}
    for index, zip_path in enumerate(source_files, start=1):
        incoming = pair_quiet_day(zip_path, targets, weather)
        for key, values in incoming.items():
            stored = totals.setdefault(key, [0.0, 0.0, 0])
            stored[0] += values[0]
            stored[1] += values[1]
            stored[2] += values[2]
        if index % 5 == 0 or index == len(source_files):
            print(f"[{index}/{len(source_files)}] quiet MSIS days calculated", flush=True)
    return totals


def quiet_run_ratio(
    run: tuple[str, int, int], totals: dict[tuple[str, int], list[float]]
) -> tuple[float, float]:
    """Input: {label, start_us, end_us} and paired sums. Output: median R and coverage."""
    label, start_us, end_us = run
    ratios = []
    for time_us in range(start_us, end_us, MINUTE_US):
        values = totals.get((label, time_us))
        if values is not None and values[2] > 0:
            ratios.append(values[0] / values[1])
    run_minutes = (end_us - start_us) // MINUTE_US
    coverage = len(ratios) / run_minutes
    if coverage < 0.8 or not ratios:
        raise ValueError(f"Insufficient quiet density coverage: {label}")
    return float(np.median(ratios)), coverage


def phase_density_arrays(
    storm_id: str, rows: list[tuple], totals: dict[tuple[str, int], list[float]]
) -> dict[str, np.ndarray]:
    """Input: P2R event rows and quiet sums. Output: minute and phase density arrays."""
    time_us = np.fromiter((row[0] for row in rows), dtype=np.int64)
    phase = np.fromiter((row[1] for row in rows), dtype=float)
    pair_count = np.fromiter((row[2] for row in rows), dtype=np.int16)
    l2 = np.full(len(rows), np.nan)
    quiet = np.full(len(rows), np.nan)
    full = np.full(len(rows), np.nan)
    for index, row in enumerate(rows):
        values = totals.get((storm_id, int(row[0])), [0.0, 0.0, 0])
        if values[2] != row[2]:
            raise ValueError(f"Quiet MSIS lost paired samples: {storm_id}:{row[0]}")
        if values[2]:
            l2[index] = values[0] / values[2]
            quiet[index] = values[1] / values[2]
            full[index] = row[4]
            if not math.isclose(l2[index], row[3], rel_tol=1e-10):
                raise ValueError(f"L2 differs from frozen P2R: {storm_id}:{row[0]}")
    support = phase_support(phase, pair_count)
    return {
        "time_us": time_us,
        "phase_rad": phase,
        "pair_count": pair_count,
        "valid": support["valid"],
        "rho_l2_phase": phase_weighted_mean(l2, pair_count, support),
        "rho_quiet_phase": phase_weighted_mean(quiet, pair_count, support),
        "rho_full_phase": phase_weighted_mean(full, pair_count, support),
        "support": support,
    }


def event_result(
    event: EventMetadata,
    context: dict,
) -> tuple[tuple, list[tuple]]:
    """Input: one event and prepared arrays/parameters. Output: event row and minute rows."""
    selection: QuietSelection = context["selection"]
    model: FixedModel = context["model"]
    series = context["series"]
    density = phase_density_arrays(event.storm_id, context["rows"], context["totals"])
    valid = density["valid"]
    indexes = (
        density["time_us"] - int(series["first_time_us"])
    ) // MINUTE_US
    response = phase_weighted_mean(
        context["filtered_sme"][indexes], density["pair_count"], density["support"]
    )
    l2 = density["rho_l2_phase"][valid]
    quiet = density["rho_quiet_phase"][valid]
    full = density["rho_full_phase"][valid]
    h_phase = response[valid]
    if any(np.any(~np.isfinite(values)) for values in (l2, quiet, full, h_phase)):
        raise ValueError(f"Invalid Phase 7 event density: {event.storm_id}")
    r_phase3, pre_coverage = quiet_run_ratio((
        f"{event.storm_id}:pre",
        selection.pre_start_time_us,
        selection.pre_end_exclusive_time_us,
    ), context["totals"])
    r_post, post_coverage = quiet_run_ratio((
        f"{event.storm_id}:post",
        selection.post_start_time_us,
        selection.post_end_exclusive_time_us,
    ), context["totals"])
    pre_index = (selection.pre_start_time_us - int(series["first_time_us"])) // MINUTE_US
    if pre_index < 1440:
        raise ValueError(f"Missing 24-hour prequiet SME: {event.storm_id}")
    features = {
        "r_phase3": r_phase3,
        "prequiet_sme_mean_nt": float(np.mean(series["sme_nt"][pre_index - 1440:pre_index])),
        "quiet_f107a_last81_sfu": quiet_solar_flux(selection),
    }
    r_ridge = ridge_prediction(features, model)
    log_anomaly = np.log(l2 / quiet)
    log_r_fit = min(
        float(np.mean(log_anomaly - model.gain_per_nt * h_phase)),
        math.log(np.nextafter(2.0, 0.0)),
    )
    r_fit = math.exp(log_r_fit)
    rho_fit = quiet * r_fit * np.exp(model.gain_per_nt * h_phase)
    rho_ridge = quiet * r_ridge * np.exp(model.gain_per_nt * h_phase)
    fit_rmse = math.sqrt(float(np.mean(np.log(l2 / rho_fit) ** 2)))
    ridge_rmse = math.sqrt(float(np.mean(np.log(l2 / rho_ridge) ** 2)))
    valid_indexes = np.flatnonzero(valid)
    minute_rows = [
        (
            event.storm_id,
            int(density["time_us"][index]),
            float(density["phase_rad"][index]),
            int(density["pair_count"][index]),
            float(density["rho_l2_phase"][index]),
            float(density["rho_quiet_phase"][index]),
            float(density["rho_full_phase"][index]),
            float(response[index]),
            r_fit,
            r_ridge,
            float(rho_fit[position]),
            float(rho_ridge[position]),
            ALGORITHM_VERSION,
        )
        for position, index in enumerate(valid_indexes)
    ]
    event_row = (
        event.storm_id,
        event.t0_time_us,
        event.symh_min_nt,
        selection.pre_start_time_us,
        selection.pre_end_exclusive_time_us,
        selection.post_start_time_us,
        selection.post_end_exclusive_time_us,
        pre_coverage,
        post_coverage,
        r_phase3,
        r_post,
        r_post / r_phase3 - 1,
        features["prequiet_sme_mean_nt"],
        features["quiet_f107a_last81_sfu"],
        r_fit,
        r_ridge,
        r_ridge - r_fit,
        len(minute_rows),
        fit_rmse,
        ridge_rmse,
        ALGORITHM_VERSION,
    )
    return event_row, minute_rows


def create_tables(database: sqlite3.Connection) -> None:
    """Input: empty SQLite connection. Output: Phase 7 density tables."""
    database.executescript("""
        CREATE TABLE phase7_density_event_v1 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL,
            symh_min_nt INTEGER NOT NULL,
            quiet_pre_start_time_us INTEGER NOT NULL,
            quiet_pre_end_exclusive_time_us INTEGER NOT NULL,
            quiet_post_start_time_us INTEGER NOT NULL,
            quiet_post_end_exclusive_time_us INTEGER NOT NULL,
            quiet_pre_density_coverage REAL NOT NULL,
            quiet_post_density_coverage REAL NOT NULL,
            r_phase3 REAL NOT NULL,
            r_post_diagnostic REAL NOT NULL,
            r_post_pre_relative_gap REAL NOT NULL,
            prequiet_sme_mean_nt REAL NOT NULL,
            quiet_f107a_last81_sfu REAL NOT NULL,
            r_fit_external REAL NOT NULL,
            r_ridge_external REAL NOT NULL,
            ridge_minus_fit_r REAL NOT NULL,
            valid_phase_minutes INTEGER NOT NULL,
            fit_rmse_log_density REAL NOT NULL,
            ridge_rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase7_density_minute_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            u_rel_rad REAL NOT NULL,
            paired_sample_count INTEGER NOT NULL,
            rho_l2_phase_kg_m3 REAL NOT NULL,
            rho_msis_quiet_phase_kg_m3 REAL NOT NULL,
            rho_m0_full_phase_kg_m3 REAL NOT NULL,
            h_phase_nt REAL NOT NULL,
            r_fit_external REAL NOT NULL,
            r_ridge_external REAL NOT NULL,
            rho_fit_external_kg_m3 REAL NOT NULL,
            rho_ridge_external_kg_m3 REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us),
            FOREIGN KEY (storm_id) REFERENCES phase7_density_event_v1(storm_id)
        );
        CREATE TABLE phase7_density_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_density() -> dict[str, int]:
    """Input: frozen Phase 0-5 sources. Output: new Phase 7 density SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    events = load_events()
    series = load_geomag_and_ap()
    selections = select_quiet_runs(events, series)
    selection_by_storm = {selection.storm_id: selection for selection in selections}
    model = load_fixed_model()
    filtered = filtered_sme(series["sme_nt"], model.tau_hours) - SME_REFERENCE_NT
    with closing(sqlite3.connect(f"file:{PHASE2R.resolve().as_posix()}?mode=ro", uri=True)) as source:
        event_rows = {event.storm_id: source_event_rows(source, event.storm_id) for event in events}
    targets = labels_by_minute(event_rows, selections)
    days = required_source_days(events, selections)
    source_files = verified_source_files(days)
    totals = calculate_density_totals(source_files, targets)
    results = [
        event_result(event, {
            "selection": selection_by_storm[event.storm_id],
            "model": model,
            "series": series,
            "filtered_sme": filtered,
            "rows": event_rows[event.storm_id],
            "totals": totals,
        })
        for event in events
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=OUTPUT.stem + ".", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.execute("PRAGMA foreign_keys=ON")
            create_tables(database)
            database.executemany(
                "INSERT INTO phase7_density_event_v1 VALUES (" + ",".join("?" * 21) + ")",
                [result[0] for result in results],
            )
            database.executemany(
                "INSERT INTO phase7_density_minute_v1 VALUES (" + ",".join("?" * 13) + ")",
                [row for result in results for row in result[1]],
            )
            database.executemany("INSERT INTO phase7_density_metadata_v1 VALUES (?,?)", [
                ("algorithm_version", ALGORITHM_VERSION),
                ("phase2r_source", str(PHASE2R)),
                ("dnsapod_manifest", str(MANIFEST)),
                ("quiet_rule", "Phase 3 near-zero response; ap<=4; SME<=100 nT; >=90 min"),
                ("phase4_v2_tau_hours", repr(model.tau_hours)),
                ("phase4_v2_gain_per_nt", repr(model.gain_per_nt)),
                ("phase5_v2_model", "frozen storm_r_ridge_v21 full-25-event parameters"),
                ("status", "external-event retrospective validation; compound storms"),
            ])
            database.commit()
            event_count, minute_count = database.execute("""
                SELECT (SELECT COUNT(*) FROM phase7_density_event_v1),
                       (SELECT COUNT(*) FROM phase7_density_minute_v1)
            """).fetchone()
            if (
                event_count != len(STORM_IDS)
                or minute_count != sum(len(result[1]) for result in results)
                or database.execute("PRAGMA foreign_key_check").fetchone() is not None
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            ):
                raise ValueError("Phase 7 density SQLite audit failed.")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    return {"events": event_count, "valid_phase_minutes": minute_count}


def main() -> None:
    """Input: no command-line arguments. Output: Phase 7 density summary."""
    print(write_density())


if __name__ == "__main__":
    main()
