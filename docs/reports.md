# 報告與分析輸出索引

報告依 Phase 放在 `phases/<phase>/reports/`；分析 CSV 放在所屬 Phase 的 `data/analysis/`；圖放在 `figures/`。重算程式位於所屬 Phase 的 `code/`。
GitHub 可直接閱讀的成果捷徑見 [OUTPUT.md](../OUTPUT.md)；本機 SQLite 檢查點不在 GitHub。
所有歷史、現行與 working Trial 的狀態及報告入口，見 [Trial 索引](trial_index.md)。

## 結案報告

- [Phase 2 三年密度驗證](../phases/phase2/reports/phase_2_final_report.md)：P2.6 檢查點與描述性 peak QC。
- [Phase 2R 十二年重現](../phases/phase2r/reports/phase_2r_final_report.md)：P2R.6 檢查點與 46 場逐場圖。
- [Phase 3 密度響應](../phases/phase3/reports/phase_3_final_report.md)：凍結的 25 場 M1 歷史基線；不作後續密度分析的固定參數。

## 工作報告

- [Phase 1 三年軌道分析](../phases/phase1/reports/orbit_analysis_report.md)：逐 10 秒候選軌道衰減率工作稿；資料契約稽核已通過，候選尚未校準。
- [Phase 1 舊 10 分鐘紀錄](../phases/phase1/reports/phase_1_final_report.md)：歷史資料產品，不作現行輸入。
- [Phase 1R 十二年軌道分析](../phases/phase1r/reports/orbit_analysis_report_2014_2026.md)：十二年獨立工作稿。
- [Phase 3 Trial4 joint fit](../phases/phase3-trial4/reports/trial4_joint_fit_tau15_report.md)：現行修正基線；25 場自由 $R_k$／$\tau_k$ 的資料內描述性擬合，已核對來源、公式與保存輸出。
- [Phase4 Trial1 資料內 GPR](../phases/phase4/reports/phase_4_trial4_altitude_gpr_report.md)：固定 Trial4 基線的五特徵資料內描述。
- [Phase4 Trial2 20/5 GPR 驗證](../phases/phase4/reports/phase_4_trial4_groupcv20_5_report.md)：固定 Trial4 基線的 storm-group held-out 檢查；GPR 未改善整體 RMSE。
- [Phase4 Trial3 nested GPR](../phases/phase4/reports/phase_4_trial4_nested_groupcv_report.md)：四特徵 nested storm-group held-out 檢查；RMSE 0.12014，劣於 Trial4。
- [Phase4 Trial4 時間、tau、季節 GPR](../phases/phase4/reports/phase_4_time_tau_season_report.md)：固定 Trial4 tau 的 nested held-out 檢查；RMSE 0.11323，仍劣於 Trial4。
- [Phase4 Trial5 新 geomagnetic driver GPR](../phases/phase4/reports/phase_4_trial5_driver_report.md)：`dSYM-H/dt`、`ap_step`、`F10.7` 的 nested held-out 檢查；RMSE 0.13203，明顯劣於 Trial4。
- [Phase4 特徵貢獻整理](../phases/phase4/reports/phase_4_feature_contribution_summary.md)：Trial1--Trial5 的共同基準與每個特徵可主張範圍。
- Phase4 Final：[not created]；Trial1--Trial5 不構成最終版。

Phase 3 主線的 6 個分析 CSV 位於 [data/analysis](../phases/phase3/data/analysis/)；逐分鐘 M1 與 25 場總覽以 `phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite` 為準。它們是 Trial4 的可追溯歷史輸入；結案資料庫只讀，不作下游固定基線。

目前密度研究路徑是 `Phase 2 -> Phase 3（歷史輸入）-> Phase 3 Trial4（修正基線）-> Phase4 Trial1 -> Phase4 Trial2 -> Phase4 Trial3 -> Phase4 Trial4 -> Phase4 Trial5`。Trial4 的[joint-fit 資料血緣](../phases/phase3-trial4/docs/lineage/trial4_joint_fit_tau15.md)記錄保存的 Phase 3 快照、Phase 2 輸入與 Trial4 輸出。Phase4 的[Trial1 血緣](../phases/phase4/docs/lineage/phase_4_trial4_altitude_gpr.md)記錄 paired DNSAPOD 高度與資料內 GPR；[Trial2 血緣](../phases/phase4/docs/lineage/phase_4_trial4_groupcv20_5.md)記錄 20/5 held-out 預測；[Trial3 血緣](../phases/phase4/docs/lineage/phase_4_trial4_nested_groupcv.md)記錄 nested kernel selection；[Trial4 血緣](../phases/phase4/docs/lineage/phase_4_time_tau_season.md)記錄時間、固定 tau、季節與 outer held-out 預測；[Trial5 血緣](../phases/phase4/docs/lineage/phase_4_trial5_driver.md)記錄新增 driver 與 outer held-out 預測。五者都不回寫已結案的 Phase 3。本機 SQLite 依專案規則不提交 Git。
