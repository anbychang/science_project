"""Check the P1.5 checkpoint and downstream-rebuild boundary."""

import sqlite3

import pytest

from phases.phase0.code.data.database.prep_raw_schema import create_tables
from phases.phase1.code.prep_03_orbital_elements import (
    create_orbital_element_table,
)
from phases.phase1.code.prep_04_mean_orbit import (
    MEAN_ORBIT_ELEMENTS_TABLE,
    MEAN_ORBIT_ELEMENT_FIELDS,
    create_mean_orbit_elements_table,
    create_mean_orbit_table,
)
from phases.phase1.code.prep_05_pod_quality import create_quality_table
from phases.phase1.code.prep_mean_orbit_checkpoint import (
    CHECKPOINT_STAGE,
    CHECKPOINT_STAGE_METADATA,
    checkpoint_mean_orbit_database,
    write_downstream_from_mean_orbit,
)


def write_completed_mean_orbit_database(database_path):
    """Input: absent SQLite path
    Output: one complete P1.5 database for checkpoint tests"""
    with sqlite3.connect(database_path) as connection:
        create_tables(connection)
        create_orbital_element_table(connection)
        create_quality_table(connection)
        create_mean_orbit_table(connection)
        create_mean_orbit_elements_table(connection)
        connection.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [
                ("mean_orbit_elements_table", MEAN_ORBIT_ELEMENTS_TABLE),
                ("mean_orbit_elements_start_time_us", "1"),
                ("mean_orbit_elements_stop_time_us", "2"),
            ],
        )
        connection.execute("INSERT INTO source_files VALUES (1, 'pod.sp3', 'sig')")
        connection.execute(
            "INSERT INTO swarm_a_pod_source_provenance VALUES (1, 'ITRF', 1, 2, 1, 10.0, 'UTC')"
        )
        connection.execute("INSERT INTO swarm_a_states VALUES (1, 1, 2, 3, 4, 5, 6, 1, 1)")
        connection.execute(
            "INSERT INTO swarm_a_orbital_elements VALUES (1, 7000000.0, NULL)"
        )
        connection.execute("INSERT INTO swarm_a_pod_quality VALUES (1, 1, NULL, 1)")
        connection.execute(
            "INSERT INTO swarm_a_mean_orbital_elements VALUES (1, 7000001.0, NULL)"
        )
        connection.execute(
            f"INSERT INTO {MEAN_ORBIT_ELEMENTS_TABLE} VALUES "
            f"({', '.join('?' for _ in range(len(MEAN_ORBIT_ELEMENT_FIELDS) + 2))})",
            (1, 7000002.0, *([None] * (len(MEAN_ORBIT_ELEMENT_FIELDS) - 1)), None),
        )


def test_checkpoint_copies_completed_p1_5_without_changing_source(tmp_path):
    """Input: one completed P1.5 database
    Output: independent checkpoint with an explicit P1.5 marker"""
    source_path = tmp_path / "source.sqlite"
    checkpoint_path = tmp_path / "mean_orbit.sqlite"
    write_completed_mean_orbit_database(source_path)

    result = checkpoint_mean_orbit_database(source_path, checkpoint_path)

    assert result["mean_orbit_rows"] == 1
    with sqlite3.connect(source_path) as source_connection:
        assert source_connection.execute(
            "SELECT count(*) FROM metadata WHERE name = ?", (CHECKPOINT_STAGE_METADATA,)
        ).fetchone()[0] == 0
    with sqlite3.connect(checkpoint_path) as checkpoint_connection:
        assert checkpoint_connection.execute(
            "SELECT value FROM metadata WHERE name = ?", (CHECKPOINT_STAGE_METADATA,)
        ).fetchone() == (CHECKPOINT_STAGE,)
        assert checkpoint_connection.execute(
            f"SELECT mean_semi_major_axis_m FROM {MEAN_ORBIT_ELEMENTS_TABLE}"
        ).fetchone() == (7000002.0,)


def test_downstream_rebuild_copies_checkpoint_before_running_writers(tmp_path, monkeypatch):
    """Input: a P1.5 checkpoint and absent downstream target
    Output: writers receive only the copied target database"""
    source_path = tmp_path / "source.sqlite"
    checkpoint_path = tmp_path / "mean_orbit.sqlite"
    target_path = tmp_path / "analysis.sqlite"
    write_completed_mean_orbit_database(source_path)
    checkpoint_mean_orbit_database(source_path, checkpoint_path)
    calls = []

    def record(name):
        return lambda *arguments: calls.append((name, *arguments)) or {"name": name}

    monkeypatch.setattr(
        "phases.phase1.code.prep_mean_orbit_checkpoint.write_orbit_10min",
        record("orbit"),
    )
    monkeypatch.setattr(
        "phases.phase1.code.prep_mean_orbit_checkpoint.write_decay_rates",
        record("decay"),
    )
    monkeypatch.setattr(
        "phases.phase1.code.prep_mean_orbit_checkpoint.write_analysis_10min",
        record("analysis"),
    )
    monkeypatch.setattr(
        "phases.phase1.code.prep_mean_orbit_checkpoint.write_scoped_v1_release_metadata",
        record("audit"),
    )

    result = write_downstream_from_mean_orbit(checkpoint_path, target_path)

    assert result["database_path"] == target_path
    assert calls == [
        ("orbit", target_path, MEAN_ORBIT_ELEMENTS_TABLE, 1, 2),
        ("decay", target_path),
        ("analysis", target_path),
        ("audit", target_path, 1, 2),
    ]
    with sqlite3.connect(target_path) as target_connection:
        assert target_connection.execute(
            f"SELECT count(*) FROM {MEAN_ORBIT_ELEMENTS_TABLE}"
        ).fetchone()[0] == 1


def test_downstream_accepts_unmarked_completed_p1_5_baseline(tmp_path, monkeypatch):
    """Input: completed P1.5 baseline without checkpoint marker
    Output: downstream writers run against an independent full copy"""
    source_path = tmp_path / "p1_5.sqlite"
    target_path = tmp_path / "p1_7.sqlite"
    write_completed_mean_orbit_database(source_path)
    monkeypatch.setattr(
        "phases.phase1.code.prep_mean_orbit_checkpoint.write_orbit_10min",
        lambda *arguments: None,
    )
    monkeypatch.setattr(
        "phases.phase1.code.prep_mean_orbit_checkpoint.write_decay_rates",
        lambda *arguments: None,
    )
    monkeypatch.setattr(
        "phases.phase1.code.prep_mean_orbit_checkpoint.write_analysis_10min",
        lambda *arguments: None,
    )
    monkeypatch.setattr(
        "phases.phase1.code.prep_mean_orbit_checkpoint.write_scoped_v1_release_metadata",
        lambda *arguments: None,
    )

    write_downstream_from_mean_orbit(source_path, target_path)

    with sqlite3.connect(source_path) as source_connection:
        assert source_connection.execute(
            "SELECT count(*) FROM metadata WHERE name = ?", (CHECKPOINT_STAGE_METADATA,)
        ).fetchone()[0] == 0
    with sqlite3.connect(target_path) as target_connection:
        assert target_connection.execute(
            f"SELECT count(*) FROM {MEAN_ORBIT_ELEMENTS_TABLE}"
        ).fetchone()[0] == 1


def test_checkpoint_rejects_missing_mean_orbit_rows(tmp_path):
    """Input: P1.5 database missing a usable mean-orbit result
    Output: no checkpoint is created"""
    source_path = tmp_path / "source.sqlite"
    checkpoint_path = tmp_path / "mean_orbit.sqlite"
    write_completed_mean_orbit_database(source_path)
    with sqlite3.connect(source_path) as connection:
        connection.execute(f"DELETE FROM {MEAN_ORBIT_ELEMENTS_TABLE}")

    with pytest.raises(ValueError, match="v1 mean-orbit table is empty"):
        checkpoint_mean_orbit_database(source_path, checkpoint_path)

    assert not checkpoint_path.exists()


def test_downstream_rejects_rejected_v1_row_before_copy(tmp_path):
    """Input: P1.5 with a rejected usable v1 row
    Output: no downstream copy is created"""
    source_path = tmp_path / "p1_5.sqlite"
    target_path = tmp_path / "p1_7.sqlite"
    write_completed_mean_orbit_database(source_path)
    with sqlite3.connect(source_path) as connection:
        connection.execute(
            f"UPDATE {MEAN_ORBIT_ELEMENTS_TABLE} SET rejection_reason = 'failed'"
        )

    with pytest.raises(ValueError, match="1 missing or rejected v1"):
        write_downstream_from_mean_orbit(source_path, target_path)

    assert not target_path.exists()
