# Phase 7：五場磁暴逐圈計分

共用符號與單位：[VARIABLES.md](../../VARIABLES.md)。

狀態：[done: exploratory external-event validation]。目前研究集合為 2021-11-04、2022-03-13、2022-11-07、2023-02-27、2023-03-24。五場計分端點均早於 P6.1 的 `B_eff` 擬合起點 2023-07-01；Ridge 使用全 25 場重擬合參數，但事件特徵及 quiet F10.7A 仍是回溯量，不能稱事前預報。2018-08-26 的舊試算保留在 `runs/earlier_storms/`，不進計分。

目前以[五場逐圈計分報告](reports/five_storm_orbit_scores.md)為主結果。正式比較每場磁暴一票：Ridge 贏 4 場，M0 贏 1 場；五場等權平均 orbit MAE 為 M0 `5.309`、Ridge `5.304 m/orbit`。453 個圈間區間是底層資料；兩模型平均只差約 `0.005 m/orbit`，不能判定有穩定優勢。五場結果 SQLite 在 `data/sqlite/swarm_a_five_storm_orbit_scores_v1.sqlite`，僅存本機。

- [五場計分](reports/five_storm_orbit_scores.md)
- [三場密度與下降報告](runs/three_storms/reports/phase_7_late_2022_early_2023_three_storms_report.md)
- [較早事件研究紀錄](runs/earlier_storms/reports/earlier_three_storms.md)
- [原兩場歷史報告](reports/phase_7_early_2023_two_storms_report.md)
