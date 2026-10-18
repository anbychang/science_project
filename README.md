# Swarm-A 軌道衰減研究

目標：研究地磁暴與 Swarm-A 軌道衰減的關係。

Phase 1 已從 local raw files 完成 fresh rebuild 並通過 P1.7 audit。可交付的 frozen release 是
`data/swarm_a_phase1_rebuild.sqlite`；原 `data/swarm_a_data.sqlite` 保留為 legacy working database，
不覆寫也不作交付依據。

完整交付與限制：[Phase 1 Final Report](plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md)。正式規格：[PLAN.md](plans/phase_1_data_preparation/PLAN.md)。
核心術語：[GLOSSARY.md](GLOSSARY.md)。

## Canonical output

```text
swarm_a_states                 14,558,400 raw POD rows
  -> swarm_a_mean_orbital_elements
                               13,495,680 usable rows
  -> swarm_a_orbit_10min          224,928 UTC bins
  -> swarm_a_orbit_decay_10min    224,280 decay rows
  -> swarm_a_analysis_10min       224,280 causal analysis rows
```

`swarm_a_analysis_10min` coverage：`2022-01-01 12:10:00 UTC` 至 `2026-08-13 00:00:00 UTC`；6 個 `chunk_id`；density 不在 core table。

frozen release 的 mean table 只保留 13,495,680 個 usable POD。legacy working DB 的 mean table
早於 campaign date-level exclusion，因此另有 14,558,400 列；它僅供比較。

frozen release metadata：`status = frozen`、`rebuild_status = verified_mean_orbit_cache_reuse`、
`audit_outcome = pass`。

## Scope

Phase 1 只準備可追溯的 10 分鐘資料集。

- 做：POD mean orbit、chunk-safe bin、12 小時 backward decay rate、causal weather/geomagnetic join、SQLite audit。
- 不做：ML、drag propagator、XYZ 預報、DNSAACC density core join。
- Q4 maneuver：ESA 已公告的 orbit-raise campaign 以 date-level exclusion 切開 chunk；其餘 residual candidate 維持 audit-only。

## 專案地圖

```text
satellite_orbit/
├─ data/
│  ├─ pod/            POD download, load, raw/derived writers
│  ├─ space_weather/  F10.7 / Ap download, load, raw writer
│  ├─ geomagnetic/    SYM-H / AE download, load, raw writer
│  ├─ density/        DNSAACC density load and raw writer
│  └─ database/       shared SQLite schema, IDs, raw-data entry point
├─ calculation/
│  ├─ pod/            time, frame, osculating and mean-orbit calculations
│  └─ analysis/       causal feature alignment
└─ phase1/         final analysis writer, rebuild, release audit

data/
├─ swarm_a_pod/        raw POD ZIP
├─ geomagnetic/        raw SYM-H / AE CSV
├─ space_weather/      raw F10.7 / Ap CSV
├─ swarm_density_acc/  raw DNSAACC density ZIP
├─ swarm_a_phase1_rebuild.sqlite frozen release; not committed
└─ swarm_a_data.sqlite legacy working database; not committed

data_lineage/               downloaded sources -> current data products
├─ pod.md                    raw POD -> orbit analysis
├─ density.md                DNSAACC ZIP -> density summary -> comparison
├─ orbit_analysis.md         orbit analysis table shapes
└─ README.md                 all source-to-output paths
```

## Data flow

```text
raw files
  -> immutable raw SQLite
  -> GCRF osculating / quality / final chunks
  -> Brouwer-Lyddane mean semi-major axis
  -> chunk-local UTC 10-minute bins
  -> chunk-local backward 12-hour difference decay rows
  -> causal space-weather + geomagnetic analysis rows
```

Raw tables are immutable. Each calculation writes a separate derived table keyed by source `time_us`.

`data/` 依資料結構分類；`calculation/` 只放純計算；`phase1/` 只放跨資料集的
pipeline entry points。新增程式先放到資料結構對應的 package，不再新增平面的 `data/*.py`。

## Documents

- [Phase 1 final report](plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md)
- [Phase 1 contracts](plans/phase_1_data_preparation/PLAN.md)
- [Data lineage index](data_lineage/README.md)
- [Orbit analysis structure](data_lineage/orbit_analysis.md)
- [Phase 2 plan](plans/phase_2_density_validation/PHASE_2_EXECUTION_PLAN.md)
- [Density flow](data_lineage/density.md)
- [Historical timeline](TIMELOG.md)
