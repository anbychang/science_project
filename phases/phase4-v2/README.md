# Phase 4 v2：共同 tau 密度基線

狀態：[done: descriptive]。現行描述性密度基線使用 25 場共同 $\tau=4.75$ h；各場 $R_k$ 與共同 $G$ 重新擬合。完整輸出是 214,907 個分鐘錨點。讀取本目錄 `data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite`，表為 `phase4_v2_minute`。方法與數值見[結果報告](reports/shared_tau_grid_report.md)，資料契約見[血緣](docs/lineage/phase4_v2_shared_tau.md)。

每場新的 $R_k$ 讀同一個 SQLite 的 `phase4_v2_events.r_fit`；[報告內的 25 場表格](reports/shared_tau_grid_report.md)列出六位小數。逐分鐘表也保存同場的 `r_fit`，計算使用完整精度。這些值是在固定 $\tau=4.75$ h 下重新擬合，不沿用 v1 的 $R_k$。

Phase 4 v1 的自由 $\tau_k$ D-model 保留在 `../phase4/`。Phase 5 的既有輸出仍依 v1；其他舊結果須依各自來源辨識，不能直接改標為 v2。v2 仍使用同場 L2 擬合，不能作無 L2 的預報輸入。
