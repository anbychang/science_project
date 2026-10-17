# Swarm-A 軌道衰減研究

目標：研究地磁暴與 Swarm-A 軌道衰減的關係。

Phase 1 已在現有 SQLite 建立並 audit 10 分鐘分析資料集；weather preparation v2/v3 修正後的 **fresh rebuild 尚未完成**。目前 database 是已驗證 working release，不是可宣稱完全重建驗證的 frozen release。

完整交付與限制：[Phase 1 Final Report](plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md)。正式規格：[PLAN.md](plans/phase_1_data_preparation/PLAN.md)。
核心術語：[GLOSSARY.md](GLOSSARY.md)。

## Canonical output

```text
swarm_a_states                 14,558,400 raw POD rows
  -> swarm_a_mean_orbital_elements
                               14,558,400 Brouwer-Lyddane mean rows
  -> swarm_a_orbit_10min          242,640 UTC bins
  -> swarm_a_orbit_decay_10min    242,352 decay rows
  -> swarm_a_analysis_10min       242,352 causal analysis rows
```

`swarm_a_analysis_10min` coverage：`2022-01-01 06:10:00 UTC` 至 `2026-08-12 18:00:00 UTC`；4 個 `chunk_id`；density 不在 core table。

current metadata status：`working_audit_pass`。只有 fresh target database 重建、比較並通過 audit 後，才可稱為 frozen release。

## Scope

Phase 1 只準備可追溯的 10 分鐘資料集。

- 做：POD mean orbit、chunk-safe bin、smooth derivative、causal weather/geomagnetic join、SQLite audit。
- 不做：ML、drag propagator、XYZ 預報、DNSAACC density core join。
- Q4 maneuver：audit-only；不以 residual 門檻拒絕資料或切 chunk。

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
└─ swarm_a_data.sqlite working database; not committed

plans/phase_1_data_preparation/
├─ PHASE_1_FINAL_REPORT.md  current Phase 1 result
├─ PLAN.md                  normative contracts
└─ data_lineage/            source-to-table flows
```

## Data flow

```text
raw files
  -> immutable raw SQLite
  -> GCRF osculating / quality / final chunks
  -> Brouwer-Lyddane mean semi-major axis
  -> chunk-local UTC 10-minute bins
  -> chunk-local centered Savitzky-Golay decay rows
  -> causal space-weather + geomagnetic analysis rows
```

Raw tables are immutable. Each calculation writes a separate derived table keyed by source `time_us`.

`data/` 依資料結構分類；`calculation/` 只放純計算；`phase1/` 只放跨資料集的
pipeline entry points。新增程式先放到資料結構對應的 package，不再新增平面的 `data/*.py`。

## Documents

- [Phase 1 final report](plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md)
- [Phase 1 contracts](plans/phase_1_data_preparation/PLAN.md)
- [SQLite structure](plans/phase_1_data_preparation/data_lineage/DATA_LINEAGE_SQLITE.md)
- [Data lineage index](plans/phase_1_data_preparation/data_lineage/README.md)
- [Historical timeline](TIMELOG.md)
