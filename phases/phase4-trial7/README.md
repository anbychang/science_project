# Phase 4 Trial7：一分鐘密度殘差移動平均

狀態：[done]。主結果使用 25 場原生配對後的一分鐘 Swarm-A L2 密度，將 Phase 3 Trial 4 的固定參數代入一分鐘輸入，只以當下以前 60 分鐘的對數殘差估計修正。20/25 場整場對數 RMSE 改善；Trial 4 的事件參數仍使用完整 L2 擬合，因此不屬獨立預測。先前單場中心移動平均只保留為事後平滑展示。

- [25 場結果、逐場圖與界線](reports/trial7_25storm_past_mean_report.md)
- [25 場對數 RMSE 圖](figures/trial7_25storm_past_mean_rmse.png)
- [單場中心移動平均展示](reports/trial7_minute_moving_average_report.md)
- [真正的一分鐘比較圖](figures/trial7_s20240511t0214_raw_minute.png)
- [每分鐘更新的一圈平均對照圖](figures/trial7_s20240511t0214_moving_average.png)
