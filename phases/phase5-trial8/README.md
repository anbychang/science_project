# Phase 5 Trial8：用上一圈誤差估計下一圈

狀態：[working]。25 場磁暴的一圈一點測試已完成。單輸入與指定四輸入 GPR 都比固定 Trial4 D-model 好，但整體不如直接沿用上一圈誤差；目前不能把 GPR 當成較好的正式修正方法。

- [方法、結果與限制](reports/trial8_next_orbit_gpr_report.md)
- [25 場同位置 RMSE 圖](figures/trial8_next_orbit_rmse.png)
- [四輸入版的四方法比較圖](figures/trial8_four_feature_rmse.png)
- [逐場預測與誤差](data/analysis/trial8_next_orbit_predictions.csv)
- [逐場分數](data/analysis/trial8_next_orbit_metrics.csv)
- [四輸入版逐場分數](data/analysis/trial8_four_feature_metrics.csv)
- [重算入口](code/prep_trial8_next_orbit_gpr.py)
- [四輸入版重算入口](code/prep_trial8_four_feature_gpr.py)
