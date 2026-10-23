# Swarm-A 軌道衰減研究

> 現行 Phase 1 工作輸出是兩份 P1.5.1 checkpoint 與其 P1.5.6 v2 working copy。

目標：研究地磁暴與 Swarm-A 軌道衰減的關係。

目前有 2014--2026 全期與 2023--2026 三年版 P1.5.1 mean-element checkpoint，
以及兩份逐 10 秒的 P1.5.6 v2 working copy。兩份 working copy 都有 raw B-L、
joint H2/H3、P1.6 causal feature 與 P1.7 v2 audit；兩份 audit 的 6 項 violation
均為 0，metadata status 為 `pass`。這是資料契約稽核，不是已校準的磁暴衰減率或
正式 release。舊 10 分鐘 P1.5--P1.7 輸出是 retained legacy，不可和 v2 混用。

完整交付與限制：[Phase 1 Final Report](plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md)。
現行執行狀態與契約：[PHASE_1_EXECUTION_PLAN.md](plans/phase_1_data_preparation/PHASE_1_EXECUTION_PLAN.md)
及 [orbit_analysis.md](data_lineage/orbit_analysis.md)。
[PLAN.md](plans/phase_1_data_preparation/PLAN.md) 保留舊 10 分鐘設計。
核心術語：[GLOSSARY.md](GLOSSARY.md)。

## 文件規則

Data Lineage 的完整寫作與資料 contract 規則在
[data_lineage/RULES.md](data_lineage/RULES.md)。

## Canonical output

```text
2014--2026 checkpoint
  -> swarm_a_mean_orbit_elements_v1  39,346,558 rows
  -> phase_candidate_working_v2
       -> raw B-L v2 / joint H2H3 v2 / P1.6 features v2 / P1.7 audit v2

2023--2026 checkpoint
  -> swarm_a_mean_orbit_elements_v1   9,469,438 rows
  -> phase_candidate_working_v1
       -> raw B-L v2 / joint H2H3 v2 / P1.6 features v2 / P1.7 audit v2
```

12 年 v2 的每張 rate table 有 38,378,878 rows；三年的兩張 rate table 與
feature table 各有 9,469,438 rows。12 年 feature row count 仍以 writer metadata
與 P1.7 key-identity audit 為證據，尚未另行完成全表獨立計數。兩份 checkpoint 的
P1.5.1 rejection 都是 0。三年 checkpoint 保留全期 raw states，只有 mean-element
table 限定三年。全期 raw／quality 比 mean-element 多的 2 筆，時間分別是
2013-12-31 23:59:44、23:59:54 UTC，位於 2014-01-01 起始範圍之前；
不是範圍內漏算。

## Scope

Phase 1 現行主線準備可追溯的逐 10 秒局部斜率候選；10 分鐘資料集是保留的舊分支。

- 做：POD mean orbit、phase-defined 3／5 圈 raw 與 H2/H3 局部 OLS、
  causal weather/geomagnetic feature、SQLite audit。
- 不做：ML、drag propagator、XYZ 預報、舊版 density core join。
- Q4 maneuver：ESA 已公告的 orbit-raise campaign 以 date-level exclusion 切開 chunk；
  其餘 residual candidate 維持 audit-only。

## 專案地圖

```text
satellite_orbit/
├─ data/
│  ├─ pod/            POD download, load, raw/derived writers
│  ├─ space_weather/  F10.7 / Ap download, load, raw writer
│  ├─ geomagnetic/    SYM-H / AE download, load, raw writer
│  ├─ density/        DNSAPOD source download and load
│  └─ database/       shared SQLite schema, IDs, raw-data entry point
├─ calculation/
│  ├─ pod/            time, frame, osculating and mean-orbit calculations
│  └─ analysis/       causal feature alignment
└─ phase1/         final analysis writer, rebuild, release audit

data/
├─ swarm_a_pod/        raw POD ZIP
├─ geomagnetic/        raw SYM-H / AE CSV
├─ space_weather/      raw F10.7 / Ap CSV
├─ swarm_density_pod/  raw DNSAPOD density ZIP
└─ sqlite/
   ├─ swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite
   ├─ swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite
   ├─ swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite
   └─ swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite

data_lineage/               downloaded sources -> current data products
├─ phase_2_storm_dataset.md  current P2.0–P2.3 SME orbit lineage
├─ orbit_analysis.md         POD -> orbit analysis
└─ README.md                 all source-to-output paths
```

舊 DNSAACC 程式與 `data_lineage/density.md` 已移除；`data/swarm_density_acc/` 的原始 ZIP 保留原位供歷史追溯。現行 Phase 2 只用 DNSAPOD。

## Data flow

```text
raw files
  -> immutable raw SQLite
  -> GCRF osculating / quality / final chunks
  -> Brouwer-Lyddane mean elements
  -> 3／5 個 phase orbit 的 raw B-L / joint H2/H3 局部 slope
  -> 每個 10 秒 time_us 的 causal feature
  -> P1.7 v2 working audit
```

Raw tables are immutable. Each calculation writes a separate derived table
keyed by source `time_us`.

`data/` 依資料結構分類；`calculation/` 只放純計算；`phase1/` 只放跨資料集的
pipeline entry points。新增程式先放到資料結構對應的 package，不再新增平面的 `data/*.py`。

## Documents

- [Phase 1 final report](plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md)
- [Phase 1 contracts](plans/phase_1_data_preparation/PLAN.md)
- [Data lineage index](data_lineage/README.md)
- [Data lineage rules](data_lineage/RULES.md)
- [POD lineage](data_lineage/orbit_analysis.md)
- [Phase 2 SME 方法主報告](plans/phase_2_density_validation/PHASE_2_SME_REPORT.md)
- [Phase 2 SME 逐圈資料血緣](data_lineage/phase_2_storm_dataset.md)
- [Historical timeline](TIMELOG.md)
