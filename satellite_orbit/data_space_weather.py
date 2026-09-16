"""Read space-weather data and align it with orbital-response data."""

import csv
from datetime import datetime
from pathlib import Path


def load_space_weather_csv(file_path):
    """Input: space weather CSV
    Output: [{time, sym_h_nT, ae_nT, f10_7_sfu, f10_7a_sfu}, ...]"""
    weather_points = []

    with Path(file_path).open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            weather_points.append(
                {
                    "time": datetime.fromisoformat(
                        row["time_utc"].replace("Z", "+00:00")
                    ),
                    "sym_h_nT": float(row["sym_h_nT"]),
                    "ae_nT": float(row["ae_nT"]),
                    "f10_7_sfu": float(row["f10_7_sfu"]),
                    "f10_7a_sfu": float(row["f10_7a_sfu"]),
                }
            )

    return weather_points


def align_orbit_and_weather(orbital_response, weather_points):
    """Input: {orbital_response, weather_points}
    Output: [{time, a_mean_km, a_dot_km_s, sym_h_nT, ...}, ...]"""
    weather_by_time = {}
    for weather_point in weather_points:
        weather_by_time[weather_point["time"]] = weather_point

    aligned_rows = []
    previous_sym_h = None
    previous_time = None

    for index, time in enumerate(orbital_response["time"]):
        a_mean_km = orbital_response["a_mean_km"][index]
        weather_point = weather_by_time.get(time)

        if a_mean_km is None or weather_point is None:
            continue

        sym_h_rate_nT_s = None
        if previous_sym_h is not None:
            elapsed_s = (time - previous_time).total_seconds()
            sym_h_rate_nT_s = (
                weather_point["sym_h_nT"] - previous_sym_h
            ) / elapsed_s

        aligned_rows.append(
            {
                "time": time,
                "a_mean_km": a_mean_km,
                "a_dot_km_s": orbital_response["a_dot_km_s"][index],
                "sym_h_nT": weather_point["sym_h_nT"],
                "sym_h_rate_nT_s": sym_h_rate_nT_s,
                "ae_nT": weather_point["ae_nT"],
                "f10_7_sfu": weather_point["f10_7_sfu"],
                "f10_7a_sfu": weather_point["f10_7a_sfu"],
            }
        )

        previous_sym_h = weather_point["sym_h_nT"]
        previous_time = time

    return aligned_rows
