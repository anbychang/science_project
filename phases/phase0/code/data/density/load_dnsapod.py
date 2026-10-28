"""Read native Swarm-A DNSAPOD density samples from one ZIP."""

import math
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import cdflib
import numpy as np


def load_dnsapod(zip_path: Path) -> dict:
    """Input: one DNSAPOD ZIP. Output: {raw_count, flag_counts, samples: [{time_us, ...}]}.

    Keep nominal samples with valid location and at least one positive density field.
    """
    with ZipFile(zip_path) as archive:
        cdf_names = [name for name in archive.namelist() if name.lower().endswith(".cdf")]
        if len(cdf_names) != 1:
            raise ValueError(f"Expected one DNSAPOD CDF in {zip_path}")
        with TemporaryDirectory() as temporary_folder:
            cdf_path = archive.extract(cdf_names[0], temporary_folder)
            density_cdf = cdflib.CDF(cdf_path)
            try:
                source = {
                    "time": cdflib.cdfepoch.to_datetime(density_cdf.varget("time")),
                    "density": density_cdf.varget("density"),
                    "density_orbitmean": density_cdf.varget("density_orbitmean"),
                    "altitude": density_cdf.varget("altitude"),
                    "latitude": density_cdf.varget("latitude"),
                    "longitude": density_cdf.varget("longitude"),
                    "validity_flag": density_cdf.varget("validity_flag"),
                }
            finally:
                # cdflib has no public close method; release the Windows file handle.
                density_cdf._f.close()
                del density_cdf
    counts = {name: len(values) for name, values in source.items()}
    if len(set(counts.values())) != 1:
        raise ValueError(f"DNSAPOD CDF columns have different lengths: {zip_path}")
    flags = {}
    samples = []
    for index in range(counts["time"]):
        flag = int(source["validity_flag"][index])
        flags[flag] = flags.get(flag, 0) + 1
        if flag != 0:
            continue
        density = float(source["density"][index])
        orbitmean = float(source["density_orbitmean"][index])
        altitude = float(source["altitude"][index])
        latitude = float(source["latitude"][index])
        longitude = float(source["longitude"][index])
        valid_density = math.isfinite(density) and density > 0
        valid_orbitmean = math.isfinite(orbitmean) and orbitmean > 0
        if not (valid_density or valid_orbitmean):
            continue
        if not (math.isfinite(altitude) and altitude > 0 and math.isfinite(latitude)
                and -90 <= latitude <= 90 and math.isfinite(longitude)):
            continue
        time_us = int(source["time"][index].astype("datetime64[us]").astype(np.int64))
        samples.append({
            "time_us": time_us,
            "latitude_deg": latitude,
            "longitude_deg": longitude,
            "altitude_m": altitude,
            "rho_l2_kg_m3": density if valid_density else None,
            "rho_l2_orbitmean_kg_m3": orbitmean if valid_orbitmean else None,
            "validity_flag": flag,
            "source_file": zip_path.name,
        })
    return {"raw_count": counts["time"], "flag_counts": flags, "samples": samples}
