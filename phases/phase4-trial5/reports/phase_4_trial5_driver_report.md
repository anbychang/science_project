# Phase4 Trial5：新 geomagnetic driver GPR

## 結論

狀態：[done]。`dSYM-H/dt`、`ap_step`、`F10.7` 無法跨 storm 改善固定 Trial4 D-model。nested 20/5 held-out 對數 RMSE 是 0.13203，明顯差於 Trial4 的 0.11005；此 Trial 不進入 Phase4 Final。

## 方法與資料界線

Trial5 從 Trial1 的 2,295 個錨點，直接對回 Phase2.6 的同一 `storm_id,time_us` minute key。輸入只有三個新增 driver：backward `symh_rate_nt_s`、`ap_step`、前一日 `f107_sfu`。這些值不使用密度目標，但已知給定事件期間的 space-weather 記錄。

外層使用五折 20-train/5-test storm split。每個 outer training split 內再做四折 15-train/5-validation，選擇 RBF 或 Matérn 3/2。Matérn 在 fold 1、2、3、5 被選中；RBF 在 fold 4 被選中。outer test storm 不參與選擇或 fit。

| 指標 | Trial4 基線 | Trial5 新 driver |
| --- | ---: | ---: |
| held-out 對數 RMSE | 0.11005 | 0.13203 |
| held-out 對數 MAE | 0.07955 | 0.09750 |
| 95% conditional coverage | — | 90.72% |

五折 RMSE 是 0.12521、0.09309、0.12138、0.16188、0.14813。五個最終 fit 各有一個 convergence warning；沒有任何穩定改善訊號。

## 決定

不要再用同類 minute geomagnetic driver 任意組合新的 GPR。`t_onset` 與地方時仍未建立可追溯的資料契約；若要繼續，下一步是先定義 onset estimator 與從 POD 位置推導地方時，而不是開 Trial6 調 kernel。

## 輸出與重算

- [逐場指標](../data/analysis/phase4_trial5_event_metrics.csv)
- [outer fold 指標](../data/analysis/phase4_trial5_fold_metrics.csv)
- [inner kernel selection](../data/analysis/phase4_trial5_inner_selection.csv)
- [新特徵 audit](../data/analysis/phase4_trial5_driver_feature_audit.csv)
- [重算入口](../code/prep_phase4_trial5_gpr.py)

本機 SQLite 不納入 Git；重算入口拒絕覆寫既有 v5 輸出。
