# Phase 7 V2：2022 年末與 2023 年初三場磁暴

狀態：[done: exploratory external-event validation]。

目前採用[五場逐圈計分](../phase7-v3/reports/five_storm_orbit_scores.md)，排除 2018 年事件；本目錄原先的六日終點分數保留作歷史對照。

Phase 7 V2 以獨立 SQLite 輸出處理 `S20221107T1720`、`S20230227T1212`、
`S20230324T0521`。它重用 frozen Phase 0–6 的方法與參數，不改寫兩事件
`../phase7/`。三場中 Ridge density 僅在 2023-02-27 優於直接 M0；Ridge 的三場
下降 MAE/RMSE 都高於 M0，因此不升級為下游模型。

- [最終報告](reports/phase_7_late_2022_early_2023_three_storms_report.md)
- [資料血緣](docs/lineage/phase_7_late_2022_early_2023_three_storms.md)
- [執行計畫](docs/plans/phase_7_late_2022_early_2023_three_storms_plan.md)
- [比較圖](figures/phase7_late_2022_early_2023_three_storms.png)
- 個別圖：`S20221107T1720`、`S20230227T1212`、`S20230324T0521`
