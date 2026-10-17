"""Load one local Swarm DNSAACC density ZIP file."""

from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import cdflib

DENSITY_FILL_VALUE = 1e30


def _time_from_cdf(cdf_time):
    """Input: CDF time as numpy datetime64
    Output: UTC datetime"""
    time_text = str(cdf_time)[:26]
    return datetime.fromisoformat(time_text).replace(tzinfo=timezone.utc)


def load_swarm_density(zip_path):
    """Input: Swarm DNSAACC ZIP path
    Output: [{time, density_kg_m3, altitude_m, latitude_deg, longitude_deg}, ...]"""
    with ZipFile(zip_path) as zip_file:
        cdf_name = next(
            (name for name in zip_file.namelist() if name.lower().endswith(".cdf")),
            None,
        )
        if cdf_name is None:
            raise ValueError("No CDF file found in the density ZIP.")
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
    for time, density, altitude_m, latitude_deg, longitude_deg, local_solar_time_h in zip(
        times,
        densities,
        altitudes_m,
        latitudes_deg,
        longitudes_deg,
        local_solar_times_h,
    ):
        density_kg_m3 = float(density)
        if not 0.0 < density_kg_m3 < DENSITY_FILL_VALUE:
            continue
        density_points.append(
            {
                "time": _time_from_cdf(time),
                "density_kg_m3": density_kg_m3,
                "altitude_m": float(altitude_m),
                "latitude_deg": float(latitude_deg),
                "longitude_deg": float(longitude_deg),
                "local_solar_time_h": float(local_solar_time_h),
            }
        )
    return density_points
