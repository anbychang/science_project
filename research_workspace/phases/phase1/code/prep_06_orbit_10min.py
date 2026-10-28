"""Write chunk-local 10-minute means from Swarm-A mean-orbit rows."""

import sys
from pathlib import Path

from research_workspace.phases.phase0.code.data.database.prep_raw_schema import connect_database


DEFAULT_DATABASE = Path("research_workspace/phases/phase1/data/sqlite/swarm_a_analysis.sqlite")
MEAN_ORBIT_TABLE = "swarm_a_mean_orbital_elements"
MEAN_ORBIT_ELEMENTS_V1_TABLE = "swarm_a_mean_orbit_elements_v1"
BIN_DURATION_US = 600_000_000
MINIMUM_POD_COUNT = 56
MAXIMUM_POD_GAP_S = 10.0
ALGORITHM_VERSION = "utc_10min_mean_brouwer_lyddane_v1"


def create_orbit_10min_table(connection):
    """Input: SQLite connection
    Output: 10-minute orbit table exists"""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_a_orbit_10min (
            time_us INTEGER PRIMARY KEY,
            semi_major_axis_orbit_mean_m REAL NOT NULL,
            pod_count INTEGER NOT NULL,
            max_pod_gap_s REAL NOT NULL,
            chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        )
        """
    )


def incomplete_mean_orbit_count(connection, mean_orbit_table, start_time_us, stop_time_us):
    """Input: SQLite connection
    Output: usable POD rows without a usable mean-orbit result"""
    return connection.execute(
        """
        SELECT count(*)
        FROM swarm_a_pod_quality AS quality
        LEFT JOIN {mean_orbit_table} AS mean
            ON mean.time_us = quality.time_us
        WHERE quality.is_usable = 1
          AND quality.time_us >= ?
          AND quality.time_us < ?
          AND (
              mean.time_us IS NULL
              OR mean.mean_semi_major_axis_m IS NULL
              OR mean.rejection_reason IS NOT NULL
          )
        """.format(mean_orbit_table=mean_orbit_table),
        (start_time_us, stop_time_us),
    ).fetchone()[0]


def orbit_bin_query(mean_orbit_table):
    """Input: none
    Output: SQL rows {time_us, mean_a, pod_count, max_gap_s, chunk_id}"""
    return """
        WITH source AS (
            SELECT
                quality.chunk_id,
                mean.time_us,
                mean.mean_semi_major_axis_m,
                LAG(mean.time_us) OVER (
                    PARTITION BY quality.chunk_id
                    ORDER BY mean.time_us
                ) AS previous_time_us
            FROM {mean_orbit_table} AS mean
            JOIN swarm_a_pod_quality AS quality
                ON quality.time_us = mean.time_us
            WHERE quality.is_usable = 1
              AND quality.chunk_id IS NOT NULL
              AND mean.mean_semi_major_axis_m IS NOT NULL
              AND mean.rejection_reason IS NULL
        ), bins AS (
            SELECT
                ((time_us / ?) + 1) * ? AS time_us,
                avg(mean_semi_major_axis_m) AS semi_major_axis_orbit_mean_m,
                count(*) AS pod_count,
                coalesce(
                    max((time_us - previous_time_us) / 1000000.0), 0.0
                ) AS max_pod_gap_s,
                chunk_id
            FROM source
            GROUP BY chunk_id, ((time_us / ?) + 1) * ?
        ), bounded_bins AS (
            SELECT
                bins.*,
                min(time_us) OVER (PARTITION BY chunk_id) AS first_time_us,
                max(time_us) OVER (PARTITION BY chunk_id) AS last_time_us
            FROM bins
        )
        SELECT
            time_us,
            semi_major_axis_orbit_mean_m,
            pod_count,
            max_pod_gap_s,
            chunk_id
        FROM bounded_bins
        WHERE pod_count >= ?
          AND max_pod_gap_s <= ?
          AND (
              pod_count = 60
              OR time_us = first_time_us
              OR time_us = last_time_us
          )
        ORDER BY time_us
    """.format(mean_orbit_table=mean_orbit_table)


def orbit_bin_parameters():
    """Input: none
    Output: parameters for orbit_bin_query"""
    return (
        BIN_DURATION_US,
        BIN_DURATION_US,
        BIN_DURATION_US,
        BIN_DURATION_US,
        MINIMUM_POD_COUNT,
        MAXIMUM_POD_GAP_S,
    )


def orbit_insert_query(mean_orbit_table):
    """Input: none
    Output: SQL insert with the fixed algorithm version"""
    return (
        """
        INSERT INTO swarm_a_orbit_10min (
            time_us,
            semi_major_axis_orbit_mean_m,
            pod_count,
            max_pod_gap_s,
            chunk_id,
            algorithm_version
        )
        SELECT
            time_us,
            semi_major_axis_orbit_mean_m,
            pod_count,
            max_pod_gap_s,
            chunk_id,
            ?
        FROM (
        """
        + orbit_bin_query(mean_orbit_table)
        + ")"
    )


def orbit_insert_parameters():
    """Input: none
    Output: parameters for orbit_insert_query"""
    return (
        ALGORITHM_VERSION,
        BIN_DURATION_US,
        BIN_DURATION_US,
        BIN_DURATION_US,
        BIN_DURATION_US,
        MINIMUM_POD_COUNT,
        MAXIMUM_POD_GAP_S,
    )


def write_metadata(connection):
    """Input: SQLite connection
    Output: 10-minute bin contract is stored"""
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("orbit_10min_algorithm", ALGORITHM_VERSION),
            (
                "orbit_10min_bin_contract",
                "[end-600s,end); >=56 rows; <=10s gap; 56-59 only chunk edge",
            ),
        ],
    )


def write_orbit_10min(
    database_path=DEFAULT_DATABASE,
    mean_orbit_table=MEAN_ORBIT_TABLE,
    start_time_us=0,
    stop_time_us=2**63 - 1,
):
    """Input: SQLite path with complete mean-orbit rows
    Output: {input_rows, stored_rows}"""
    database_path = Path(database_path)
    if mean_orbit_table not in (MEAN_ORBIT_TABLE, MEAN_ORBIT_ELEMENTS_V1_TABLE):
        raise ValueError(f"Unsupported mean-orbit table: {mean_orbit_table}")
    connection = connect_database(database_path)
    try:
        with connection:
            create_orbit_10min_table(connection)
            incomplete_rows = incomplete_mean_orbit_count(
                connection, mean_orbit_table, start_time_us, stop_time_us
            )
            if incomplete_rows:
                raise ValueError(
                    "Cannot bin POD while "
                    f"{incomplete_rows} usable mean-orbit rows are incomplete."
                )

            input_rows = connection.execute(
                f"SELECT count(*) FROM {mean_orbit_table} WHERE time_us >= ? AND time_us < ?",
                (start_time_us, stop_time_us),
            ).fetchone()[0]
            candidate_bins = connection.execute(
                "SELECT count(*) FROM (" + orbit_bin_query(mean_orbit_table) + ")",
                orbit_bin_parameters(),
            ).fetchone()[0]
            connection.execute("DELETE FROM swarm_a_orbit_10min")
            connection.execute(
                orbit_insert_query(mean_orbit_table), orbit_insert_parameters()
            )
            write_metadata(connection)
    finally:
        connection.close()

    return {
        "input_rows": input_rows,
        "stored_rows": candidate_bins,
    }


def main():
    """Input: python -m research_workspace.phases.phase1.code.prep_06_orbit_10min
    Output: 10-minute orbit write summary"""
    if sys.argv[1:]:
        raise ValueError("Usage: no arguments")
    result = write_orbit_10min()
    print(f"Mean-orbit input rows: {result['input_rows']}")
    print(f"10-minute rows written: {result['stored_rows']}")


if __name__ == "__main__":
    main()
