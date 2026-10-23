"""Build a fresh Phase 1 SQLite release without replacing a working database."""

import sys
from pathlib import Path

from satellite_orbit.data.database.prep_raw_database import write_sqlite_database
from satellite_orbit.data.pod.prep_02_source_provenance import write_database_provenance
from satellite_orbit.data.pod.prep_03_orbital_elements import write_orbital_elements
from satellite_orbit.data.pod.prep_mean_orbit_cache import (
    copy_verified_mean_orbit_cache,
    copy_verified_orbital_element_cache,
)
from satellite_orbit.data.pod.prep_05_pod_quality import write_pod_quality
from satellite_orbit.data.pod.prep_06_orbit_10min import write_orbit_10min
from satellite_orbit.data.pod.prep_07_decay_rate import write_decay_rates
from satellite_orbit.phase1.prep_08_analysis_10min import write_analysis_10min
from satellite_orbit.phase1.prep_09_release_audit import write_release_metadata


def write_phase1_raw_database(database_path):
    """Input: new Phase 1 SQLite path.
    Output: raw POD, weather, and geomagnetic rows without Phase 2 density."""
    return write_sqlite_database(database_path)


def write_mean_orbit_stage(database_path, cache_database_path):
    """Input: target SQLite path and required verified P1.5 cache path.
    Output: verified mean-orbit rows copied without an Orekit calculation."""
    if cache_database_path is None:
        raise ValueError(
            "Phase 1 rebuild requires a P1.5 mean-orbit cache; "
            "normal rebuilds do not recompute Orekit mean elements."
        )
    return copy_verified_mean_orbit_cache(database_path, cache_database_path)


def default_stages(
    rebuild_evidence,
    mean_orbit_cache_database=None,
    orbital_element_cache_database=None,
):
    """Input: rebuild evidence, required P1.5 cache, optional P1.3 cache
    Output: ordered {(name, writer), ...} for a new Phase 1 database"""
    if mean_orbit_cache_database is None:
        raise ValueError(
            "Phase 1 rebuild requires a P1.5 mean-orbit cache; "
            "normal rebuilds do not recompute Orekit mean elements."
        )
    return (
        ("01_raw", write_phase1_raw_database),
        ("02_provenance", write_database_provenance),
        (
            "03_orbital_elements",
            lambda path: (
                copy_verified_orbital_element_cache(path, orbital_element_cache_database)
                if orbital_element_cache_database is not None
                else write_orbital_elements(path)
            ),
        ),
        ("04_quality", write_pod_quality),
        (
            "05_mean_orbit",
            lambda path: write_mean_orbit_stage(path, mean_orbit_cache_database),
        ),
        ("06_orbit_10min", write_orbit_10min),
        ("07_signed_rate", write_decay_rates),
        ("08_analysis", write_analysis_10min),
        (
            "09_release_audit",
            lambda path: write_release_metadata(
                path,
                clean_rebuild_evidence=rebuild_evidence,
            ),
        ),
    )


def write_phase1_rebuild(
    database_path,
    stages=None,
    mean_orbit_cache_database=None,
    orbital_element_cache_database=None,
):
    """Input: absent target path, optional stages, and required default P1.5 cache
    Output: {database_path, stages} after a fresh Phase 1 rebuild"""
    database_path = Path(database_path)
    if database_path.exists():
        raise ValueError(
            f"Fresh Phase 1 rebuild target already exists: {database_path}. "
            "Choose a new SQLite path."
        )
    rebuild_evidence = {
        "entry_point": "write_phase1_rebuild",
        "target_database": str(database_path),
    }
    if mean_orbit_cache_database is not None:
        rebuild_evidence["mean_orbit_cache_database"] = str(mean_orbit_cache_database)
    if orbital_element_cache_database is not None:
        rebuild_evidence["orbital_element_cache_database"] = str(
            orbital_element_cache_database
        )
    selected_stages = (
        default_stages(
            rebuild_evidence,
            mean_orbit_cache_database,
            orbital_element_cache_database,
        )
        if stages is None
        else stages
    )
    completed_stages = []
    for name, writer in selected_stages:
        writer(database_path)
        completed_stages.append(name)

    return {"database_path": database_path, "stages": completed_stages}


def main():
    """Input: python -m satellite_orbit.phase1.prep_phase1_rebuild NEW_DATABASE P1_5_CACHE
    Output: fresh Phase 1 rebuild summary"""
    arguments = sys.argv[1:]
    if len(arguments) != 2:
        raise ValueError("Usage: NEW_DATABASE P1_5_CACHE_DATABASE")
    cache_database_path = arguments[1]
    result = write_phase1_rebuild(
        arguments[0],
        mean_orbit_cache_database=cache_database_path,
        orbital_element_cache_database=cache_database_path,
    )
    print(f"Fresh database: {result['database_path']}")
    print(f"Stages: {', '.join(result['stages'])}")


if __name__ == "__main__":
    main()
