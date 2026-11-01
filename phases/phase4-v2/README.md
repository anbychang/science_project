# Phase 4 v2：共同 tau 密度基線

狀態：[done: descriptive]。現行描述性密度基線使用 25 場共同 $\tau=4.75$ h；各場 $R_k$ 與共同 $G$ 重新擬合。完整輸出是 214,907 個分鐘錨點。讀取本目錄 `data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite`，表為 `phase4_v2_minute`。方法與數值見[結果報告](reports/shared_tau_grid_report.md)，資料契約見[血緣](docs/lineage/phase4_v2_shared_tau.md)。

Phase 4 v1 的自由 $\tau_k$ D-model 保留在 `../phase4/`。Phase 5、Phase 6 既有輸出及重算腳本仍指定 v1；它們不是 v2 的驗證結果。v2 仍使用同場 L2 擬合，不能作無 L2 的預報輸入。
