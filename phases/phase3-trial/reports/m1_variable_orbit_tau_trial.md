# M1 平靜 MSIS 逐圈時間常數試驗

## 決定與狀態

狀態：[trial]。完全沿用 Phase 3 主線 M1 的平靜 MSIS、每場既定 \(R_k\)、共用 \(G\)、SME 參考值及 \(u\pm\pi\) 相位平均；唯一變更是把共用 \(\tau=4.65\) 小時改成每個不重疊軌道段各自的 \(\tau_j\)。Phase 3 主線保持唯讀。本試驗先前誤用完整 M0 的版本不適用於此問題。

## 輸入與計算

- 25 場事件、214,907 個有效相位錨點；以 Phase 2 的連續 \(u\) 每增加 \(2\pi\) 劃一段，共 2,325 段。
- 背景密度取主線 `phase3_prediction_minute.rho_msis_quiet_phase_kg_m3`，其 MSIS 七個 `ap` 欄位固定為 4。L2 密度、\(R_k\) 也取主線同一 SQLite。共用 \(G=0.0007032326071208369\,\mathrm{nT}^{-1}\) 取主線 \(\tau=4.65\) 小時的格點紀錄。
- 一分鐘輸入 \(q_t=\mathrm{SME}_t-65\,\mathrm{nT}\)，負值保留。第 \(j\) 段內 \(H_t=e^{-1/(60\tau_j)}H_{t-1}+(1-e^{-1/(60\tau_j)})q_t\)；\(\tau_j=0\) 時 \(H_t=q_t\)。\(H\) 跨段延續；窗口起點前的初值沿用連續 4.65 小時濾波。
- 先算逐分鐘 \(H\)，再依主線的 \(u\pm\pi\) 與 L2 配對權重算 \(\overline H_i\)。預測 \(\widehat\rho_i=R_k\rho_{\mathrm{MSIS,q},i}\exp(G\overline H_i)\)。每圈 \(\tau_j\) 以整場有效錨點的對數密度誤差平方和評分。
- 全部 \(\tau_j\) 從 4.65 小時開始。候選為 0–10 小時、間隔 0.5 小時，再加入主線的 4.65 小時，共 22 值。依圈號逐一選改善誤差的候選，整輪沒有改變就停止，最多 20 輪。這是座標下降的局部試驗，沒有相鄰圈平順限制。

固定全部 \(\tau_j=4.65\) 小時時，重算的相位響應與主線最大差 \(1.52\times10^{-11}\,\mathrm{nT}\)，214,907 列固定 M1 密度與主線逐列完全相同；合併對數密度 RMSE 重現為 0.206517515。這驗證本試驗除 \(\tau\) 外使用相同的 M1 基線。

## 結果

| 項目 | 結果 |
| --- | ---: |
| M1 共用 4.65 小時，合併對數密度 RMSE | 0.206517515 |
| 逐圈自由 \(\tau_j\)，合併對數密度 RMSE | 0.122489449 |
| 資料內 RMSE 相對下降 | 40.7% |
| \(\tau_j=0\) 小時 | 263 段（11.3%） |
| \(\tau_j=10\) 小時 | 1,591 段（68.4%） |
| 落在任一搜尋邊界 | 1,854／2,325 段（79.7%） |
| 20 輪內停止 | 25／25 場 |

`S20241109T1237` 在第 11 輪停止；其餘場次不超過 10 輪。大部分圈落在搜尋邊界，故資料內誤差下降不能解讀為已量到可靠的逐圈物理時間常數。使用平靜 MSIS 後，邊界問題仍存在，表示完整 MSIS 的 `ap` 響應不是這個問題的唯一原因。\(R_k\) 和 \(G\) 已使用同一批 L2 校準，本試驗又以事件期間 L2 選 2,325 個 \(\tau_j\)，不能作獨立預報或與主線的留出事件結果直接比較。

## 輸出與驗證

- SQLite：`phases/phase3-trial/data/sqlite/swarm_a_m1_variable_orbit_tau_phase2_v2.sqlite`。`m1_variable_tau_orbit` 存每段 \(\tau_j\)；`m1_variable_tau_event` 存逐場誤差；`m1_variable_tau_sweep` 存每輪變化；`m1_variable_tau_minute` 存 L2、平靜 MSIS、固定 M1 及逐圈試驗曲線。v1 僅作重跑前紀錄，因掃描輪數不足且 `changed_orbit_count` 型別錯誤而不採用。
- 逐場圖：`phases/phase3-trial/figures/m1_variable_tau_25_events.png`；分布圖：`phases/phase3-trial/figures/m1_variable_tau_distribution.png`。
- 重算入口：`phases/phase3-trial/code/prep_m1_variable_orbit_tau.py`。SQLite `integrity_check=ok`；187 筆逐輪改變圈數均為整數；試驗測試 7 項通過。
