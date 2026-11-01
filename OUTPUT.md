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
| Phase 4 v1 | 保留自由 $R_k$／$\tau_k$ 的歷史基線；舊 Phase 5 結果仍依 v1 | [joint-fit 報告](phases/phase4/reports/trial4_joint_fit_tau15_report.md)、[資料血緣](phases/phase4/docs/lineage/trial4_joint_fit_tau15.md) | [25 場總覽圖](phases/phase4/figures/trial4_joint_fit_tau15_25storm_overview.png)、`trial4_joint_fit_events` SQLite table |
| Phase 4 v2 | 現行共同 $\tau=4.75$ h 描述性基線；25 場逐分鐘 RMSE 0.113059，尚未外測 | [v2 報告](phases/phase4-v2/reports/shared_tau_grid_report.md)、[資料血緣](phases/phase4-v2/docs/lineage/phase4_v2_shared_tau.md) | 本機 `phase4_v2_minute` SQLite table |
| Phase 5 | 整場沒有目標 L2 時，已測 GPR 未得到可採用的修正；Trial9 需上一圈 L2，保留為歷史結果 | [最終報告](phases/phase5/reports/phase_5_report.md)、[Trial1--Trial13 整合報告](phases/phase5/reports/phase_5_trial1_13_report.md) | [Trial10 的 25 場密度曲線](phases/phase5-trial10/figures/m1_shape_gpr_25storm_overview.png)、[Trial11 的 25 場密度曲線](phases/phase5-trial11/figures/temporal_shape_gpr_25storm_overview.png)、[Trial12 的 25 場密度曲線](phases/phase5-trial12/figures/peak_context_gpr_25storm_overview.png)、本機 `phases/phase5-trial13/data/sqlite/` |
| Phase 5 V2 | 固定三因素 Ridge 的探索性事件 $R_k$；尚無新事件獨立外測 | [Ridge 報告](phases/phase5-v2/reports/storm_r_ridge_report.md)、[資料血緣](phases/phase5-v2/docs/lineage/storm_r_ridge.md) | [25 場 Ridge density 圖](phases/phase5-v2/figures/ridge_density_25_storms_5x5_v3.png) |
| Phase 6 | 固定 `B_eff` 下的 M0、Ridge 與 POD 半長軸下降描述性統整 | [最終報告](phases/phase6/reports/phase_6_final_report.md) | [25 場下降時間圖](phases/phase6/figures/phase6_4_decay_time_25_storms.png)、[25 場 density 時間圖](phases/phase6/figures/phase6_4_density_time_25_storms.png) |

Phase 2、2R、3 的報告與檢查點已固定；Phase 3 只保留為 Phase 4 的歷史比較與可追溯輸入。Phase 1／1R 的舊 10 分鐘結果不代表現行逐 10 秒候選。
