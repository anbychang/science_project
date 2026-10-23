"""Calculate causal-input NRLMSIS 2.0 density at DNSAPOD samples."""

import csv
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import numpy as np
import pymsis


THREE_HOURS = timedelta(hours=3)
ONE_DAY = timedelta(days=1)
F107A_DAYS = 81
KM_PER_M = 0.001


def load_msis_weather(gfz_path: Path, solar_path: Path) -> dict:
    """Input: GFZ ap JSON and CelesTrak CSV. Output: UTC ap and observed solar maps."""
    gfz = json.loads(Path(gfz_path).read_text(encoding="utf-8"))
    ap_slots = {}
    for label, value, status in zip(gfz["datetime"], gfz["ap"], gfz["status"], strict=True):
        start = datetime.fromisoformat(label.replace("Z", "+00:00"))
        if status != "def" or value is None or not math.isfinite(float(value)):
            raise ValueError(f"Invalid GFZ ap slot: {label}")
        ap_slots[start] = float(value)
    solar = {}
    with Path(solar_path).open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["F10.7_DATA_TYPE"] != "OBS" or not row["F10.7_OBS"]:
                continue
            flux = float(row["F10.7_OBS"])
            if math.isfinite(flux) and flux > 0:
                solar[date.fromisoformat(row["DATE"])] = flux
    daily_solar = {day + ONE_DAY: solar_drivers(day + ONE_DAY, solar)
                   for day in solar}
    return {"ap_slots": ap_slots, "daily_solar": daily_solar}


def solar_drivers(sample_day: date, solar_obs: dict) -> dict | None:
    """Input: UTC sample day and observed flux map. Output: prior-day F10.7/A or None."""
    previous_day = sample_day - ONE_DAY
    previous_flux = solar_obs.get(previous_day)
    observed = [solar_obs[previous_day - timedelta(days=offset)]
                for offset in range(F107A_DAYS)
                if previous_day - timedelta(days=offset) in solar_obs]
    if previous_flux is None or len(observed) != F107A_DAYS:
        return None
    return {"f107_day_utc": previous_day.isoformat(), "f107_sfu": previous_flux,
            "f107a_sfu": sum(observed) / len(observed),
            "f107a_observed_days": len(observed)}


def ap_drivers(sample_time: datetime, ap_slots: dict) -> dict | None:
    """Input: UTC sample time and GFZ slots. Output: seven completed-slot ap values."""
    current_start = sample_time.replace(
        hour=sample_time.hour - sample_time.hour % 3, minute=0, second=0, microsecond=0
    )
    last_start = current_start - THREE_HOURS
    previous_day = sample_time.date() - ONE_DAY
    day_start = datetime.combine(previous_day, time.min, timezone.utc)
    daily = [ap_slots.get(day_start + offset * THREE_HOURS) for offset in range(8)]
    recent = [ap_slots.get(last_start - offset * THREE_HOURS) for offset in range(4)]
    older_12_33 = [ap_slots.get(last_start - offset * THREE_HOURS)
                   for offset in range(4, 12)]
    older_36_57 = [ap_slots.get(last_start - offset * THREE_HOURS)
                   for offset in range(12, 20)]
    if any(value is None for value in daily + recent + older_12_33 + older_36_57):
        return None
    values = [sum(daily) / 8, *recent, sum(older_12_33) / 8,
              sum(older_36_57) / 8]
    return {"ap_values": values,
            "ap_last_slot_end_time_us": int(current_start.timestamp() * 1_000_000),
            "ap_daily_day_utc": previous_day.isoformat()}


def sample_drivers(time_us: int, weather: dict) -> dict | None:
    """Input: DNSAPOD UTC epoch and weather maps. Output: completed MSIS drivers."""
    sample_time = datetime.fromtimestamp(time_us / 1_000_000, timezone.utc)
    solar = weather["daily_solar"].get(sample_time.date())
    ap = ap_drivers(sample_time, weather["ap_slots"])
    if solar is None or ap is None:
        return None
    return {**solar, **ap}


def calculate_msis_density(samples: list[dict], drivers: list[dict]) -> list[float]:
    """Input: aligned DNSAPOD samples and drivers. Output: MSIS densities [kg/m^3]."""
    if len(samples) != len(drivers):
        raise ValueError("MSIS samples and drivers are not aligned.")
    if not samples:
        return []
    dates = np.array([np.datetime64(sample["time_us"], "us") for sample in samples])
    result = pymsis.calculate(
        dates,
        np.array([sample["longitude_deg"] for sample in samples]),
        np.array([sample["latitude_deg"] for sample in samples]),
        np.array([sample["altitude_m"] * KM_PER_M for sample in samples]),
        f107s=np.array([driver["f107_sfu"] for driver in drivers]),
        f107as=np.array([driver["f107a_sfu"] for driver in drivers]),
        aps=np.array([driver["ap_values"] for driver in drivers]),
        version=2.0,
        geomagnetic_activity=-1,
    )
    densities = result[:, pymsis.Variable.MASS_DENSITY].astype(float).tolist()
    return [density if math.isfinite(density) and density > 0 else None
            for density in densities]
