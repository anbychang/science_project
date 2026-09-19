"""Add F10.7 and Ap data to one orbit state."""

import csv
from datetime import datetime, time, timedelta, timezone
from pathlib import Path


DEFAULT_FILE = Path("data/space_weather/SW-All.csv")
_weather_cache = {}


def _read_needed_days(state_time, file_path):
    """Input: {state_time, file_path}
    Output: {date_1: raw_row_1, date_2: raw_row_2, ...}"""
    first_day = state_time.date() - timedelta(days=3)
    last_day = state_time.date()
    rows = {}

    with Path(file_path).open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            row_day = datetime.fromisoformat(row["DATE"]).date()

            if row_day < first_day:
                continue
            if row_day > last_day:
                break
            if not row["AP1"]:
                continue

            rows[row_day] = row

    return rows


def _make_ap_timeline(rows):
    """Input: {date_1: raw_row_1, ...}
    Output: {time_1: ap_1, time_2: ap_2, ...}"""
    ap_by_time = {}

    for row_day, row in rows.items():
        day_start = datetime.combine(row_day, time.min, tzinfo=timezone.utc)

        for slot in range(8):
            slot_time = day_start + timedelta(hours=3 * slot)
            ap_by_time[slot_time] = float(row[f"AP{slot + 1}"])

    return ap_by_time


def _load_day_data(state_time, file_path):
    """Input: {state_time, file_path}
    Output: {rows: {...}, ap_by_time: {...}}"""
    file_path = Path(file_path).resolve()
    cache_key = (file_path, state_time.date())

    if cache_key in _weather_cache:
        return _weather_cache[cache_key]

    rows = _read_needed_days(state_time, file_path)
    day_data = {
        "rows": rows,
        "ap_by_time": _make_ap_timeline(rows),
    }
    _weather_cache[cache_key] = day_data
    return day_data


def _three_hour_start(state_time):
    """Input: state_time
    Output: start time of its 3-hour block"""
    start_hour = state_time.hour - state_time.hour % 3
    return state_time.replace(
        hour=start_hour,
        minute=0,
        second=0,
        microsecond=0,
    )


def _past_ap(ap_by_time, current_time, hours_before):
    """Input: {ap_by_time, current_time, hours_before}
    Output: one Ap value"""
    wanted_time = current_time - timedelta(hours=hours_before)
    return ap_by_time[wanted_time]


def _average_past_ap(ap_by_time, current_time, first_hour, last_hour):
    """Input: {ap_by_time, current_time, first_hour, last_hour}
    Output: average Ap value"""
    values = []

    for hours_before in range(first_hour, last_hour + 1, 3):
        values.append(_past_ap(ap_by_time, current_time, hours_before))

    return sum(values) / len(values)


def load_space_weather(state, file_path=DEFAULT_FILE):
    """Input: state
    Output: state + {f107_sfu, f107a_sfu, ap_values, f107_data_type}

    ap_values = [daily, now, -3h, -6h, -9h, avg_12_to_33h, avg_36_to_57h]
    """
    state_time = state["time"].astimezone(timezone.utc)
    day_data = _load_day_data(state_time, file_path)
    rows = day_data["rows"]

    current_day = state_time.date()
    previous_day = current_day - timedelta(days=1)

    if current_day not in rows or previous_day not in rows:
        raise ValueError(f"No space-weather data for {current_day}.")

    current_row = rows[current_day]
    previous_row = rows[previous_day]
    ap_by_time = day_data["ap_by_time"]
    current_ap_time = _three_hour_start(state_time)

    ap_values = [
        float(current_row["AP_AVG"]),
        _past_ap(ap_by_time, current_ap_time, 0),
        _past_ap(ap_by_time, current_ap_time, 3),
        _past_ap(ap_by_time, current_ap_time, 6),
        _past_ap(ap_by_time, current_ap_time, 9),
        _average_past_ap(ap_by_time, current_ap_time, 12, 33),
        _average_past_ap(ap_by_time, current_ap_time, 36, 57),
    ]

    state_with_weather = state.copy()
    state_with_weather["f107_sfu"] = float(previous_row["F10.7_OBS"])
    state_with_weather["f107a_sfu"] = float(
        current_row["F10.7_OBS_CENTER81"]
    )
    state_with_weather["ap_values"] = ap_values
    state_with_weather["f107_data_type"] = previous_row["F10.7_DATA_TYPE"]
    return state_with_weather
