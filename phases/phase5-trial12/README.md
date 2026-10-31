# Phase 5 Trial 12：用 M1 峰值與累積密度描述整場磁暴

狀態：[done]。沿用 Trial 11 的 GPR 與五折整場留出，只替換四個輸入。25 場合計的對數密度 RMSE 從 M1 的 **0.20663** 升到 GPR 的 **0.21395**；9/25 場改善。這版不作無同場 L2 的 Phase 5 終版修正。

- [方法、五折結果與判定](reports/trial12_peak_context_gpr_report.md)
- [25 場 L2、M1、GPR 密度曲線](figures/peak_context_gpr_25storm_overview.png)
- `data/sqlite/swarm_a_phase5_peak_context_gpr_v1.sqlite`：本機衍生結果，不納入 Git

在專案根目錄執行 `python phases/phase5-trial12/code/prep_peak_context_gpr.py` 產生 SQLite；不覆寫現有結果。執行 `python phases/phase5-trial12/code/prep_peak_context_figures.py` 重畫兩張圖，不重訓 GPR。
