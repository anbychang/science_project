# Phase4 Trial1--Trial5：特徵貢獻整理

狀態：[done]。目前沒有任何 Phase4 特徵組合能穩定改善固定 Trial4 D-model；Phase4 Final 維持 `[not created]`。現有試驗只能判定「特徵組合」的 held-out 貢獻，不能把每個單一特徵誠實拆成獨立 RMSE 貢獻，因為沒有做預先定義的單欄消融。

## 共同比較基準

Trial2--Trial5 都以相同 25 場 storm 的 2,295 個 anchors，做 20-train/5-test storm-group held-out 評估。固定 Trial4 D-model 的對數 RMSE 是 0.11005；較低才是改善。Trial4 D-model 本身已用這 25 場擬合，因此這些結果只驗證殘差 GPR 能否跨 storm，並非整條密度模型的端到端外測。

| Trial | 特徵組合 | 評估 | RMSE | 相對 Trial4 | 結論 |
| --- | --- | --- | ---: | ---: | --- |
| 1 | `H_tau_k, H_24h, SME, SYM-H, altitude` | 同資料 fit/predict | 0.02029 | -0.08976 | 只證明可記住資料，不能算貢獻 |
| 2 | 同 Trial1 五特徵 | 固定 20/5 | 0.11028 | +0.00023 | 整組近乎零貢獻 |
| 3 | `H_tau_k, H_24h, SME, SYM-H` | nested 20/5 | 0.12014 | +0.01009 | 整組造成有害修正 |
| 4 | `relative_time, tau, season_sin, season_cos` | nested 20/5 | 0.11323 | +0.00318 | 整組沒有泛化增益 |
| 5 | `dSYM-H/dt, ap_step, F10.7` | nested 20/5 | 0.13203 | +0.02198 | 整組明顯有害 |

Trial1 和 Trial2--Trial5 不能直接比較：Trial1 的資料內分數不是 held-out 分數。

## 特徵帳本

| 特徵 | 出現的 Trial | 現有證據 | 可下的結論 |
| --- | --- | --- | --- |
| `H_tau_k` | 1, 2, 3 | Trial2 五特徵無改善；Trial3 四特徵變差；ARD 平均尺度為 0.598 SD | 未證明跨 storm 貢獻；不能單獨判定好或壞 |
| `H_24h` | 1, 2, 3 | 同上；Trial2 的資料內 ARD 平均尺度為 0.285 SD | 在資料內是四個 geomagnetic 欄位中較局部敏感者；不是泛化貢獻或因果排序 |
| `SME` | 1, 2, 3 | 同上；ARD 平均尺度為 3.309 SD | 資料內敏感度最低；沒有獨立外測增益 |
| `SYM-H` | 1, 2, 3 | 同上；ARD 平均尺度為 0.844 SD | 沒有獨立外測增益 |
| `altitude` | 1, 2 | Trial2 每折 ARD 都卡在 0.010 SD 下界；fold 3、4 有約 20% 測試高度超出訓練範圍 | 強烈資料內局部插值跡象；不能當作高度因果，亦未證明可轉移貢獻 |
| `relative_time_hours` | 4 | 與 `tau`、季節合併後 RMSE 變差 | 沒有獨立貢獻估計 |
| `tau_hours` | 4 | 同上；它來自同一場 Trial4 密度擬合 | 只能做 retrospective 描述，不可當未見 storm 的預報輸入 |
| `season_sin`, `season_cos` | 4 | 同上 | 沒有獨立貢獻估計 |
| `dSYM-H/dt` | 5 | 與其餘新 driver 合併後明顯變差；只有 23 個值 | 時間解析度或量化程度不足以支持此 GPR；沒有獨立貢獻估計 |
| `ap_step` | 5 | 同上；只有 28 個值 | 離散且資訊不足；沒有獨立貢獻估計 |
| `F10.7` | 5 | 同上；167 個值 | 未顯示可轉移殘差訊號；沒有獨立貢獻估計 |

Trial2 的 ARD 只是 GPR 在該折訓練資料內的局部距離尺度：尺度越小，模型越容易隨該欄位改變。它不等於 RMSE 貢獻、物理效應大小或因果性。五特徵模型整體沒有 held-out 增益，因此不可用其 ARD 替任何欄位背書。

## 未納入結論的候選

`t_onset` 尚沒有明確且可重算的 onset 定義；local time 尚未由 POD 位置資料導出。兩者沒有被試驗，不能列為有效或無效特徵。

## 決策

- Phase4 Final 不採用 Trial1--Trial5 任一 GPR。
- 不再對同一 25 場任意混搭既有特徵；繼續嘗試只會把 held-out 標籤用於反覆選模。
- 若真的需要「單一特徵貢獻」，必須先鎖定一個候選模型，對未接觸的事件資料做預先定義的 leave-one-feature-out 消融；不能再使用這五個 Trial 的分數補算後宣稱為確認性結論。

## 證據

- [Trial1 資料內報告](phase_4_trial4_altitude_gpr_report.md)
- [Trial2 五特徵 held-out 報告](phase_4_trial4_groupcv20_5_report.md)
- [Trial3 四特徵 nested 報告](phase_4_trial4_nested_groupcv_report.md)
- [Trial4 時間、tau、季節報告](phase_4_time_tau_season_report.md)
- [Trial5 新 geomagnetic driver 報告](phase_4_trial5_driver_report.md)
- [Trial2 ARD 參數](../data/analysis/phase4_trial4_groupcv20_5_hyperparams.csv)
- [Trial5 新特徵 audit](../data/analysis/phase4_trial5_driver_feature_audit.csv)
