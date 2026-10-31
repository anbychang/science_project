# 報告與分析輸出索引

報告依 Phase 放在 `phases/<phase>/reports/`；分析 CSV 放在所屬 Phase 的 `data/analysis/`；圖放在 `figures/`。重算程式位於所屬 Phase 的 `code/`。
GitHub 可直接閱讀的成果捷徑見 [OUTPUT.md](../OUTPUT.md)；本機 SQLite 檢查點不在 GitHub。
所有歷史、現行與 working Trial 的狀態及報告入口，見 [Trial 索引](trial_index.md)。

## 結案報告

- [Phase 2 三年密度驗證](../phases/phase2/reports/phase_2_final_report.md)：P2.6 檢查點與描述性 peak QC。
- [Phase 2R 十二年重現](../phases/phase2r/reports/phase_2r_final_report.md)：P2R.6 檢查點與 46 場逐場圖。
- [Phase 3 密度響應](../phases/phase3/reports/phase_3_final_report.md)：凍結的 25 場 M1 歷史基線；不作後續密度分析的固定參數。

## 工作報告

- [Phase 5 採用版報告](../phases/phase5/reports/phase_5_report.md)：固定 Phase 4 加跨場逐圈 GPR；列出輸入、結果與使用界線。
- [Phase 5 Trial1--Trial9 實驗報告](../phases/phase5/reports/phase_5_trial1_9_report.md)：依九次嘗試的順序整理方法、結果與圖。
- [Phase 1 三年軌道分析](../phases/phase1/reports/orbit_analysis_report.md)：逐 10 秒候選軌道衰減率工作稿；資料契約稽核已通過，候選尚未校準。
- [Phase 1 舊 10 分鐘紀錄](../phases/phase1/reports/phase_1_final_report.md)：歷史資料產品，不作現行輸入。
- [Phase 1R 十二年軌道分析](../phases/phase1r/reports/orbit_analysis_report_2014_2026.md)：十二年獨立工作稿。
- [Phase 4 joint fit](../phases/phase4/reports/trial4_joint_fit_tau15_report.md)：現行修正基線；25 場自由 $R_k$／$\tau_k$ 的資料內描述性擬合，已核對來源、公式與保存輸出。
- [Phase5 Trial1 資料內 GPR](../phases/phase5-trial1/reports/phase_5_trial4_altitude_gpr_report.md)：固定 Trial4 基線的五特徵資料內描述。
- [Phase5 Trial2 20/5 GPR 驗證](../phases/phase5-trial2/reports/phase_5_trial4_groupcv20_5_report.md)：固定 Trial4 基線的 storm-group held-out 檢查；GPR 未改善整體 RMSE。
- [Phase5 Trial3 nested GPR](../phases/phase5-trial3/reports/phase_5_trial4_nested_groupcv_report.md)：四特徵 nested storm-group held-out 檢查；RMSE 0.12014，劣於 Trial4。
- [Phase5 Trial4 時間、tau、季節 GPR](../phases/phase5-trial4/reports/phase_5_time_tau_season_report.md)：固定 Trial4 tau 的 nested held-out 檢查；RMSE 0.11323，仍劣於 Trial4。
- [Phase5 Trial5 新 geomagnetic driver GPR](../phases/phase5-trial5/reports/phase_5_trial5_driver_report.md)：`dSYM-H/dt`、`ap_step`、`F10.7` 的 nested held-out 檢查；RMSE 0.13203，明顯劣於 Trial4。
- [Phase5 Trial6 同場短缺口](../phases/phase5-trial6/reports/trial6_within_storm_ridge_report.md)：六小時人工缺口內插、壓力測試與選擇規則。
- [Phase5 Trial7 一分鐘更新](../phases/phase5-trial7/reports/trial7_25storm_past_mean_report.md)：只用前 60 分鐘 L2 殘差的 25 場檢查。
- [Phase5 特徵貢獻整理](../phases/phase5-trial2/reports/phase_5_feature_contribution_summary.md)：Trial1--Trial5 的共同基準與每個特徵可主張範圍。
- [Phase5 單一特徵 GPR 消融](../phases/phase5-trial2/reports/phase_5_feature_ablation_report.md)：五欄 `only-feature`／`drop-feature` 的探索性 held-out 貢獻。

Phase 3 主線的 6 個分析 CSV 位於 [data/analysis](../phases/phase3/data/analysis/)；逐分鐘 M1 與 25 場總覽以 `phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite` 為準。它們是 Phase 4 的可追溯歷史輸入；結案資料庫只讀，不作下游固定基線。

目前密度研究路徑是 `Phase 2 -> Phase 3（歷史輸入）-> Phase 4（固定基線）-> Phase 5（逐圈殘差修正）`。採用版見[Phase 5 報告](../phases/phase5/reports/phase_5_report.md)；各次嘗試見[實驗報告](../phases/phase5/reports/phase_5_trial1_9_report.md)。血緣從[Phase 4 joint-fit](../phases/phase4/docs/lineage/trial4_joint_fit_tau15.md)與[Phase 5 現行資料血緣](../phases/phase5/docs/lineage/phase5_pooled_orbit_gpr.md)查回。本機 SQLite 依專案規則不提交 Git；下游不回寫已結案的 Phase 3。
