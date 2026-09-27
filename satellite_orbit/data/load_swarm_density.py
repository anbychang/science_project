"""Load one local Swarm DNSAACC density ZIP file."""

from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import cdflib

DENSITY_FILL_VALUE = 1e30


def _cdf_name(zip_file):
    """Input: density ZIP
    Output: CDF file name inside the ZIP"""
    for file_name in zip_file.namelist():
        if file_name.lower().endswith(".cdf"):
            return file_name
    raise ValueError("No CDF file found in the density ZIP.")


def _time_from_cdf(cdf_time):
    """Input: CDF time as numpy datetime64
    Output: UTC datetime"""
    time_text = str(cdf_time)[:26]
    return datetime.fromisoformat(time_text).replace(tzinfo=timezone.utc)


def load_swarm_density(zip_path):
    """Input: Swarm DNSAACC ZIP path
    Output: [{time, density_kg_m3, altitude_m, latitude_deg, longitude_deg}, ...]"""
    with ZipFile(zip_path) as zip_file:
        cdf_name = _cdf_name(zip_file)
        with TemporaryDirectory() as temporary_folder:
            cdf_path = zip_file.extract(cdf_name, temporary_folder)
            density_cdf = cdflib.CDF(cdf_path)
            times = cdflib.cdfepoch.to_datetime(density_cdf.varget("time"))
            densities = density_cdf.varget("density")
            altitudes_m = density_cdf.varget("altitude")
            latitudes_deg = density_cdf.varget("latitude")
            longitudes_deg = density_cdf.varget("longitude")
            local_solar_times_h = density_cdf.varget("local_solar_time")
            del density_cdf

    density_points = []
    for index in range(len(times)):
        density_kg_m3 = float(densities[index])
        if density_kg_m3 <= 0.0 or density_kg_m3 >= DENSITY_FILL_VALUE:
            continue
        density_points.append(
            {
                "time": _time_from_cdf(times[index]),
                "density_kg_m3": density_kg_m3,
                "altitude_m": float(altitudes_m[index]),
                "latitude_deg": float(latitudes_deg[index]),
                "longitude_deg": float(longitudes_deg[index]),
                "local_solar_time_h": float(local_solar_times_h[index]),
            }
        )

    return density_points
