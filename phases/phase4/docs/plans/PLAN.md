# Phase4 Trial1--Trial5 計畫：Trial4 殘差 GPR

狀態：[done]。Phase 4 接續 `Phase 2 -> Phase 3 -> Trial4`。Trial4 的 D-model 固定每場 $R_k$、$\tau_k$ 與共同 $G$；Phase 4 不重估這些參數，只描述 Trial4 尚未解釋的對數密度殘差。

Phase4 Final 保留給後續最終方法，狀態：[not created]。Trial1 是資料內描述，Trial2--Trial5 是 held-out 檢查；五者都不能被改稱為 final。

## Phase4 Trial1：資料內描述 [done]

```text
Trial4 minute baseline + P2.6 paired DNSAPOD altitude
  -> one u +/- pi anchor near each 2pi grid point
  -> five-feature zero-mean GPR on all 25 storms
  -> Trial4+GPR descriptive curves and conditional intervals
```

目標是 `residual_log_density=ln(rho_L2_phase/rho_Trial4_phase)`。五個特徵是 `{H_tau_k, H_24h, SME, SYM-H, altitude_phase_m}`。高度先按與 P2.6 density 相同的 paired native DNSAPOD samples 平均，再用相同的中心 $u\pm\pi$ 窗口與 paired count 加權。

這是資料內回溯描述：Trial4 已使用同一批事件期間 L2 擬合每場基線，Phase 4 也在同一批一圈錨點上 `fit` 與 `predict`。不得把 RMSE、MAE、區間涵蓋率或圖形改稱成留一場、外測或即時預報證據。高度 length scale 碰到下界時，必須視為過度貼合或資料問題診斷，不得當成高度因果結論。

## Phase4 Trial2：20/5 storm-group 驗證 [done]

Trial2 讀取 Trial1 已保存的 2,295 個一圈錨點，不重新準備 DNSAPOD 或 Trial4。固定 seed 的五折 `GroupKFold` 每折以 20 場 storm fit scaler 與 GPR，對另外 5 場完整 storm 預測；每個 anchor 只作一次 held-out 預測。Trial4 D-model 仍由全部 25 場校準，因此這只測試殘差 GPR 跨 storm 的泛化，不是整條 Trial4+GPR 的端到端外測。

整體 held-out RMSE 是 0.11028，略高於 Trial4 的 0.11005；GPR 沒有實質泛化增益。Trial1 的 0.02029 資料內 RMSE 不能用於模型有效性主張。詳見 [Trial2 報告](../../reports/phase_4_trial4_groupcv20_5_report.md)。

## Phase4 Trial3：nested 四特徵 GPR [done]

Trial3 將高度移出 GPR，只保留 `{H_tau_k, H_24h, SME, SYM-H}`。每個 outer 20/5 split 的 20 場 storm 內再做 four-fold 15/5 split，選擇 RBF 或 Matérn 3/2 kernel，再對 outer 5 場預測。這避免用同一個 outer test storm 選 kernel，但仍是同一組 25 場的回溯 trial，不是 Final。

整體 held-out RMSE 是 0.12014，差於 Trial4 的 0.11005；移除高度雖解除 Trial2 的局部化，卻沒有產生可移轉的殘差修正。詳見 [Trial3 報告](../../reports/phase_4_trial4_nested_groupcv_report.md)。

## Phase4 Trial4：時間、tau、季節 GPR [done]

Trial4 以每場 event UTC 時刻起算 `relative_time_hours`，保留固定 Phase3 Trial4 `tau_hours`，並以 UTC 年內週期座標表達季節。外層 20/5 split 與 Trial3 相同；每個 outer training split 內以 15/5 split 選 RBF 或 Matérn 3/2。`tau_hours` 已由同一事件的 Phase3 Trial4 密度擬合，因此這只可做 retrospective 描述。

整體 held-out RMSE 是 0.11323，仍差於 Trial4 的 0.11005。五個最終 fit 都有一個 convergence warning；沒有充分證據繼續調參。詳見 [Trial4 報告](../../reports/phase_4_time_tau_season_report.md)。

## Phase4 Trial5：新 geomagnetic driver GPR [done]

Trial5 只使用新增的 `{dSYM-H/dt, ap_step, F10.7}`。每個值以 Trial1 anchor 的 `storm_id,time_us` 直接對回 P2.6 minute feature；`dSYM-H/dt` 是 backward difference。outer 20/5 與 inner 15/5 kernel selection 沿用 Trial3/4。

整體 held-out RMSE 是 0.13203，明顯差於 Trial4 的 0.11005。此類 driver 不再進行任意 GPR feature mix；詳見 [Trial5 報告](../../reports/phase_4_trial5_driver_report.md)。

## Trial1--Trial5 特徵貢獻整理 [done]

五個 trial 的共同 held-out 基準、特徵組合的 RMSE 差值與單一特徵不可識別的限制，已固定於[特徵貢獻整理](../../reports/phase_4_feature_contribution_summary.md)。現有結果不能支持任何單一特徵或特徵組合進入 Phase4 Final。
