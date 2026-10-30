# Phase4 Trial 與 Final 保留位

目前只有兩個已完成 trial：

- Trial1：Trial4 固定基線上的五特徵資料內 GPR。
- Trial2：Trial1 的 20/5 storm-group held-out 檢查；沒有改善 Trial4 RMSE。
- Trial3：nested 20/5 storm-group 的四特徵 GPR；RMSE 0.12014，劣於 Trial4 的 0.11005。
- Trial4：時間、固定 Trial4 tau、季節的 nested GPR；RMSE 0.11323，仍劣於 Trial4。
- Trial5：`dSYM-H/dt`、`ap_step`、`F10.7` nested GPR；RMSE 0.13203，明顯劣於 Trial4。

Phase4 Final 狀態：[not created]。它保留給後續通過明確驗收條件的方法；不得重用 Trial1--Trial5 的成績宣稱 final。

Trial1--Trial5 的共同比較、每個特徵目前可主張的貢獻，以及不可主張的範圍，見[特徵貢獻整理](reports/phase_4_feature_contribution_summary.md)。
