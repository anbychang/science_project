# Phase5 Trial4：時間、Trial4 tau、季節 GPR

## 結論

狀態：[done]。時間、固定 Trial4 `tau_hours` 與季節特徵沒有改善 Trial4 基線。nested 20/5 held-out 對數 RMSE 是 0.11323，高於 Trial4 的 0.11005；此 Trial 不進入 Phase5 Final。

## 方法與資料界線

Trial4 從 Trial1 的 2,295 個錨點建立四個特徵：每場 event 時刻起算的 `relative_time_hours`、固定 `tau_hours`、UTC 年內位置的 `season_sin` 與 `season_cos`。事件時間由 `storm_id=SYYYYMMDDTHHMM` 解析；anchor 覆蓋事件前約 47 小時到後約 96 小時。季節採用 UTC 年內連續角度，避免年末與年初的人為斷點。

外層使用與 Trial2/Trial3 相同的五折 20-train/5-test storm split。每個 outer training split 以四個 inner 15-train/5-validation split 選擇 RBF 或 Matérn 3/2，outer test storm 不參與選擇。RBF 在 fold 2、3 被選中，Matérn 3/2 在 fold 1、4、5 被選中。

`tau_hours` 是 Phase 4 對同一場 storm 密度擬合得到的參數。它已包含該事件資料，因此本 Trial 只能描述「已知 Trial4 event fit」的剩餘殘差；不是未見 storm 的預報或端到端外測。

| 指標 | Trial4 基線 | Phase5 Trial4 |
| --- | ---: | ---: |
| held-out 對數 RMSE | 0.11005 | 0.11323 |
| held-out 對數 MAE | 0.07955 | 0.08192 |
| 95% conditional coverage | — | 93.20% |

五折 RMSE 是 0.10286、0.08186、0.11727、0.12206、0.13490。fold 1、3、5 略有改善或持平，但 fold 2、4 的劣化抵消它們。五個最終 fit 各記錄一個 convergence warning；結果不支援繼續把這組 GPR 當成候選模型調參。

## 決定

目前四個 Trial 的結論一致：沒有任何 tested GPR 特徵組合穩定改善固定 Trial4 D-model。Phase5 Final 仍是 [not created]。不要再在同一批 25 場上反覆替換特徵或 kernel；那會把 retrospective trials 變成對這批事件的選模循環。

## 輸出與重算

- [逐場指標](../data/analysis/phase4_trial4_time_tau_season_event_metrics.csv)
- [outer fold 指標](../data/analysis/phase4_trial4_time_tau_season_fold_metrics.csv)
- [inner kernel selection](../data/analysis/phase4_trial4_time_tau_season_inner_selection.csv)
- [outer fold 指派](../data/analysis/phase4_trial4_time_tau_season_folds.json)
- [資料血緣](../docs/lineage/phase_5_time_tau_season.md)
- [重算入口](../code/prep_phase5_trial4_time_tau_season.py)

本機 SQLite 不納入 Git；重算入口拒絕覆寫既有 v4 輸出。
