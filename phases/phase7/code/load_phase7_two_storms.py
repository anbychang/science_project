"""Load frozen sources for the configured Phase 7 storm set."""

import json
import math
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from phases.phase3.code.prep_phase3_rquiet_near_zero import near_zero_runs


RUN_ROOT = Path(os.environ.get("PHASE7_RUN_ROOT", "phases/phase7"))
RUN_LABEL = os.environ.get("PHASE7_RUN_LABEL", "early_2023_two_storms")
STORM_IDS = tuple(
    storm_id
    for storm_id in os.environ.get(
        "PHASE7_STORM_IDS", "S20230227T1212,S20230324T0521"
    ).split(",")
    if storm_id
)
if not STORM_IDS or len(STORM_IDS) != len(set(STORM_IDS)):
    raise ValueError("PHASE7_STORM_IDS must contain one or more distinct storm IDs.")
MINUTE_US = 60_000_000
SELECTION_END_US = int(datetime(2023, 6, 1, tzinfo=timezone.utc).timestamp() * 1_000_000)
PHASE2R = Path("phases/phase2r/data/sqlite/swarm_a_phase2r_p2r_6_final_v1.sqlite")
PHASE1R = Path(
    "phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite"
)
GFZ_AP = Path("phases/phase0/data/raw/geomagnetic/gfz_ap_2014-07-01_2026-06-30.json")
PHASE4_V2 = Path("phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite")
PHASE5_V2 = Path("phases/phase5-v2/data/sqlite/storm_r_ridge_v21.sqlite")
PHASE6_BEFF = Path("phases/phase6/data/sqlite/swarm_a_phase6_1_beff_v1.sqlite")


@dataclass(frozen=True)
class EventMetadata:
    """Input: frozen P2R rows. Output: one selected event and phase-window record."""

    storm_id: str
    t0_time_us: int
    symh_min_nt: int
    first_minimum_time_us: int
    last_minimum_time_us: int
    minute_start_time_us: int
    minute_end_time_us: int


@dataclass(frozen=True)
class QuietSelection:
    """Input: one event and quiet-run indexes. Output: pre/post UTC minute bounds."""

    storm_id: str
    pre_start_time_us: int
    pre_end_exclusive_time_us: int
    post_start_time_us: int
    post_end_exclusive_time_us: int


@dataclass(frozen=True)
class FixedModel:
    """Input: frozen Phase 4/5/6 parameters. Output: fixed downstream model record."""

    tau_hours: float
    gain_per_nt: float
    ridge_intercept: float
    ridge_parameters: dict[str, tuple[float, float, float]]
    beff_m2_kg: float


def read_only(path: Path) -> sqlite3.Connection:
    """Input: existing SQLite path. Output: read-only SQLite connection."""
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_events() -> list[EventMetadata]:
    """Input: frozen P2R SQLite. Output: [checked event metadata records]."""
    marks = ",".join("?" for _ in STORM_IDS)
    with closing(read_only(PHASE2R)) as database:
        rows = database.execute(f"""
            SELECT e.storm_id,e.t0_time_us,e.symh_min_nt,
                   MIN(m.minimum_time_us),MAX(m.minimum_time_us),
                   p.minute_start_time_us,p.minute_end_time_us,
                   c.l2_coverage,c.paired_coverage,c.is_valid_80pct
            FROM storm_event_v2 AS e
            JOIN storm_minimum_v2 AS m ON m.storm_id=e.storm_id
            JOIN storm_event_t0_phase_v5 AS p ON p.storm_id=e.storm_id
            JOIN storm_event_coverage_v5 AS c ON c.storm_id=e.storm_id
            WHERE e.storm_id IN ({marks})
            GROUP BY e.storm_id
            ORDER BY e.t0_time_us
        """, STORM_IDS).fetchall()
    if len(rows) != len(STORM_IDS) or any(
        row["is_valid_80pct"] != 1
        or row["l2_coverage"] < 0.8
        or row["paired_coverage"] < 0.8
        for row in rows
    ):
        raise ValueError("Phase 7 events need complete frozen P2R windows.")
    return [EventMetadata(row[0], *(int(value) for value in row[1:7])) for row in rows]


def load_geomag_and_ap() -> dict[str, int | np.ndarray]:
    """Input: P2R geomag and 12-year GFZ ap. Output: aligned minute arrays through 2023-05."""
    with closing(read_only(PHASE2R)) as database:
        first_time_us, count = database.execute(
            "SELECT MIN(time_us),COUNT(*) FROM geomag_1min_v2 WHERE time_us<?",
            (SELECTION_END_US,),
        ).fetchone()
        rows = database.execute(
            "SELECT sme_nt,sme_valid FROM geomag_1min_v2 WHERE time_us<? ORDER BY time_us",
            (SELECTION_END_US,),
        )
        sme = np.fromiter(
            (float(row[0]) if row[1] else np.nan for row in rows), dtype=float, count=count
        )
    source = json.loads(GFZ_AP.read_text(encoding="utf-8"))
    ap_first_time_us = int(
        datetime.fromisoformat(source["datetime"][0].replace("Z", "+00:00")).timestamp()
        * 1_000_000
    )
    ap = np.repeat(np.asarray(source["ap"], dtype=float), 180)[:count]
    if first_time_us != ap_first_time_us or len(ap) != len(sme) or not np.isfinite(sme).all():
        raise ValueError("P2R SME and GFZ ap are not a complete aligned minute grid.")
    return {"first_time_us": int(first_time_us), "sme_nt": sme, "ap": ap}


def select_quiet_runs(events: list[EventMetadata], series: dict) -> list[QuietSelection]:
    """Input: events and aligned SME/ap. Output: nearest Phase 3 pre/post quiet runs."""
    first_time_us = int(series["first_time_us"])
    runs = near_zero_runs(series["sme_nt"], series["ap"])

    def minute_index(time_us: int) -> int:
        """Input: UTC epoch us. Output: minute index from the P2R grid start."""
        return (time_us - first_time_us) // MINUTE_US

    def time_us(index: int) -> int:
        """Input: minute index from P2R start. Output: UTC epoch us."""
        return first_time_us + index * MINUTE_US

    selections = []
    for event in events:
        first_minimum = minute_index(event.first_minimum_time_us)
        last_minimum = minute_index(event.last_minimum_time_us)
        pre = max((run for run in runs if run[1] <= first_minimum), key=lambda run: run[1])
        post = min((run for run in runs if run[0] >= last_minimum), key=lambda run: run[0])
        selections.append(QuietSelection(
            event.storm_id,
            time_us(pre[0]),
            time_us(pre[1]),
            time_us(post[0]),
            time_us(post[1]),
        ))
    return selections


def required_source_days(
    events: list[EventMetadata], selections: list[QuietSelection]
) -> set[str]:
    """Input: event and quiet bounds. Output: DNSAPOD UTC day labels YYYYMMDD."""
    days = set()
    bounds = [(event.minute_start_time_us, event.minute_end_time_us) for event in events]
    bounds.extend(
        interval
        for selection in selections
        for interval in (
            (selection.pre_start_time_us, selection.pre_end_exclusive_time_us),
            (selection.post_start_time_us, selection.post_end_exclusive_time_us),
        )
    )
    for start_us, end_us in bounds:
        day = datetime.fromtimestamp(start_us / 1_000_000, timezone.utc).date()
        last_day = datetime.fromtimestamp((end_us - 1) / 1_000_000, timezone.utc).date()
        while day <= last_day:
            days.add(day.strftime("%Y%m%d"))
            day += timedelta(days=1)
    return days


def load_fixed_model() -> FixedModel:
    """Input: frozen Phase 4 V2, Phase 5 V2, and Phase 6. Output: fixed parameters."""
    with closing(read_only(PHASE4_V2)) as database:
        phase4_rows = database.execute(
            "SELECT DISTINCT tau_hours,gain_per_nt FROM phase4_v2_events"
        ).fetchall()
    if len(phase4_rows) != 1:
        raise ValueError("Phase 4 V2 must contain one shared tau and gain.")
    with closing(read_only(PHASE5_V2)) as database:
        ridge_parameters = {
            row["feature"]: (
                float(row["train_mean"]),
                float(row["train_scale"]),
                float(row["coefficient"]),
            )
            for row in database.execute(
                "SELECT feature,train_mean,train_scale,coefficient FROM final_parameter"
            )
        }
        ridge_intercept = float(database.execute(
            "SELECT value FROM metadata WHERE name='final_intercept_delta_r'"
        ).fetchone()[0])
    with closing(read_only(PHASE6_BEFF)) as database:
        beff_rows = database.execute(
            "SELECT beta_eff_m2_kg FROM phase6_1_beff_fit_v1"
        ).fetchall()
    expected_features = {
        "r_phase3", "prequiet_sme_mean_nt", "quiet_f107a_last81_sfu"
    }
    if ridge_parameters.keys() != expected_features or len(beff_rows) != 1:
        raise ValueError("Frozen Ridge or B_eff parameter contract changed.")
    return FixedModel(
        float(phase4_rows[0][0]),
        float(phase4_rows[0][1]),
        ridge_intercept,
        ridge_parameters,
        float(beff_rows[0][0]),
    )


def quiet_solar_flux(selection: QuietSelection) -> float:
    """Input: pre-event quiet run. Output: latest causal F10.7A before run start in sfu."""
    with closing(read_only(PHASE1R)) as database:
        row = database.execute("""
            SELECT time_us,f107a_last81_sfu FROM space_weather
            WHERE time_us<=? ORDER BY time_us DESC LIMIT 1
        """, (selection.pre_start_time_us,)).fetchone()
    if row is None or row[1] is None or selection.pre_start_time_us - row[0] > 3 * 60 * MINUTE_US:
        raise ValueError(f"Missing causal F10.7A for {selection.storm_id}.")
    return float(row[1])


def ridge_prediction(features: dict[str, float], model: FixedModel) -> float:
    """Input: three frozen Ridge factors and parameters. Output: predicted event R."""
    correction = model.ridge_intercept
    for name, (mean, scale, coefficient) in model.ridge_parameters.items():
        correction += coefficient * (features[name] - mean) / scale
    prediction = features["r_phase3"] + correction
    if not 0 < prediction < 2 or not math.isfinite(prediction):
        raise ValueError(f"Invalid frozen Ridge prediction: {prediction}")
    return prediction
