"""Read local F10.7 and Ap data for one orbit state."""

import csv
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

DEFAULT_FILE = Path("phases/phase0/data/raw/space_weather/SW-All.csv")
AP_BLOCK_HOURS = 3
AP_12_TO_33_HOURS = range(12, 34, AP_BLOCK_HOURS)
AP_36_TO_57_HOURS = range(36, 58, AP_BLOCK_HOURS)
_weather_cache = {}


def _load_weather_file(file_path):
    """Input: raw space-weather CSV path
    Output: {daily_rows: {...}, ap_by_time: {...}}"""
    file_path = Path(file_path).resolve()

    cache_key = (file_path, file_path.stat().st_mtime_ns, file_path.stat().st_size)
    if cache_key in _weather_cache:
        return _weather_cache[cache_key]

    daily_rows = {}
    ap_by_time = {}

    with file_path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if not row["AP1"]:
                continue

            row_day = datetime.fromisoformat(row["DATE"]).date()
            daily_rows[row_day] = row
            day_start = datetime.combine(row_day, time.min, tzinfo=timezone.utc)

            for slot in range(8):
                slot_time = day_start + timedelta(hours=AP_BLOCK_HOURS * slot)
                ap_by_time[slot_time] = float(row[f"AP{slot + 1}"])

    weather_data = {
        "daily_rows": daily_rows,
        "ap_by_time": ap_by_time,
    }
    _weather_cache[cache_key] = weather_data
    return weather_data


def _average_ap(ap_by_time, current_time, hours_before):
    """Input: {ap_by_time, current_time, hours_before}
    Output: average Ap value"""
    values = [
        ap_by_time[current_time - timedelta(hours=offset_h)]
        for offset_h in hours_before
    ]
    return sum(values) / len(values)


def load_space_weather(state, file_path=DEFAULT_FILE):
    """Input: state
    Output: state + {f107_sfu, f107a_sfu, f107a_last81_sfu, ap_values, f107_data_type}

    ap_values = [daily, now, -3h, -6h, -9h, avg_12_to_33h, avg_36_to_57h]
    """
    state_time = state["time"].astimezone(timezone.utc)
    weather_data = _load_weather_file(file_path)
    daily_rows = weather_data["daily_rows"]
    ap_by_time = weather_data["ap_by_time"]

    current_day = state_time.date()
    previous_day = current_day - timedelta(days=1)

    if current_day not in daily_rows or previous_day not in daily_rows:
        raise ValueError(f"No space-weather data for {current_day}.")

    current_row = daily_rows[current_day]
    previous_row = daily_rows[previous_day]
    start_hour = state_time.hour - state_time.hour % AP_BLOCK_HOURS
    current_ap_time = state_time.replace(
        hour=start_hour,
        minute=0,
        second=0,
        microsecond=0,
    )

    ap_values = [
        float(current_row["AP_AVG"]),
        ap_by_time[current_ap_time],
        ap_by_time[current_ap_time - timedelta(hours=AP_BLOCK_HOURS)],
        ap_by_time[current_ap_time - timedelta(hours=2 * AP_BLOCK_HOURS)],
        ap_by_time[current_ap_time - timedelta(hours=3 * AP_BLOCK_HOURS)],
        _average_ap(ap_by_time, current_ap_time, AP_12_TO_33_HOURS),
        _average_ap(ap_by_time, current_ap_time, AP_36_TO_57_HOURS),
    ]

    state_with_weather = state.copy()
    state_with_weather["f107_sfu"] = float(previous_row["F10.7_OBS"])
    state_with_weather["f107a_sfu"] = float(current_row["F10.7_OBS_CENTER81"])
    state_with_weather["f107a_last81_sfu"] = float(current_row["F10.7_OBS_LAST81"])
    state_with_weather["ap_values"] = ap_values
    state_with_weather["f107_data_type"] = previous_row["F10.7_DATA_TYPE"]
    return state_with_weather
