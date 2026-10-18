"""Build a fresh Phase 1 SQLite release without replacing a working database."""

import sys
from pathlib import Path

from satellite_orbit.data.database.prep_raw_database import write_sqlite_database
from satellite_orbit.data.pod.prep_02_source_provenance import write_database_provenance
from satellite_orbit.data.pod.prep_03_orbital_elements import write_orbital_elements
from satellite_orbit.data.pod.prep_04_mean_orbit import write_mean_orbits
from satellite_orbit.data.pod.prep_mean_orbit_cache import (
    copy_verified_mean_orbit_cache,
    copy_verified_orbital_element_cache,
)
from satellite_orbit.data.pod.prep_05_pod_quality import write_pod_quality
from satellite_orbit.data.pod.prep_06_orbit_10min import write_orbit_10min
from satellite_orbit.data.pod.prep_07_decay_rate import write_decay_rates
from satellite_orbit.phase1.prep_08_analysis_10min import write_analysis_10min
from satellite_orbit.phase1.prep_09_release_audit import write_release_metadata


def write_mean_orbit_stage(database_path, cache_database_path):
    """Input: target SQLite path and optional verified mean-orbit cache
    Output: mean orbit calculated or copied after verification"""
    if cache_database_path is not None:
        return copy_verified_mean_orbit_cache(database_path, cache_database_path)
    return write_mean_orbits(database_path, rebuild=True)


def default_stages(
    rebuild_evidence,
    mean_orbit_cache_database=None,
    orbital_element_cache_database=None,
):
    """Input: explicit rebuild evidence and optional mean-orbit cache
    Output: ordered {(name, writer), ...} for a new Phase 1 database"""
    return (
        ("01_raw", write_sqlite_database),
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
    """Input: absent target path, optional stages, and optional mean-orbit cache
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
    """Input: python -m satellite_orbit.phase1.prep_phase1_rebuild NEW_DATABASE [MEAN_CACHE]
    Output: fresh Phase 1 rebuild summary"""
    arguments = sys.argv[1:]
    if len(arguments) not in (1, 2):
        raise ValueError("Usage: NEW_DATABASE [CACHE_DATABASE]")
    cache_database_path = arguments[1] if len(arguments) == 2 else None
    result = write_phase1_rebuild(
        arguments[0],
        mean_orbit_cache_database=cache_database_path,
        orbital_element_cache_database=cache_database_path,
    )
    print(f"Fresh database: {result['database_path']}")
    print(f"Stages: {', '.join(result['stages'])}")


if __name__ == "__main__":
    main()
