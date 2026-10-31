# Phase 5 Trial 10：只看 Phase 3 M1 形狀的 GPR

狀態：[done]。25 場完整磁暴五折留出測試已完成。GPR 的三個輸入都由 Phase 3 M1 密度計算；整體對數 RMSE 從 M1 的 0.20663 升到 0.21960，因此不採用這版修正。

- [方法、五折結果與限制](reports/trial10_m1_shape_gpr_report.md)
- [25 場 L2、M1、GPR 折線圖](figures/m1_shape_gpr_25storm_overview.png)
- [逐場 RMSE 變化圖](figures/m1_shape_gpr_event_rmse_change.png)
- [SQLite 結果](data/sqlite/swarm_a_phase5_m1_shape_gpr_v1.sqlite)：本機產物，不納入 Git

在專案根目錄執行 `python phases/phase5-trial10/code/prep_phase5_m1_shape_gpr.py` 產生 SQLite；程式不覆寫現有結果。執行 `python phases/phase5-trial10/code/prep_phase5_m1_shape_figures.py` 從 SQLite 重畫兩張圖，不重新訓練。

這是以凍結的 Phase 3 M1 作歷史對照；[Phase 5 最終報告](../phase5/reports/phase_5_report.md)將本結果與 Trial11--Trial13 一起判讀，不把它升格為無同場 L2 的修正模型。
