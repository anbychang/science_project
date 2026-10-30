# OUTPUT

各 Phase 的成果捷徑；此檔不複製資料。連結指向 GitHub 可閱讀的報告、圖或分析 CSV。大型 SQLite 與原始資料只存本機，未上傳 GitHub；各檢查點名稱見 [CATALOG.md](CATALOG.md)。

| Phase | 狀態 | 報告 | 圖與表 |
| --- | --- | --- | --- |
| Phase 0 | 共用來源，無獨立研究輸出 | — | — |
| Phase 1（三年） | 候選資料已完成；物理校準未完成 | [軌道候選資料報告](phases/phase1/reports/orbit_analysis_report.md)、[舊 10 分鐘紀錄](phases/phase1/reports/phase_1_final_report.md) | [圖檔](phases/phase1/figures/) |
| Phase 1R（十二年） | 候選與報告範圍已核對；獨立 release 和物理校準未完成 | [十二年軌道分析](phases/phase1r/reports/orbit_analysis_report_2014_2026.md) | [圖檔](phases/phase1r/figures/) |
| Phase 2（三年） | 已結案 | [最終報告](phases/phase2/reports/phase_2_final_report.md)、[SME 方法報告](phases/phase2/reports/phase_2_sme_report.md) | [25 場 P2.6 圖](phases/phase2/figures/P2.6/) |
| Phase 2R（十二年） | 已結案 | [最終報告](phases/phase2r/reports/phase_2r_final_report.md) | [46 場 P2R.6 圖](phases/phase2r/figures/P2R.6/) |
| Phase 3（三年） | 唯讀歷史 M1 基線；不作後續密度分析固定參數 | [密度響應最終報告](phases/phase3/reports/phase_3_final_report.md) | [25 場總覽圖](phases/phase3/figures/prediction_tau465_25storm_overview.png)、[全部圖檔](phases/phase3/figures/)、[分析 CSV](phases/phase3/data/analysis/) |
| Phase 3 Trial4 | 現行修正基線；自由 $R_k$／$\tau_k$ 的資料內描述性 joint fit，已核對來源、公式與保存輸出，尚未外測 | [joint-fit 報告](phases/phase3-trial4/reports/trial4_joint_fit_tau15_report.md)、[資料血緣](phases/phase3-trial4/docs/lineage/trial4_joint_fit_tau15.md) | [25 場總覽圖](phases/phase3-trial4/figures/trial4_joint_fit_tau15_25storm_overview.png)、[逐場參數](phases/phase3-trial4/data/analysis/trial4_joint_fit_tau15_events.csv) |
| Phase4 Trial1 | Trial4 固定基線上的五特徵資料內 GPR；不可作外測或預報 | [結果報告](phases/phase4-trial1/reports/phase_4_trial4_altitude_gpr_report.md)、[資料血緣](phases/phase4-trial1/docs/lineage/phase_4_trial4_altitude_gpr.md) | [資料內 RMSE 圖](phases/phase4/reports/figures/phase4_trial1_insample_rmse.png)、[25 場資料內圖](phases/phase4-trial1/figures/phase4_trial4_altitude_gpr_25storm.png) |
| Phase4 Trial2 | 20/5 storm-group held-out GPR；RMSE 0.11028，未改善 Trial4 的 0.11005 | [結果報告](phases/phase4-trial2/reports/phase_4_trial4_groupcv20_5_report.md)、[資料血緣](phases/phase4-trial2/docs/lineage/phase_4_trial4_groupcv20_5.md) | [高度距離圖](phases/phase4/reports/figures/phase4_trial2_altitude_ard_distance.png)、[held-out 25 場圖](phases/phase4-trial2/figures/phase4_trial4_groupcv20_5_25storm.png)、[折次指標](phases/phase4-trial2/data/analysis/phase4_trial4_groupcv20_5_fold_metrics.csv) |
| Phase4 Trial3 | nested 20/5 storm-group 四特徵 GPR；RMSE 0.12014，劣於 Trial4 的 0.11005 | [結果報告](phases/phase4-trial3/reports/phase_4_trial4_nested_groupcv_report.md)、[資料血緣](phases/phase4-trial3/docs/lineage/phase_4_trial4_nested_groupcv.md) | [逐場 RMSE 變化圖](phases/phase4/reports/figures/phase4_trial3_event_rmse_change.png)、[outer 指標](phases/phase4-trial3/data/analysis/phase4_trial4_trial3_fold_metrics.csv) |
| Phase4 Trial4 | 時間、固定 Trial4 tau、季節 nested GPR；RMSE 0.11323，仍劣於 Trial4 0.11005 | [結果報告](phases/phase4-trial4/reports/phase_4_time_tau_season_report.md)、[資料血緣](phases/phase4-trial4/docs/lineage/phase_4_time_tau_season.md) | [折次 RMSE 變化圖](phases/phase4/reports/figures/phase4_trial4_fold_rmse_change.png)、[outer 指標](phases/phase4-trial4/data/analysis/phase4_trial4_time_tau_season_fold_metrics.csv) |
| Phase4 Trial5 | 新 geomagnetic driver nested GPR；RMSE 0.13203，明顯劣於 Trial4 0.11005 | [結果報告](phases/phase4-trial5/reports/phase_4_trial5_driver_report.md)、[資料血緣](phases/phase4-trial5/docs/lineage/phase_4_trial5_driver.md) | [逐場 RMSE 變化圖](phases/phase4/reports/figures/phase4_trial5_event_rmse_change.png)、[feature audit](phases/phase4-trial5/data/analysis/phase4_trial5_driver_feature_audit.csv) |
| Phase4 Trial6 | 同場六小時缺口內插；平均改善，部分區段補壞 | [結果報告](phases/phase4-trial6/reports/trial6_within_storm_ridge_report.md) | [單場內插示意圖](phases/phase4-trial6/figures/trial6_one_storm_interpolation.png)、[逐段指標](phases/phase4-trial6/data/analysis/trial6_block_metrics.csv) |
| Phase4 Trial7 | 原生一分鐘、前 60 分鐘殘差平均；20/25 場改善，非獨立預測 | [25 場結果報告](phases/phase4-trial7/reports/trial7_25storm_past_mean_report.md) | [25 場 RMSE 圖](phases/phase4-trial7/figures/trial7_25storm_past_mean_rmse.png)、[逐場摘要](phases/phase4-trial7/data/analysis/trial7_25storm_past_mean_summary.csv) |
| Phase4 整合 | Trial1--Trial7 的結果與限制；尚無通用最終修正 | [總報告](phases/phase4/reports/phase_4_report.md) | [GPR 跨場圖](phases/phase4/reports/figures/phase4_gpr_heldout_rmse.png)、[六小時缺口圖](phases/phase4/reports/figures/phase4_trial6_gap_rmse.png) |
| Phase4 Final | [not created]；保留最終版，尚無模型或輸出 | — | — |

Phase 2、2R、3 的報告與檢查點已固定；Phase 3 只保留為 Trial4 的歷史比較與可追溯輸入。Phase 1／1R 的舊 10 分鐘結果不代表現行逐 10 秒候選。
