# Phase 5 Trial9：跨磁暴共用的逐圈 GPR

狀態：[working]。沿用 Trial2 的五折 20 場訓練／5 場完整測試名單。四輸入 GPR 在 2,115 個與 Trial8 相同的圈上，對數 RMSE 為 0.03926；直接沿用上一圈誤差為 0.04211。整場有 17/25 場改善；磁暴中心前後 24 小時只有 13/25 場改善。

- [方法、結果與限制](reports/trial9_pooled_orbit_gpr_report.md)
- [25 場同位置 RMSE](figures/trial9_pooled_rmse.png)
- [磁暴中心前後 24 小時 RMSE](figures/trial9_t0_48h_rmse.png)
- [逐圈預測](data/analysis/trial9_pooled_predictions.csv)
- [逐場指標](data/analysis/trial9_pooled_event_metrics.csv)
- [五折指標](data/analysis/trial9_pooled_fold_metrics.csv)
- [五折模型清單](data/models/manifest.json)、[供日後使用的 25 場模型清單](data/models/final_manifest.json)
- [載入已訓練模型](code/load_trial9_gpr_model.py)：在本機有模型檔時，推論不需重新訓練。
- [重算入口](code/prep_trial9_pooled_orbit_gpr.py)

模型 `.joblib` 檔保存在本機 `data/models/`，因體積較大不納入 Git；清單與[重建五折模型](code/prep_trial9_save_models.py)、[重建 25 場模型](code/prep_trial9_save_final_model.py)程式保留在專案。五折模型只用於重現留場測試；25 場模型供日後新資料使用，不能回頭評分這 25 場。
