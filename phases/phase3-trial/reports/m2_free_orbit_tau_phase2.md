# M2 逐圈自由 \(\tau_j\) 試驗

狀態：[superseded]。本試驗使用完整 M0（實際 `ap`），不符合後來確認的「完全沿用 M1 平靜 MSIS、只改逐圈 \(\tau_j\)」定義。正確試驗見 [M1 平靜 MSIS 逐圈時間常數試驗](m1_variable_orbit_tau_trial.md)。以下僅保留歷史試算紀錄。

## 決定與範圍

- 每場事件依 Phase 2 的連續軌道相位 \(u\) 劃分不重疊軌道段：\(j=\lfloor u/(2\pi)\rfloor\)。每段單獨估計一個 \(\tau_j\)，不預設它由 SME 決定，也不強迫各段數值互異。
- 只處理 25 場事件窗口；主線 Phase 3 報告與資料不變。這是使用事件期間 L2 的資料內試驗，不能當作預報能力或逐圈物理時間常數的測量。
- 為隔離 \(\tau\) 的影響，沿用先前 M2 試驗逐場的 \(R_k\) 和共用的 \(G=2.2410076898631752\times10^{-4}\,\mathrm{nT}^{-1}\)；這兩者並非本試驗重新估計。

## 計算

每分鐘輸入 \(q_t=\mathrm{SME}_t-65\,\mathrm{nT}\)。在第 \(j\) 個軌道段內，使用

\[
H_t=e^{-\Delta t/\tau_j}H_{t-1}+(1-e^{-\Delta t/\tau_j})q_t,
\qquad \Delta t=1\,\mathrm{min}.
\]

\(\tau_j=0\) 時令 \(H_t=q_t\)。\(H\) 在相鄰軌道段間延續；事件窗口第一分鐘的初值取自此前的連續固定 3.5 小時 SME 遞迴。窗口以外沒有建立逐圈變動的 \(\tau\) 序列。沿用 Phase 2 的 \(u\pm\pi\) 相位配對與有效資料條件，先算逐分鐘 \(H\)，再求相位平均 \(\overline H_i\)。預測及殘差為

\[
\rho_{M2,i}=R_k\rho_{M0,i}\exp(G\overline H_i),\qquad
e_i=\ln\!\left(\frac{\rho_{L2,i}}{R_k\rho_{M0,i}}\right)-G\overline H_i.
\]

每個 \(\tau_j\) 可選 \(0,0.5,\ldots,10\) 小時。從全部 \(3.5\) 小時開始，逐段試遍 21 個候選值；評分使用整場事件的 \(\sum_i e_i^2\)，因此該段對後續 \(H\) 的影響也納入。重複掃描直到整輪沒有參數改變，最多 10 輪。這是座標下降的局部解，不保證全域最小值。

## 結果與判讀

| 項目 | 結果 |
| --- | ---: |
| 事件 / 軌道段 / 有效分鐘 | 25 / 2,325 / 214,907 |
| 固定 3.5 小時的整體對數密度 RMSE | 0.105434 |
| 逐圈自由 \(\tau_j\) 的整體對數密度 RMSE | 0.079678 |
| RMSE 相對下降 | 24.4% |
| 選到 0 小時的軌道段 | 353（15.2%） |
| 選到 10 小時的軌道段 | 1,575（67.7%） |
| 選到任一搜尋邊界的軌道段 | 1,928（82.9%） |
| 在 10 輪內停止的事件 | 25 / 25 |

資料內誤差下降，但絕大多數 \(\tau_j\) 卡在邊界。這些值主要是擬合自由度的結果，不能解讀為熱層在這些圈真的具有 0 或 10 小時的響應時間。每圈約 90 分鐘，單圈及相位平均後的密度資料對數小時的記憶時間辨識不足；固定的 \(R_k\)、\(G\)、基準 SME 與 MSIS 誤差也可能被自由 \(\tau_j\) 吸收。此試驗支持「放開逐圈參數可改善資料內擬合」，不支持「已量出可靠的逐圈時間常數」。

## 資料與驗證

- 25 場逐圈圖：`phases/phase3-trial/figures/m2_free_tau_25_events.png`；全體分布圖：`phases/phase3-trial/figures/m2_free_tau_distribution.png`。
- 輸出：`phases/phase3-trial/data/sqlite/swarm_a_m2_free_orbit_tau_phase2_v1.sqlite`。
- `m2_free_tau_orbit` 存每圈 \(\tau_j\)；`m2_free_tau_event` 存逐場誤差及邊界數；`m2_free_tau_sweep` 存每輪變化；`m2_free_tau_minute` 存逐分鐘相位平均響應、M0、M2 與 L2。全部輸出另存為 derived tables。
- Phase 2 提供 SME；Phase 3 的 `swarm_a_phase3_h_tau_phase_v1.sqlite` 提供 \(u\) 與相位配對。M0/L2 配對密度取自先前獨立 M2 試驗 `swarm_a_m2_r_grid_trial_v1.sqlite` 的保存副本；\(R_k,G\) 取自 `swarm_a_m2_alternating_v1.sqlite`。
- SQLite `PRAGMA integrity_check` 為 `ok`；`phases/phase3-trial/tests` 共 7 個測試通過，其中包括兩段已知 \(\tau\) 的遞迴檢查。
