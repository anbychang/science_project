"""Build a fresh Phase 1 SQLite release without replacing a working database."""

import sys
from pathlib import Path

from satellite_orbit.data.database.prep_raw_database import write_sqlite_database
from satellite_orbit.data.pod.prep_derived_decay_rate import write_decay_rates
from satellite_orbit.data.pod.prep_derived_mean_orbit import write_mean_orbits
from satellite_orbit.data.pod.prep_derived_orbit_10min import write_orbit_10min
from satellite_orbit.data.pod.prep_derived_orbital_elements import write_orbital_elements
from satellite_orbit.data.pod.prep_derived_pod_quality import write_pod_quality
from satellite_orbit.data.pod.prep_source_provenance import write_database_provenance
from satellite_orbit.phase1.prep_derived_analysis_10min import write_analysis_10min
from satellite_orbit.phase1.prep_p1_7_release_audit import write_release_metadata


def default_stages(rebuild_evidence):
    """Input: explicit clean-rebuild evidence
    Output: ordered {(name, writer), ...} for a new Phase 1 database"""
    return (
        ("raw", write_sqlite_database),
        ("provenance", write_database_provenance),
        ("p1_3_orbital_elements", write_orbital_elements),
        ("p1_4_quality", write_pod_quality),
        ("p1_5_mean_orbit", lambda path: write_mean_orbits(path, rebuild=True)),
        ("p1_5_orbit_10min", write_orbit_10min),
        ("p1_5_decay_rate", write_decay_rates),
        ("p1_6_analysis", write_analysis_10min),
        (
            "p1_7_release_audit",
            lambda path: write_release_metadata(
                path,
                clean_rebuild_evidence=rebuild_evidence,
            ),
        ),
    )


def write_phase1_rebuild(database_path, stages=None):
    """Input: absent target SQLite path and optional ordered stages
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
    selected_stages = default_stages(rebuild_evidence) if stages is None else stages
    completed_stages = []
    for name, writer in selected_stages:
        writer(database_path)
        completed_stages.append(name)

    return {"database_path": database_path, "stages": completed_stages}


def main():
    """Input: python -m satellite_orbit.phase1.prep_phase1_rebuild NEW_DATABASE
    Output: fresh Phase 1 rebuild summary"""
    arguments = sys.argv[1:]
    if len(arguments) != 1:
        raise ValueError("Usage: NEW_DATABASE")
    result = write_phase1_rebuild(arguments[0])
    print(f"Fresh database: {result['database_path']}")
    print(f"Stages: {', '.join(result['stages'])}")


if __name__ == "__main__":
    main()
