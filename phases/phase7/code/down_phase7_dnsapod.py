"""Download DNSAPOD days required by the configured Phase 7 storm set."""

import json
from datetime import datetime, timezone
from pathlib import Path

from phases.phase0.code.data.density.down_swarm_density_pod import (
    SOURCE_SERVER,
    download_source_file,
    list_pod_source_files,
    select_source_files,
    sha256_file,
)
from phases.phase0.code.data.geomagnetic.down_gfz_ap import write_new
from phases.phase7.code.load_phase7_two_storms import (
    GFZ_AP,
    PHASE1R,
    PHASE2R,
    RUN_LABEL,
    RUN_ROOT,
    load_events,
    load_geomag_and_ap,
    required_source_days,
    select_quiet_runs,
)


OUTPUT_FOLDER = Path("phases/phase0/data/raw/swarm_density_pod")
MANIFEST = RUN_ROOT / "data" / "raw" / f"manifest_dnsapod_{RUN_LABEL}.json"


def manifest_document(source_files: list[dict]) -> dict:
    """Input: verified ESA source records. Output: Phase 7 raw manifest record."""
    records = []
    for source_file in source_files:
        local_path = OUTPUT_FOLDER / source_file["name"]
        records.append({
            "name": local_path.name,
            "source_path": source_file["path"],
            "source_mtime_utc": datetime.fromtimestamp(
                source_file["mtime"], timezone.utc
            ).isoformat(),
            "local_mtime_utc": datetime.fromtimestamp(
                local_path.stat().st_mtime, timezone.utc
            ).isoformat(),
            "size_bytes": source_file["size"],
            "sha256": sha256_file(local_path),
        })
    return {
        "source": SOURCE_SERVER,
        "collection": "SW_OPER_DNSAPOD_2_",
        "selection": "Phase 7 configured event windows and Phase 3-compatible pre/post quiet runs",
        "phase2r_database": PHASE2R.as_posix(),
        "phase2r_database_sha256": sha256_file(PHASE2R),
        "phase1r_database": PHASE1R.as_posix(),
        "phase1r_database_sha256": sha256_file(PHASE1R),
        "gfz_ap": GFZ_AP.as_posix(),
        "gfz_ap_sha256": sha256_file(GFZ_AP),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": records,
    }


def download_required_density() -> Path:
    """Input: frozen Phase 1R/2R and ESA listing. Output: verified ZIPs and manifest."""
    if MANIFEST.exists():
        raise FileExistsError(MANIFEST)
    events = load_events()
    selections = select_quiet_runs(events, load_geomag_and_ap())
    days = required_source_days(events, selections)
    source_files = select_source_files(list_pod_source_files(), days)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    for index, source_file in enumerate(source_files, start=1):
        download_source_file(source_file, OUTPUT_FOLDER)
        if index % 10 == 0 or index == len(source_files):
            print(f"[{index}/{len(source_files)}] DNSAPOD days verified", flush=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    write_new(
        MANIFEST,
        (json.dumps(manifest_document(source_files), indent=2) + "\n").encode("utf-8"),
    )
    return MANIFEST


def main() -> None:
    """Input: fixed Phase 7 sources. Output: DNSAPOD manifest path."""
    print(download_required_density())


if __name__ == "__main__":
    main()
