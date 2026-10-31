# Phase 5 Trial 11：只學 M1 誤差曲線形狀的 GPR

狀態：[done]。25 場磁暴五折整場留出，使用四個不含 L2 的輸入，讓 GPR 學每場平均值之外的誤差升降。對數密度 RMSE：M1 **0.20663**，GPR **0.21922**；五折全部變差，只有 7/25 場改善。不採用這版修正。

- [完整方法、五折分數與限制](reports/trial11_temporal_shape_gpr_report.md)
- [25 場 L2、M1、GPR 密度曲線](figures/temporal_shape_gpr_25storm_overview.png)
- [SQLite 留場結果](data/sqlite/swarm_a_phase5_temporal_shape_gpr_v1.sqlite)：本機產物，不納入 Git

在專案根目錄執行 `python phases/phase5-trial11/code/prep_temporal_shape_gpr.py` 產生 SQLite；不覆寫現有檔案。執行 `python phases/phase5-trial11/code/prep_temporal_shape_figures.py` 從結果重畫圖，不重訓 GPR。這是獨立實驗，結果納入[Phase 5 最終判定](../phase5/reports/phase_5_report.md)。
