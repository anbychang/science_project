# CATALOG

專案現行資料與文件入口。`phases/<phase>/` 內的 `code/`、`data/`、`docs/`、`figures/`、`reports/`、`tests/` 依責任歸屬存放；不是每個 Phase 都有全部目錄。

```text
[done: candidate] 候選資料產品已完成；物理校準尚未完成
[done: negative] 指定資料條件下的候選方法已核對，沒有選出可採用版本
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
| Phase 3（三年） | [retained] | `phases/phase3/data/sqlite/`（本機） 與 [分析 CSV](phases/phase3/data/analysis/)；M1 分鐘結果在 `swarm_a_phase3_prediction_tau465_exploratory.sqlite`。它是唯讀歷史比較與 Phase 4 保存快照的來源，不作現行下游固定參數。 | [最終報告](phases/phase3/reports/phase_3_final_report.md)、[資料血緣](phases/phase3/docs/lineage/phase_3_25_storm_prediction.md) |
| Phase 4 v1 | [retained: descriptive] | `phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite`（本機）含 25 場、214,907 列自由 $R_k,\tau_k$ joint fit；Phase 5 既有輸出仍讀這版。 | [joint-fit 報告](phases/phase4/reports/trial4_joint_fit_tau15_report.md)、[資料血緣](phases/phase4/docs/lineage/trial4_joint_fit_tau15.md) |
| Phase 4 v2 | [done: descriptive] | `phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite`（本機）含共同 $\tau=4.75$ h、25 場、214,907 筆；目前的描述性密度基線。 | [v2 報告](phases/phase4-v2/reports/shared_tau_grid_report.md)、[資料血緣](phases/phase4-v2/docs/lineage/phase4_v2_shared_tau.md) |
| Phase 5 | [done: negative] | 無同場 L2 時，Trial10--Trial12 的 GPR 留場結果未勝過 M1；Trial13 的統一核對保存在本機 `phases/phase5-trial13/data/sqlite/`。`phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite` 與六個模型是需上一圈 L2 的歷史 Trial9 延伸版，不是無 L2 終版。 | [最終報告](phases/phase5/reports/phase_5_report.md)、[Trial1--Trial13 整合報告](phases/phase5/reports/phase_5_trial1_13_report.md)、[總入口](phases/phase5/README.md) |
| Phase 5 V2 | [done: exploratory] | `storm_r_ridge_density_v1.sqlite` 含 25 場、214,907 筆留出 Ridge $R_k$ 密度；同批事件參與特徵選擇，尚無獨立外測。 | [Ridge 報告](phases/phase5-v2/reports/storm_r_ridge_report.md)、[資料血緣](phases/phase5-v2/docs/lineage/storm_r_ridge.md)、[工作空間](phases/phase5-v2/README.md) |
| Phase 6 | [done: descriptive] | P6.1 固定 `B_eff`；P6.2 M0、P6.3 Ridge 下降；P6.4 完成 POD 總量、時間曲線與 density 統整。 | [最終報告](phases/phase6/reports/phase_6_final_report.md)、[工作空間](phases/phase6/README.md)、[P6.4 lineage](phases/phase6/docs/lineage/phase6_4_decay_comparison.md) |

Phase 1／1R 的候選資料尚未校準為正式衰減率。舊 10 分鐘分支只供歷史比較，不作現行輸入。Phase 2、2R、3 的檢查點不回寫；新的修正密度分析讀 Phase 4 v2。Phase 6 已在固定 `B_eff` 下完成 M0、Ridge 與 POD 的描述性比較，但不是獨立軌道預報驗證。

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
