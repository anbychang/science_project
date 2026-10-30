# Phase4 Trial2：20/5 storm-group GPR 驗證

## 結論

狀態：[done]。Phase4 Trial2 的五折 20/5 storm-group 驗證沒有顯示 GPR 可泛化改善 Trial4。全部 2,295 個 held-out anchors 的對數 RMSE 從 Trial4 的 0.11005 變成 0.11028，增加 0.00023；MAE 從 0.07955 變成 0.07950，差異小到沒有實質意義。Phase4 Trial1 的 0.02029 資料內 RMSE 是記憶同一批資料的結果，不能作為泛化效能。

## 方法與資料邊界

Trial2 直接讀取 Trial1 的 2,295 個 `{H_tau_k, H_24h, SME, SYM-H, altitude_phase_m}` 錨點與 Trial4 殘差。固定 seed 的 `GroupKFold(n_splits=5)` 依 `storm_id` 分組；每折 20 場 storm fit `StandardScaler` 和零均值 GPR，另外 5 場只 predict。五折的測試 storm 互斥，25 場各測一次。每折保留 Trial1 的 kernel、5 次 optimizer restart 與 seed。

Trial4 的 $R_{\mathrm{fit},k}$、$\tau_k$、共同 $G$ 仍是用全部 25 場得到。因此這是「固定 Trial4 基線下，殘差 GPR 能否跨 storm」的測試，不是未見 storm 的端到端 Trial4+GPR 驗證。

| 指標 | Trial4 | held-out GPR |
| --- | ---: | ---: |
| 全部 anchors 對數 RMSE | 0.11005 | 0.11028 |
| 全部 anchors 對數 MAE | 0.07955 | 0.07950 |
| 95% 條件式涵蓋率 | 無 | 95.42% |

五折 held-out RMSE 依序為 0.10409、0.08103、0.11538、0.10798、0.13581。第二折的 GPR 明顯較差；其餘折的變化也很小。沒有一個整體一致的跨 storm 改善訊號。

## 判讀

這是負結果，但比 v1 有價值。高度 ARD length scale 在五折都達 0.010 下界，表示資料內模型對高度座標的極度局部敏感，卻沒有轉成 held-out RMSE 改善。現階段不能把高度或五特徵 GPR 視為已驗證的物理修正項。

## GPR 診斷 [done]

Trial2 的失敗不是五個輸入在 held-out storm 全面離開訓練分布。每折的五維普通標準化最近鄰距離中位數是 0.30--0.42 SD；各特徵幾乎都仍在該折訓練範圍內。去除高度後，以已擬合的四個 geomagnetic ARD scale 計算，最近鄰距離中位數只有 0.20--0.33。

高度是支配失敗的單一維度。它的 fitted length scale 固定碰到 0.010 SD，即 197--226 m；各折 held-out anchor 與最近訓練 anchor 的高度差中位數則是 0.58--1.96 km。加入高度後，五維 ARD 最近鄰距離中位數升到 3.37--9.37。對 RBF kernel，這表示相關性最多約 0.003，其他折更接近零。因此 GPR 只能回到零均值，折次中位絕對修正值為 $1.5\times10^{-20}$、$2.6\times10^{-4}$、$5.7\times10^{-6}$、$1.4\times10^{-16}$、$8.3\times10^{-20}$。

這說明 Trial1 的高度擬合主要是資料內局部插值，不是可移轉的高度關係。它不是高度沒有影響的證據，也不能用來宣稱高度因果。若繼續 GPR，下一個方法必須把「不使用高度」與「對高度採取預先定義的較平滑尺度」當成候選模型，以 nested storm-group validation 選擇；不得用已曝光的 Trial2 held-out 標籤直接選 kernel 或 bounds 後再引用 Trial2 分數。

## 輸出與重算

- [held-out 25 場圖](../figures/phase4_trial4_groupcv20_5_25storm.png)：紅線只由該場未參與訓練的 GPR 產生。
- [逐場指標](../data/analysis/phase4_trial4_groupcv20_5_event_metrics.csv)：每場僅一個測試 fold。
- [折次指標](../data/analysis/phase4_trial4_groupcv20_5_fold_metrics.csv)：每折 20/5 結果。
- [fold 指派](../data/analysis/phase4_trial4_groupcv20_5_folds.json)：保存五組 train/test storm IDs。
- [核參數](../data/analysis/phase4_trial4_groupcv20_5_hyperparams.csv)：每折 GPR 的 ARD、signal、noise 與 warning count。
- [特徵分布漂移](../data/analysis/phase4_trial4_groupcv20_5_feature_shift.csv)：每折訓練／測試 feature range 與 standardized mean shift。
- [fold 幾何診斷](../data/analysis/phase4_trial4_groupcv20_5_fold_geometry.csv)：普通、含高度與移除高度的最近鄰距離。
- [逐場幾何診斷](../data/analysis/phase4_trial4_groupcv20_5_event_geometry.csv)：每場的特徵支撐、修正幅度與 RMSE。
- [資料血緣](../docs/lineage/phase_4_trial4_groupcv20_5.md)：v1 輸入、group split 與 v2 SQLite contract。
- [重算入口](../code/prep_phase4_trial4_groupcv.py)：拒絕覆寫既有 v2 輸出。
- [診斷重算入口](../code/prep_phase4_trial4_groupcv_diagnostics.py)：只讀既有 Trial1／Trial2 輸出，拒絕覆寫診斷 CSV。

完整五折重算約需 80 分鐘 CPU；本機 SQLite 不納入 Git。
