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
| Phase 4 | 現行修正基線；自由 $R_k$／$\tau_k$ 的資料內描述性 joint fit，已核對來源、公式與保存輸出，尚未外測 | [joint-fit 報告](phases/phase4/reports/trial4_joint_fit_tau15_report.md)、[資料血緣](phases/phase4/docs/lineage/trial4_joint_fit_tau15.md) | [25 場總覽圖](phases/phase4/figures/trial4_joint_fit_tau15_25storm_overview.png)、`trial4_joint_fit_events` SQLite table |
| Phase 5 | 採用固定 Phase 4 加跨場逐圈 GPR；結果保存在 SQLite，尚非端到端預報 | [採用版報告](phases/phase5/reports/phase_5_report.md)、[Trial1--Trial9 實驗報告](phases/phase5/reports/phase_5_trial1_9_report.md) | 本機 `phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite`、[逐場 RMSE 圖](phases/phase5/figures/phase5_pooled_gpr_rmse.png)、[25 場三線總覽圖](phases/phase5/figures/phase5_density_25storm_overview.png) |

Phase 2、2R、3 的報告與檢查點已固定；Phase 3 只保留為 Phase 4 的歷史比較與可追溯輸入。Phase 1／1R 的舊 10 分鐘結果不代表現行逐 10 秒候選。
