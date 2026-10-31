# Phase 5 Trial 13：無同場 L2 的 M1-GPR 統一核對

狀態：[done]。這是 Trial 10–12 已保存留場預測的**統一比較**，沒有再訓練一個 GPR。只用對數密度 RMSE 評分：相同 25 場、2,235 圈的 M1 為 **0.20663**，三版 GPR 依序為 **0.21960、0.21922、0.21395**。三版都變差，不採用。

- [核對方法、完整數字與結論](reports/trial13_m1_gpr_final_audit.md)
- [Phase 5 無同場 L2 終版決定](../phase5/reports/phase_5_report.md)
- `data/sqlite/swarm_a_phase5_m1_gpr_comparison_v1.sqlite`：本機衍生結果，不納入 Git

在專案根目錄執行 `python phases/phase5-trial13/code/prep_gpr_comparison.py` 重算 SQLite。它只讀 Trial 10–12 的保存結果，不重訓模型；入口拒絕覆寫既有結果。
