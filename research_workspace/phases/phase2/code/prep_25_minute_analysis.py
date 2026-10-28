"""Create the minute-resolution Phase 2 analysis view from P2.3 and P2.4 rows."""

import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from research_workspace.phases.phase0.code.data.density.down_swarm_density_pod import sha256_file


ALGORITHM_VERSION = "storm_minute_analysis_v2"
SOURCE_VERSION = "storm_density_t0_phase_v5"


@dataclass(frozen=True)
class MinuteAnalysisPaths:
    """Input: frozen P2.4 path. Output: new P2.5 checkpoint path record."""

    source: Path = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_4_density_t0_phase_v5.sqlite")
    output: Path = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_5_minute_analysis_v2.sqlite")


def minute_key_mismatches(database: sqlite3.Connection) -> tuple[int, int]:
    """Input: P2.3 feature and P2.4 density tables. Output: unmatched key counts both ways."""
    missing_density = database.execute("""
        SELECT count(*) FROM (
            SELECT storm_id,source_time_us FROM storm_minute_feature_v5
            EXCEPT
            SELECT storm_id,source_time_us FROM storm_density_1min_v5
        )
    """).fetchone()[0]
    missing_feature = database.execute("""
        SELECT count(*) FROM (
            SELECT storm_id,source_time_us FROM storm_density_1min_v5
            EXCEPT
            SELECT storm_id,source_time_us FROM storm_minute_feature_v5
        )
    """).fetchone()[0]
    return missing_density, missing_feature


def create_analysis_view(database: sqlite3.Connection) -> None:
    """Input: copied P2.4 SQLite. Output: minute-resolution P2.5 analysis view."""
    database.execute(f"""
        CREATE VIEW storm_minute_analysis_v2 AS
        SELECT
            feature.storm_id,
            feature.source_time_us,
            event.t0_time_us,
            event.symh_min_nt,
            event.compound,
            event.n_minima,
            event.phase_start_time_us,
            event.phase_end_time_us,
            event.phase_orbits_before,
            event.phase_orbits_after,
            feature.assumed_support_start_time_us,
            feature.assumed_support_end_time_us,
            feature.t_rel_h,
            feature.u_rad,
            feature.u_rel_rad,
            feature.mean_semi_major_axis_m,
            feature.phase_left_time_us,
            feature.phase_right_time_us,
            feature.chunk_id,
            feature.phase_status,
            feature.raw_3_rate_m_s,
            feature.raw_3_sigma_m_s,
            feature.raw_3_sample_count,
            feature.raw_3_reject_reason,
            feature.raw_5_rate_m_s,
            feature.raw_5_sigma_m_s,
            feature.raw_5_sample_count,
            feature.raw_5_reject_reason,
            feature.joint_3_rate_m_s,
            feature.joint_3_sigma_m_s,
            feature.joint_3_sample_count,
            feature.joint_3_reject_reason,
            feature.joint_5_rate_m_s,
            feature.joint_5_sigma_m_s,
            feature.joint_5_sample_count,
            feature.joint_5_reject_reason,
            feature.sme_nt,
            feature.symh_nt,
            feature.sme_station_count,
            feature.sme_not_before_time_us,
            feature.kyoto_not_before_time_us,
            feature.ap_step,
            feature.ap_source_end_time_us,
            feature.f107_sfu,
            feature.f107a_sfu,
            feature.core_ready_time_us,
            density.l2_valid_sample_count,
            density.paired_sample_count,
            density.orbitmean_valid_sample_count,
            density.rho_l2_kg_m3,
            density.rho_msis_kg_m3,
            density.rho_l2_orbitmean_kg_m3,
            density.log_ratio_obs,
            coverage.expected_30s_sample_count AS event_expected_30s_sample_count,
            coverage.l2_valid_sample_count AS event_l2_valid_sample_count,
            coverage.paired_sample_count AS event_paired_sample_count,
            coverage.l2_coverage AS event_l2_coverage,
            coverage.paired_coverage AS event_paired_coverage,
            coverage.is_valid_80pct AS event_is_valid_80pct,
            coverage.status AS storm_status,
            feature.algorithm_version AS feature_algorithm_version,
            density.algorithm_version AS density_algorithm_version,
            coverage.algorithm_version AS coverage_algorithm_version,
            '{ALGORITHM_VERSION}' AS algorithm_version
        FROM storm_minute_feature_v5 AS feature
        JOIN storm_density_1min_v5 AS density
          ON density.storm_id=feature.storm_id
         AND density.source_time_us=feature.source_time_us
        JOIN storm_event_t0_phase_v5 AS event
          ON event.storm_id=feature.storm_id
        JOIN storm_event_coverage_v5 AS coverage
          ON coverage.storm_id=feature.storm_id
    """)


def verify_output(database: sqlite3.Connection) -> dict:
    """Input: populated P2.5 SQLite. Output: checked minute, event, and mismatch counts."""
    missing_density, missing_feature = minute_key_mismatches(database)
    source_minutes = database.execute(
        "SELECT count(*) FROM storm_minute_feature_v5"
    ).fetchone()[0]
    analysis_minutes = database.execute(
        "SELECT count(*) FROM storm_minute_analysis_v2"
    ).fetchone()[0]
    events = database.execute(
        "SELECT count(DISTINCT storm_id) FROM storm_minute_analysis_v2"
    ).fetchone()[0]
    expected_events = database.execute(
        "SELECT count(*) FROM storm_event_t0_phase_v5"
    ).fetchone()[0]
    if missing_density or missing_feature:
        raise ValueError("P2.3 and P2.4 minute keys are not one-to-one.")
    if analysis_minutes != source_minutes or events != expected_events:
        raise ValueError("P2.5 view lost minute or event rows.")
    if database.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("P2.5 foreign-key check failed.")
    if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("P2.5 SQLite integrity check failed.")
    return {
        "minute_rows": analysis_minutes,
        "storms": events,
        "missing_density_keys": missing_density,
        "missing_feature_keys": missing_feature,
    }


def write_minute_analysis(paths: MinuteAnalysisPaths = MinuteAnalysisPaths()) -> dict:
    """Input: frozen P2.4 checkpoint. Output: copied P2.5 SQLite with checked analysis view."""
    if not paths.source.is_file():
        raise FileNotFoundError(paths.source)
    if paths.output.exists():
        raise FileExistsError(paths.output)
    source_hash = sha256_file(paths.source)
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=paths.output.stem + ".", suffix=".building", dir=paths.output.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(paths.source, temporary)
        if sha256_file(temporary) != source_hash:
            raise ValueError("P2.4 changed during copy.")
        with closing(sqlite3.connect(temporary)) as database:
            database.execute("PRAGMA foreign_keys=ON")
            version = database.execute(
                "SELECT value FROM phase2_metadata WHERE name='p2_4_algorithm_version'"
            ).fetchone()
            if version is None or version[0] != SOURCE_VERSION:
                raise ValueError("Input is not the current P2.4 checkpoint.")
            if minute_key_mismatches(database) != (0, 0):
                raise ValueError("P2.3 and P2.4 minute keys are not one-to-one.")
            with database:
                create_analysis_view(database)
                result = verify_output(database)
                database.executemany(
                    "INSERT INTO phase2_metadata VALUES (?,?)",
                    (("p2_5_algorithm_version", ALGORITHM_VERSION),
                     ("p2_5_source_sha256", source_hash),
                     ("p2_5_storage", "view"),
                     ("p2_5_minute_rows", str(result["minute_rows"])),
                     ("p2_5_storms", str(result["storms"])),
                     ("p2_5_missing_density_keys", "0"),
                     ("p2_5_missing_feature_keys", "0")),
                )
        if sha256_file(paths.source) != source_hash:
            raise ValueError("P2.4 source changed during build.")
        if paths.output.exists():
            raise FileExistsError("P2.5 output appeared during build.")
        os.rename(temporary, paths.output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return result


def main() -> None:
    """Input: optional P2.4 and P2.5 paths. Output: P2.5 row counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 2):
        raise SystemExit("Usage: python -m research_workspace.phases.phase2.code.prep_25_minute_analysis "
                         "[P2_4_DB OUTPUT_DB]")
    paths = MinuteAnalysisPaths(*map(Path, arguments)) if arguments else MinuteAnalysisPaths()
    print(write_minute_analysis(paths))


if __name__ == "__main__":
    main()
