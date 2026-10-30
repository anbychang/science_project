# Phase4 Trial3：nested storm-group 四特徵 GPR

## 結論

狀態：[done]。Trial3 移除高度後仍沒有改善 Trial4；nested 20/5 held-out 對數 RMSE 是 0.12014，高於 Trial4 的 0.11005，也高於 Trial2 的 0.11028。四個 geomagnetic 特徵的 GPR 會對未見 storm 做錯修正，不能進入 Phase4 Final。

## 方法與邊界

Trial3 只讀取 Trial1 的 2,295 個一圈錨點與固定 Trial4 D-model。外層是原本的五折 20-train/5-test storm split。每個外層 20 場再用四折 15-train/5-validation 選擇 `geomagnetic_rbf` 或 `geomagnetic_matern32`；兩個候選都只使用 `{H_tau_k, H_24h, SME, SYM-H}`，不使用高度。外層的 5 場 storm 完全不參與該折的 kernel 選擇或 fit。

RBF 在外層 fold 1、2、5 被選中，Matérn 3/2 在 fold 3、4 被選中。內層選擇不穩定，沒有一個 kernel 一致勝出。Trial4 D-model 仍由全部 25 場校準，因此 Trial3 只檢查殘差 GPR，並非完整 Trial4+GPR 端到端外測。

| 指標 | Trial4 | Trial2 五特徵 | Trial3 nested 四特徵 |
| --- | ---: | ---: | ---: |
| held-out 對數 RMSE | 0.11005 | 0.11028 | 0.12014 |
| held-out 對數 MAE | 0.07955 | 0.07950 | 0.08777 |
| 95% conditional coverage | — | 95.42% | 87.76% |

Trial3 在五折的 RMSE 是 0.12895、0.08961、0.11385、0.12676、0.13603；只有 fold 3、5 比 Trial4 小，其餘三折明顯變差。拿掉高度解除了 Trial2 的近鄰遮斷，但沒有留下可跨 storm 預測的殘差訊號。

## 決定

Phase4 GPR 目前有兩個互補的負結果：五特徵 ARD-RBF 會被高度局部化而退回零修正；四特徵 nested GPR 則產生有害的跨 storm 修正。Phase4 Final 仍是 [not created]，不可把 Trial1、Trial2 或 Trial3 的結果升格為最終模型。

## 輸出與重算

- [逐場指標](../data/analysis/phase4_trial4_trial3_event_metrics.csv)
- [外層 fold 指標](../data/analysis/phase4_trial4_trial3_fold_metrics.csv)
- [內層 model selection](../data/analysis/phase4_trial4_trial3_inner_selection.csv)
- [outer fold 指派](../data/analysis/phase4_trial4_trial3_folds.json)
- [資料血緣](../docs/lineage/phase_4_trial4_nested_groupcv.md)
- [重算入口](../code/prep_phase4_trial4_trial3.py)

本機 SQLite 不納入 Git；重算入口拒絕覆寫既有 v3 輸出。
