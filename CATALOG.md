# CATALOG

專案現行資料與文件入口。`phases/<phase>/` 內的 `code/`、`data/`、`docs/`、`figures/`、`reports/`、`tests/` 依責任歸屬存放；不是每個 Phase 都有全部目錄。

```text
[working] 仍在修訂或尚未校準
[final]   已結案；資料與報告只讀
[plan]    尚未產生研究結果
```

## 共用來源

| 位置 | 內容 | 使用方式 |
| --- | --- | --- |
| [Phase 0 原始資料](phases/phase0/data/raw/) | POD、DNSAPOD、DNSAACC、地磁與太空天氣來源；來源檔只存一份。 | 由各 Phase 的資料流程讀取，不修改原始觀測。 |
| [Phase 0 共用程式](phases/phase0/code/) | 下載、載入、原始資料準備與共用計算。 | 從專案根目錄執行 Python 模組。 |
| [Phase 0 計畫](phases/phase0/docs/plans/PLAN.md) | 共用基礎的範圍。 | 新增共用來源時先看此處。 |

## Phase 交付

| Phase | 狀態 | 資料位置與主要檢查點 | 閱讀入口 |
| --- | --- | --- | --- |
| Phase 1（三年） | [working] | [SQLite](phases/phase1/data/sqlite/)：`swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite` 是 mean-element checkpoint；`swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite` 是逐 10 秒候選工作版。 | [狀態報告](phases/phase1/reports/phase_1_final_report.md)、[現行執行計畫](phases/phase1/docs/plans/phase_1_execution_plan.md)、[資料血緣](phases/phase1/docs/lineage/orbit_analysis.md) |
| Phase 1R（十二年） | [working] | [SQLite](phases/phase1r/data/sqlite/)：`swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite` 是 mean-element checkpoint；`swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite` 是逐 10 秒候選工作版。 | [計畫](phases/phase1r/docs/plans/PLAN.md)、[工作報告](phases/phase1r/reports/orbit_analysis_report_2014_2026.md) |
| Phase 2（三年） | [final] | [SQLite 檢查點鏈](phases/phase2/data/sqlite/)：P2.0 至 P2.6；最終檔為 `swarm_a_phase2_sme_p2_6_final.sqlite`。 | [最終報告](phases/phase2/reports/phase_2_final_report.md)、[資料血緣](phases/phase2/docs/lineage/phase_2_storm_dataset.md) |
| Phase 2R（十二年） | [final] | [SQLite 檢查點鏈](phases/phase2r/data/sqlite/)：P2R.0 至 P2R.6；最終檔為 `swarm_a_phase2r_p2r_6_final_v1.sqlite`。 | [最終報告](phases/phase2r/reports/phase_2r_final_report.md)、[資料血緣](phases/phase2r/docs/lineage/phase_2r_12year_replication.md) |
| Phase 3（三年） | [final] | [SQLite](phases/phase3/data/sqlite/) 與 [分析 CSV](phases/phase3/data/analysis/)；M1 分鐘結果在 `swarm_a_phase3_prediction_tau465_exploratory.sqlite`，逐場 $R_k$ 校準依最終報告。 | [最終報告](phases/phase3/reports/phase_3_final_report.md)、[資料血緣](phases/phase3/docs/lineage/phase_3_25_storm_prediction.md) |
| Phase 4 | [plan] | 尚無程式或資料輸出；新結果寫入 Phase 4 自己的目錄。 | [計畫](phases/phase4/docs/plans/PLAN.md) |

Phase 1／1R 的候選資料尚未校準為正式衰減率。舊 10 分鐘分支只供歷史比較，不作現行輸入。Phase 2、2R、3 的結案檢查點不回寫。

## 文件與維護

| 位置 | 用途 |
| --- | --- |
| [報告索引](docs/reports.md) | 各 Phase 報告與分析輸出的詳細入口。 |
| [資料血緣索引](docs/data_lineage/README.md) | 來源、轉換與各 Phase 血緣入口。 |
| [資料血緣規則](docs/data_lineage/RULES.md) | 撰寫和修改血緣文件時的格式與資料契約。 |
| [寫作規則](docs/writing_style.md) | 專案 Markdown 格式。 |
| [ISSUE.md](ISSUE.md) | 已確認、暫不處理的問題。 |
| [TIMELOG.md](TIMELOG.md) | 歷史決策與執行紀錄。 |

本機暫存資料放在 `tmp/`，不屬於正式交付。SQLite 與大部分原始來源不提交 Git；檔案清單以本機資料夾為準。
