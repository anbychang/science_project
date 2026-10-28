# 報告與分析輸出索引

報告依 Phase 放在 `phases/<phase>/reports/`；分析 CSV 放在所屬 Phase 的 `data/analysis/`；圖放在 `figures/`。重算程式位於所屬 Phase 的 `code/`。
GitHub 可直接閱讀的成果捷徑見 [OUTPUT.md](../OUTPUT.md)；本機 SQLite 檢查點不在 GitHub。

## 結案報告

- [Phase 2 三年密度驗證](../phases/phase2/reports/phase_2_final_report.md)：P2.6 檢查點與描述性 peak QC。
- [Phase 2R 十二年重現](../phases/phase2r/reports/phase_2r_final_report.md)：P2R.6 檢查點與 46 場逐場圖。
- [Phase 3 密度響應](../phases/phase3/reports/phase_3_final_report.md)：25 場 M1 結果，逐場 $R_k$ 校準已定稿。

## 工作報告

- [Phase 1 三年軌道分析](../phases/phase1/reports/orbit_analysis_report.md)：逐 10 秒候選軌道衰減率工作稿；資料契約稽核已通過，候選尚未校準。
- [Phase 1 舊 10 分鐘紀錄](../phases/phase1/reports/phase_1_final_report.md)：歷史資料產品，不作現行輸入。
- [Phase 1R 十二年軌道分析](../phases/phase1r/reports/orbit_analysis_report_2014_2026.md)：十二年獨立工作稿。

Phase 3 的 30 個分析 CSV 位於 [data/analysis](../phases/phase3/data/analysis/)；逐分鐘 M1 與 25 場總覽以 `phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite` 為準。結案資料庫只讀；新分析另建輸出。

## 尚未產出

[Phase 4](../phases/phase4/docs/plans/PLAN.md) 已建立 GPR 殘差修正計畫，尚無模型結果或報告。
