# Phase 1R：十二年軌道候選工作版

狀態：[working]。分析期間為 2014-07-01 至 2026-07-01 UTC（左含右不含）。資料庫保留 2014 年上半年觀測；[十二年報告](../../reports/orbit_analysis_report_2014_2026.md)在讀取時排除該期間。

## 資料與輸出

- P1.5.1 平均軌道檢查點：`phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite`。
- P1.5.6 v2 候選工作庫：`phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite`。P1.6 feature 與 P1.7 v2 audit 已完成；候選斜率尚未校準成真實衰減率。
- 十二年報告圖：`phases/phase1r/figures/`，重算入口為 `python -m phases.phase1r.code.prep_report_figures`。

共用的計算方法與資料契約見 [Phase 1 執行計畫](../../../phase1/docs/plans/phase_1_execution_plan.md)及 [軌道資料血緣](../../../phase1/docs/lineage/orbit_analysis.md)。兩個工作版使用同一方法，但資料庫與報告分開。十二年報告從 2014-07 起的篩選範圍尚未另行完成 release 稽核。
