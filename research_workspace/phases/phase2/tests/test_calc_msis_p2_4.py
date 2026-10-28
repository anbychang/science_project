"""Check the CelesTrak solar drivers used by P2.3 and P2.4."""

import json
from datetime import date, timedelta

from research_workspace.phases.phase0.code.calculation.density.calc_msis_p2_4 import (
    load_msis_weather,
)


def write_weather_files(folder, replacement_type: str) -> tuple:
    """Input: temp folder and one F10.7 type. Output: minimal GFZ/solar source paths."""
    gfz_path = folder / "gfz.json"
    gfz_path.write_text(json.dumps({"datetime": [], "ap": [], "status": []}), encoding="utf-8")
    solar_path = folder / "solar.csv"
    header = "DATE,F10.7_OBS,F10.7_DATA_TYPE,F10.7_OBS_CENTER81\n"
    start = date(2024, 1, 1)
    rows = []
    for offset in range(12):
        source_type = replacement_type if offset == 10 else "OBS"
        rows.append(f"{(start + timedelta(days=offset)).isoformat()},100.0,{source_type},150.0\n")
    solar_path.write_text(header + "".join(rows), encoding="utf-8")
    return gfz_path, solar_path


def test_int_f107_is_usable_but_prediction_is_not(tmp_path) -> None:
    """Input: current and prior INT or PRD days. Output: only observed/interpolated drivers."""
    target_days = (date(2024, 1, 11), date(2024, 1, 12))
    int_paths = write_weather_files(tmp_path, "INT")
    int_weather = load_msis_weather(*int_paths)
    assert all(int_weather["daily_solar"][day] is not None for day in target_days)

    prd_paths = write_weather_files(tmp_path, "PRD")
    prd_weather = load_msis_weather(*prd_paths)
    assert all(prd_weather["daily_solar"].get(day) is None for day in target_days)


def test_f107a_uses_source_center81_without_recalculating(tmp_path) -> None:
    """Input: daily CSV with distinct center81. Output: same-day source value and prior F10.7."""
    weather = load_msis_weather(*write_weather_files(tmp_path, "OBS"))
    drivers = weather["daily_solar"][date(2024, 1, 2)]

    assert drivers["f107_sfu"] == 100.0
    assert drivers["f107a_sfu"] == 150.0
    assert drivers["f107_day_utc"] == "2024-01-01"


def test_f107a_requires_current_day_source_row(tmp_path) -> None:
    """Input: first source day. Output: no previous-day solar driver."""
    weather = load_msis_weather(*write_weather_files(tmp_path, "OBS"))

    assert weather["daily_solar"][date(2024, 1, 1)] is None
