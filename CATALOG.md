# CATALOG

專案現行資料與文件入口。`phases/<phase>/` 內的 `code/`、`data/`、`docs/`、`figures/`、`reports/`、`tests/` 依責任歸屬存放；不是每個 Phase 都有全部目錄。

```text
[done: candidate] 候選資料產品已完成；物理校準尚未完成
[working] 仍在修訂
[final]   已結案；資料與報告只讀
[retained] 已凍結的歷史基線；不作現行下游輸入
[plan]    已立計畫，尚無研究結果
```

## 共用來源

| 位置 | 內容 | 使用方式 |
| --- | --- | --- |
| `phases/phase0/data/raw/`（本機） | POD、DNSAPOD、DNSAACC、地磁與太空天氣來源；來源檔只存一份。 | 由各 Phase 的資料流程讀取，不修改原始觀測。 |
| [Phase 0 共用程式](phases/phase0/code/) | 下載、載入、原始資料準備與共用計算。 | 從專案根目錄執行 Python 模組。 |
| [Phase 0 計畫](phases/phase0/docs/plans/PLAN.md) | 共用基礎的範圍。 | 新增共用來源時先看此處。 |

## Phase 交付

| Phase | 狀態 | 資料位置與主要檢查點 | 閱讀入口 |
| --- | --- | --- | --- |
| Phase 1（三年） | [done: candidate] | `phases/phase1/data/sqlite/`（本機）：`swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite` 是 mean-element checkpoint；`swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite` 是逐 10 秒候選資料庫。物理校準未完成。 | [候選資料報告](phases/phase1/reports/orbit_analysis_report.md)、[舊 10 分鐘紀錄](phases/phase1/reports/phase_1_final_report.md)、[現行執行計畫](phases/phase1/docs/plans/phase_1_execution_plan.md)、[資料血緣](phases/phase1/docs/lineage/orbit_analysis.md) |
| Phase 1R（十二年） | [working] | `phases/phase1r/data/sqlite/`（本機）：`swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite` 是 mean-element checkpoint；`swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite` 是逐 10 秒候選工作版。報告範圍已核對，獨立 release 未建立。 | [計畫](phases/phase1r/docs/plans/PLAN.md)、[工作報告](phases/phase1r/reports/orbit_analysis_report_2014_2026.md) |
| Phase 2（三年） | [final] | `phases/phase2/data/sqlite/`（本機檢查點鏈）：P2.0 至 P2.6；最終檔為 `swarm_a_phase2_sme_p2_6_final.sqlite`。 | [最終報告](phases/phase2/reports/phase_2_final_report.md)、[資料血緣](phases/phase2/docs/lineage/phase_2_storm_dataset.md) |
| Phase 2R（十二年） | [final] | `phases/phase2r/data/sqlite/`（本機檢查點鏈）：P2R.0 至 P2R.6；最終檔為 `swarm_a_phase2r_p2r_6_final_v1.sqlite`。 | [最終報告](phases/phase2r/reports/phase_2r_final_report.md)、[資料血緣](phases/phase2r/docs/lineage/phase_2r_12year_replication.md) |
| Phase 3（三年） | [retained] | `phases/phase3/data/sqlite/`（本機） 與 [分析 CSV](phases/phase3/data/analysis/)；M1 分鐘結果在 `swarm_a_phase3_prediction_tau465_exploratory.sqlite`。它是唯讀歷史比較與 Trial4 保存快照的來源，不作現行下游固定參數。 | [最終報告](phases/phase3/reports/phase_3_final_report.md)、[資料血緣](phases/phase3/docs/lineage/phase_3_25_storm_prediction.md) |
| Phase 3 Trial4 | [done: descriptive] | `phases/phase3-trial4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite`（本機）含 25 場、214,907 列資料內 joint fit；保存的 Phase 3 輸入快照與 [CSV／圖](phases/phase3-trial4/data/analysis/) 同在 Trial4。這是現行修正基線，不是外測或物理 release。 | [joint-fit 報告](phases/phase3-trial4/reports/trial4_joint_fit_tau15_report.md)、[資料血緣](phases/phase3-trial4/docs/lineage/trial4_joint_fit_tau15.md) |
| Phase4 Trial1 | [done] | `swarm_a_phase4_trial4_altitude_gpr_v1.sqlite` 是 2,295 列資料內描述。 | [計畫](phases/phase4/docs/plans/PLAN.md)、[報告](phases/phase4-trial1/reports/phase_4_trial4_altitude_gpr_report.md)、[資料血緣](phases/phase4-trial1/docs/lineage/phase_4_trial4_altitude_gpr.md) |
| Phase4 Trial2 | [done] | `swarm_a_phase4_trial4_altitude_groupcv20_5_v2.sqlite` 是每場一次 held-out 的 20/5 結果；RMSE 0.11028，未改善 Trial4 0.11005。 | [報告](phases/phase4-trial2/reports/phase_4_trial4_groupcv20_5_report.md)、[資料血緣](phases/phase4-trial2/docs/lineage/phase_4_trial4_groupcv20_5.md) |
| Phase4 Trial3 | [done] | `swarm_a_phase4_trial4_nested_groupcv_v3.sqlite` 是 nested 20/5 的四特徵 held-out 結果；RMSE 0.12014，劣於 Trial4 0.11005。 | [計畫](phases/phase4/docs/plans/PLAN.md)、[報告](phases/phase4-trial3/reports/phase_4_trial4_nested_groupcv_report.md)、[資料血緣](phases/phase4-trial3/docs/lineage/phase_4_trial4_nested_groupcv.md) |
| Phase4 Trial4 | [done] | `swarm_a_phase4_trial4_time_tau_season_nested_v4.sqlite` 是時間、固定 Trial4 tau、季節 nested held-out 結果；RMSE 0.11323，劣於 Trial4 0.11005。 | [計畫](phases/phase4/docs/plans/PLAN.md)、[報告](phases/phase4-trial4/reports/phase_4_time_tau_season_report.md)、[資料血緣](phases/phase4-trial4/docs/lineage/phase_4_time_tau_season.md) |
| Phase4 Trial5 | [done] | `swarm_a_phase4_trial5_driver_gpr_v5.sqlite` 是新 geomagnetic driver nested held-out 結果；RMSE 0.13203，劣於 Trial4 0.11005。 | [計畫](phases/phase4/docs/plans/PLAN.md)、[報告](phases/phase4-trial5/reports/phase_4_trial5_driver_report.md)、[資料血緣](phases/phase4-trial5/docs/lineage/phase_4_trial5_driver.md) |
| Phase4 Final | [plan] | 保留給最終版；尚無資料、程式或輸出。 | [Trial 計畫](phases/phase4/docs/plans/PLAN.md)、[特徵貢獻整理](phases/phase4/reports/phase_4_feature_contribution_summary.md) |

Phase 1／1R 的候選資料尚未校準為正式衰減率。舊 10 分鐘分支只供歷史比較，不作現行輸入。Phase 2、2R、3 的檢查點不回寫；下游密度分析讀 Trial4 D-model，不讀 Phase 3 固定 M1。

## 文件與維護

| 位置 | 用途 |
| --- | --- |
| [報告索引](docs/reports.md) | 各 Phase 報告與分析輸出的詳細入口。 |
| [資料血緣索引](docs/data_lineage/README.md) | 來源、轉換與各 Phase 血緣入口。 |
| [資料血緣規則](docs/data_lineage/RULES.md) | 撰寫和修改血緣文件時的格式與資料契約。 |
| [寫作規則](docs/writing_style.md) | 專案 Markdown 格式。 |
| [ISSUE.md](ISSUE.md) | 已確認、暫不處理的問題。 |
| [TIMELOG.md](TIMELOG.md) | 歷史決策與執行紀錄。 |

本機暫存資料放在 `tmp/`，不屬於正式交付。SQLite 與大部分原始來源不提交 Git；檔案清單以本機資料夾為準。所有 Trial 的採用狀態與報告入口見 [Trial 索引](docs/trial_index.md)。
