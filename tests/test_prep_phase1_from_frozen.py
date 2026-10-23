import sqlite3

from satellite_orbit.data.database.prep_raw_schema import create_tables
from satellite_orbit.data.pod.prep_03_orbital_elements import (
    create_orbital_element_table,
)
from satellite_orbit.data.pod.prep_04_mean_orbit import (
    create_mean_orbit_table,
    mean_orbit_metadata,
)
from satellite_orbit.data.pod.prep_05_pod_quality import create_quality_table
from satellite_orbit.phase1.prep_phase1_from_frozen import (
    create_p1_5_base,
    write_p1_6_outputs,
)


def write_frozen_source(database_path):
    """Input: SQLite path
    Output: frozen source through P1.5 for a copy test"""
    connection = sqlite3.connect(database_path)
    try:
        create_tables(connection)
        create_orbital_element_table(connection)
        create_quality_table(connection)
        create_mean_orbit_table(connection)
        connection.execute("INSERT INTO source_files VALUES (1, 'pod.sp3', 'sig')")
        connection.execute(
            "INSERT INTO swarm_a_pod_source_provenance VALUES (1, 'ITRF', 1, 2, 1, 10.0, 'UTC')"
        )
        connection.execute(
            "INSERT INTO swarm_a_states VALUES (1, 1, 2, 3, 4, 5, 6, 1, 1)"
        )
        connection.execute(
            "INSERT INTO swarm_a_orbital_elements VALUES (1, 7000000.0, NULL)"
        )
        connection.execute("INSERT INTO swarm_a_pod_quality VALUES (1, 1, NULL, 1)")
        connection.execute(
            "INSERT INTO swarm_a_mean_orbital_elements VALUES (1, 7000001.0, NULL)"
        )
        connection.execute(
            "INSERT INTO space_weather VALUES (1, 70, 71, 72, 3, 4, 5, 6, 7, 8, 9, 'OBS')"
        )
        connection.execute("INSERT INTO geomagnetic VALUES (1, -10, 20, 1, 1)")
        metadata = dict(mean_orbit_metadata())
        metadata["mean_orbit_algorithm"] = "frozen-test"
        metadata["mean_orbit_implementation_fingerprint"] = "frozen-test"
        metadata["p1_4_quality_policy_version"] = "test"
        connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
        connection.commit()
    finally:
        connection.close()


def test_create_p1_5_base_copies_only_frozen_inputs_and_mean_cache(tmp_path):
    frozen_path = tmp_path / "frozen.sqlite"
    target_path = tmp_path / "p1_5_base.sqlite"
    write_frozen_source(frozen_path)

    result = create_p1_5_base(target_path, frozen_path)

    assert result["mean_orbit_rows"] == 1
    connection = sqlite3.connect(target_path)
    try:
        assert connection.execute("SELECT count(*) FROM swarm_a_states").fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM swarm_a_mean_orbital_elements"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE name = 'swarm_a_orbit_10min'"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_write_p1_6_outputs_creates_empty_tables_when_no_10min_bin_exists(tmp_path):
    frozen_path = tmp_path / "frozen.sqlite"
    target_path = tmp_path / "p1_5_base.sqlite"
    write_frozen_source(frozen_path)
    create_p1_5_base(target_path, frozen_path)

    result = write_p1_6_outputs(target_path)

    assert result["analysis"]["stored_rows"] == 0
    connection = sqlite3.connect(target_path)
    try:
        assert connection.execute(
            "SELECT count(*) FROM swarm_a_orbit_10min"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM swarm_a_orbit_decay_10min"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM swarm_a_analysis_10min"
        ).fetchone()[0] == 0
    finally:
        connection.close()
