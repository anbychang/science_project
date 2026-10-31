# Phase5 Trial1--Trial7 計畫：Trial4 殘差模型

狀態：[done]。Phase 5 接續 `Phase 2 -> Phase 3 -> Trial4`。Trial4 的 D-model 固定每場 $R_k$、$\tau_k$ 與共同 $G$；Phase 5 不重估這些參數，只描述 Trial4 尚未解釋的對數密度殘差。

Trial6 的獨立工作空間與[完整執行計畫](../../../phase5-trial6/docs/plans/PLAN.md)已建立，狀態：[done]。它以每圈時間與日側有效樣本比例，檢查同場事後殘差補值；另遮住 $t_0$ 前後三小時與非 $t_0$ 強烈 SYM-H 變化區。結果未顯示穩定 Ridge 優勢，詳見[Trial6 報告](../../../phase5-trial6/reports/trial6_within_storm_ridge_report.md)。

Phase 5 現行採用版已選定，見[採用版報告](../../reports/phase_5_report.md)。本計畫保留 Trial1--Trial7 的歷史問題與結果；Trial1 是資料內描述，Trial2--Trial5 是 held-out 檢查，五者都不是現行方法。

## Phase5 Trial1：資料內描述 [done]

```text
Trial4 minute baseline + P2.6 paired DNSAPOD altitude
  -> one u +/- pi anchor near each 2pi grid point
  -> five-feature zero-mean GPR on all 25 storms
  -> Trial4+GPR descriptive curves and conditional intervals
```

目標是 `residual_log_density=ln(rho_L2_phase/rho_Trial4_phase)`。五個特徵是 `{H_tau_k, H_24h, SME, SYM-H, altitude_phase_m}`。高度先按與 P2.6 density 相同的 paired native DNSAPOD samples 平均，再用相同的中心 $u\pm\pi$ 窗口與 paired count 加權。

這是資料內回溯描述：Trial4 已使用同一批事件期間 L2 擬合每場基線，Phase 5 也在同一批一圈錨點上 `fit` 與 `predict`。不得把 RMSE、MAE、區間涵蓋率或圖形改稱成留一場、外測或即時預報證據。高度 length scale 碰到下界時，必須視為過度貼合或資料問題診斷，不得當成高度因果結論。

## Phase5 Trial2：20/5 storm-group 驗證 [done]

Trial2 讀取 Trial1 已保存的 2,295 個一圈錨點，不重新準備 DNSAPOD 或 Trial4。固定 seed 的五折 `GroupKFold` 每折以 20 場 storm fit scaler 與 GPR，對另外 5 場完整 storm 預測；每個 anchor 只作一次 held-out 預測。Trial4 D-model 仍由全部 25 場校準，因此這只測試殘差 GPR 跨 storm 的泛化，不是整條 Trial4+GPR 的端到端外測。

整體 held-out RMSE 是 0.11028，略高於 Trial4 的 0.11005；GPR 沒有實質泛化增益。Trial1 的 0.02029 資料內 RMSE 不能用於模型有效性主張。詳見 [Trial2 報告](../../../phase5-trial2/reports/phase_5_trial4_groupcv20_5_report.md)。

## Phase5 Trial3：nested 四特徵 GPR [done]

Trial3 將高度移出 GPR，只保留 `{H_tau_k, H_24h, SME, SYM-H}`。每個 outer 20/5 split 的 20 場 storm 內再做 four-fold 15/5 split，選擇 RBF 或 Matérn 3/2 kernel，再對 outer 5 場預測。這避免用同一個 outer test storm 選 kernel，但仍是同一組 25 場的回溯 trial，不是 Final。

整體 held-out RMSE 是 0.12014，差於 Trial4 的 0.11005；移除高度雖解除 Trial2 的局部化，卻沒有產生可移轉的殘差修正。詳見 [Trial3 報告](../../../phase5-trial3/reports/phase_5_trial4_nested_groupcv_report.md)。

## Phase5 Trial4：時間、tau、季節 GPR [done]

Trial4 以每場 event UTC 時刻起算 `relative_time_hours`，保留固定 Phase 4 `tau_hours`，並以 UTC 年內週期座標表達季節。外層 20/5 split 與 Trial3 相同；每個 outer training split 內以 15/5 split 選 RBF 或 Matérn 3/2。`tau_hours` 已由同一事件的 Phase 4 密度擬合，因此這只可做 retrospective 描述。

整體 held-out RMSE 是 0.11323，仍差於 Trial4 的 0.11005。五個最終 fit 都有一個 convergence warning；沒有充分證據繼續調參。詳見 [Trial4 報告](../../../phase5-trial4/reports/phase_5_time_tau_season_report.md)。

## Phase5 Trial5：新 geomagnetic driver GPR [done]

Trial5 只使用新增的 `{dSYM-H/dt, ap_step, F10.7}`。每個值以 Trial1 anchor 的 `storm_id,time_us` 直接對回 P2.6 minute feature；`dSYM-H/dt` 是 backward difference。outer 20/5 與 inner 15/5 kernel selection 沿用 Trial3/4。

整體 held-out RMSE 是 0.13203，明顯差於 Trial4 的 0.11005。此類 driver 不再進行任意 GPR feature mix；詳見 [Trial5 報告](../../../phase5-trial5/reports/phase_5_trial5_driver_report.md)。

## Trial1--Trial5 特徵貢獻整理 [done]

五個 trial 的共同 held-out 基準、特徵組合的 RMSE 差值與單一特徵不可識別的限制，已固定於[特徵貢獻整理](../../../phase5-trial2/reports/phase_5_feature_contribution_summary.md)。這批特徵組合沒有進入現行採用版。

## 單一特徵 GPR 消融 [done]

同一個五折 20/5 split 下，已對五個 Trial1 特徵各做 `only-feature` 與 `drop-feature` held-out GPR。完整五欄仍比 Trial4 差；消融只補足各欄在這個 GPR 中的探索性條件訊號，不改變這組舊特徵不被採用的決策。詳見[單一特徵 GPR 消融](../../../phase5-trial2/reports/phase_5_feature_ablation_report.md)。

## Phase5 Trial7：一分鐘移動平均展示 [done]

Trial7 先以 `S20240511T0214` 作中心 61 分鐘移動平均展示，確認它包含被評分的當分鐘 L2，不能作為預測證據。隨後改成只用前 60 個連續有效分鐘的殘差，在 25 場原生一分鐘資料上評分；20/25 場改善，合併對數 RMSE 由 0.18056 降至 0.15374。Trial4 D-model 參數保持固定，套用到一分鐘 quiet-MSIS 與 SME 響應；它是一分鐘點尺度延伸，不是原本每分鐘更新的一圈平均輸出的重命名。結果與圖見 [25 場 Trial7 報告](../../../phase5-trial7/reports/trial7_25storm_past_mean_report.md)。因為 Trial4 原參數仍用全事件 L2 擬合，結果不能稱為獨立預測。
