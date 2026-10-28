# Swarm-A 軌道衰減研究

> Phase 1 是三年工作版，Phase 1R 是十二年工作版；兩者各保留 P1.5.1 checkpoint 與 P1.5.6 v2 working copy。Phase 2、Phase 2R 與 Phase 3 已結案並封存。

目標：研究地磁暴與 Swarm-A 軌道衰減的關係。

目前有 2014--2026 全期與 2023--2026 三年版 P1.5.1 mean-element checkpoint，
以及兩份逐 10 秒的 P1.5.6 v2 working copy。兩份 working copy 都有 raw B-L、
joint H2/H3、P1.6 causal feature 與 P1.7 v2 audit；兩份 audit 的 6 項 violation
均為 0，metadata status 為 `pass`。這是資料契約稽核，不是已校準的磁暴衰減率或
正式 release。舊 10 分鐘 P1.5--P1.7 輸出是 retained legacy，不可和 v2 混用。

完整交付與限制：[Phase 1 Final Report](research_workspace/phases/phase1/reports/phase_1_final_report.md)。
現行執行狀態與契約：[phase_1_execution_plan.md](research_workspace/phases/phase1/docs/plans/phase_1_execution_plan.md)
及 [orbit_analysis.md](research_workspace/phases/phase1/docs/lineage/orbit_analysis.md)。
[PLAN.md](research_workspace/phases/phase1/docs/plans/PLAN.md) 保留舊 10 分鐘設計。
[Phase 1R 十二年計畫](research_workspace/phases/phase1r/docs/plans/PLAN.md)與[十二年工作報告](research_workspace/phases/phase1r/reports/orbit_analysis_report_2014_2026.md)記錄獨立的十二年範圍與限制。
核心術語：[GLOSSARY.md](GLOSSARY.md)。
資料與文件入口：[CATALOG.md](CATALOG.md)。

## 文件規則

Data Lineage 的完整寫作與資料 contract 規則在
[research_workspace/docs/data_lineage/RULES.md](research_workspace/docs/data_lineage/RULES.md)。

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

Phase 2 three-year minute chain
  -> P2.0 source audit -> P2.1 geomag -> P2.2 events
  -> P2.3 t0 phase minute features -> P2.4 density
  -> P2.5 minute analysis view -> P2.6 final smoothed peak QC

Phase 2R 12-year replication
  -> P2R.0 source audit -> P2R.1 geomag -> P2R.2 events
  -> P2R.3 t0 phase minute features -> P2R.4 density
  -> P2R.5 minute analysis view -> P2R.6 final smoothed peak QC

Phase 3 three-year density response
  -> final per-event R_k calibration -> SME first-order response
  -> quiet-MSIS/M1 offline density curves -> final report
```

Phase 2 已結案；唯一交付的 P2.6 檢查點是 `research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite`。F10.7A 使用來源 `F10.7_OBS_CENTER81`；SME 與密度殘差先平滑，peak 只在 `t0 - 12 h` 至 `t0 + 24 h` 選取。25 張磁暴圖直接位於 `research_workspace/phases/phase2/figures/P2.6/`，不設圖版本子目錄。交付結果與限制見[Phase 2 最終報告](research_workspace/phases/phase2/reports/phase_2_final_report.md)。

Phase 2R 把相同科學方法套用到 2014-07-01 至 2026-06-30，並把連續 `chunk_id` 明定為資料完整性邊界。代表完整 12 年範圍的 7 個獨立 checkpoint 位於 `research_workspace/phases/phase2r/data/sqlite/`；49 場候選中 46 場有完整連續相位與密度，產生 400,696 筆分鐘資料及 46 張逐場圖。交付結果與限制見[Phase 2R 最終報告](research_workspace/phases/phase2r/reports/phase_2r_final_report.md)。

Phase 3 已完成三年 25 場離線密度響應分析。每場 $R_k$ 已依低活動段規則計算並用於 M1；主線結果與適用範圍見[Phase 3 結案報告](research_workspace/phases/phase3/reports/phase_3_final_report.md)，各步 SQLite key、Input／Output 與重算入口見[Phase 3 資料血緣](research_workspace/phases/phase3/docs/lineage/phase_3_25_storm_prediction.md)。[Phase 3 計畫](research_workspace/phases/phase3/docs/plans/PLAN.md)保留決策歷史。

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

[Phase 0 共用基礎計畫](research_workspace/phases/phase0/docs/plans/PLAN.md)定義全專案的原始來源與共用程式。各研究 Phase 的衍生資料仍由該 Phase 管理。

```text
research_workspace/
  docs/                       全專案血緣規則、報告索引與寫作規則
  phases/
    phase0/                   code/data、code/calculation、data/raw、docs、tests
    phase1/                   code、data、docs、figures、reports、tests
    phase1r/                  十二年 code、data、docs、figures、reports、tests
    phase2/                   code、data、docs、figures、reports、tests
    phase2r/                  十二年 code、data、docs、figures、reports、tests
    phase3/                   code、data、docs、figures、reports、tests
    phase4/docs/plans/        Phase 4 計畫
```

共用來源只存一份；各 phase 的 SQLite 位於自己的 `data/sqlite/`。
`research_workspace/phases/phase0/data/raw/swarm_density_acc/` 保存歷史 DNSAACC ZIP；現行 Phase 2 使用 DNSAPOD。

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

`research_workspace/phases/phase0/code/data/` 依來源資料分類；`research_workspace/phases/phase0/code/calculation/` 放共用計算；各 Phase 的 `code/` 放自己的研究流程。新增程式依實際責任放入對應目錄。

## Documents

- [Phase 1 final report](research_workspace/phases/phase1/reports/phase_1_final_report.md)
- [Phase 1 contracts](research_workspace/phases/phase1/docs/plans/PLAN.md)
- [Phase 1R 十二年計畫](research_workspace/phases/phase1r/docs/plans/PLAN.md)
- [Phase 1R 十二年工作報告](research_workspace/phases/phase1r/reports/orbit_analysis_report_2014_2026.md)
- [Data lineage index](research_workspace/docs/data_lineage/README.md)
- [Data lineage rules](research_workspace/docs/data_lineage/RULES.md)
- [POD lineage](research_workspace/phases/phase1/docs/lineage/orbit_analysis.md)
- [Phase 2 最終報告](research_workspace/phases/phase2/reports/phase_2_final_report.md)
- [Phase 2 計畫](research_workspace/phases/phase2/docs/plans/PLAN.md)
- [Phase 2 SME 方法主報告](research_workspace/phases/phase2/reports/phase_2_sme_report.md)
- [Phase 2 SME 分鐘資料血緣](research_workspace/phases/phase2/docs/lineage/phase_2_storm_dataset.md)
- [Phase 2R 12 年最終報告](research_workspace/phases/phase2r/reports/phase_2r_final_report.md)
- [Phase 2R 12 年計畫](research_workspace/phases/phase2r/docs/plans/PLAN.md)
- [Phase 2R 12 年資料血緣](research_workspace/phases/phase2r/docs/lineage/phase_2r_12year_replication.md)
- [Historical timeline](TIMELOG.md)
