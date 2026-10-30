# M2：Phase 2 相位的逐圈時間常數試驗

## 決定與結果

狀態：[trial]。沿用 Phase 2 的事件相對相位 `u_rel_rad`；每跨過 $2\pi$ 建一個不重疊軌道段。只處理 25 場事件窗口，不使用 Phase 1 的三年軌道表作圈界。先前的 Phase 1 圈界試算已丟棄。Phase 3 主線及正式 $R_k$ 不變。

本輪**擬合一條共用活動規則**，由規則給每圈一個 $\tau_j$；沒有讓 2,325 圈各自自由擬合參數。

| 項目 | 結果 |
| --- | ---: |
| 軌道段 | 2,325；每場 93 段 |
| 最佳規則的逐圈 $\tau_j$ | 2.408–5.000 h |
| 固定 $\tau=3.5$ h 的合併對數密度 RMSE | 0.105434 |
| 逐圈規則的最低 RMSE | 0.105287 |
| 相對 RMSE 下降 | 0.14% |
| 逐場 RMSE 下降／上升 | 15／10 場 |
| 49 組規則中，RMSE 在最低值 1%／5% 內 | 16／45 組 |

改善很小，且大多數格點接近最低誤差。目前無法明確辨識活動量與 $\tau_j$ 的關係。

## 規則與計算順序

第 $j$ 圈是 $u\in[2\pi j,2\pi(j+1))$。只用上一圈已觀測的 SME 平均 $S_{j-1}$（nT）決定本圈時間常數：

$$
A_{j-1}=\max(S_{j-1}-65,0),\qquad
w_j=\frac{A_{j-1}}{A_{j-1}+435},\qquad
\tau_j=\tau_{\mathrm{quiet}}+(\tau_{\mathrm{active}}-\tau_{\mathrm{quiet}})w_j.
$$

$w_j$ 無單位。65 nT 是沿用的 SME 參考值；435 nT 是本次試驗假設的活動尺度，使上一圈平均 SME 為 500 nT 時 $w_j=0.5$，不是物理常數。事件窗口第一圈沒有窗口內的上一圈，設 $S_{j-1}=65$ nT。

每分鐘以當圈 $\tau_j$ 遞迴計算 $H$，圈界只切換 $\tau_j$，不把 $H$ 歸零：

$$
H_t=e^{-1/(60\tau_j)}H_{t-1}
+\left(1-e^{-1/(60\tau_j)}\right)(\mathrm{SME}_t-65).
$$

$\tau_j$ 用小時，時間步是 1 分鐘，$H$ 與 SME 用 nT。事件開始前一分鐘的 $H$ 取自全三年連續的固定 $\tau=3.5$ h 基線。算完一分鐘 $H$ 後，才依原有 $u\pm\pi$ 中心相位窗口平均。錨點的 `tau_at_anchor_hours` 是其所在圈的值；平均後的 $H$ 可能包含相鄰圈。

M2 密度為 $\widehat\rho_2=R_k\rho_{\mathrm{M0,aligned}}\exp(GH)$。逐場 $R_k$ 固定為上次交替試算終值，完整 MSIS 繼續使用實際 `ap` 歷史。試 $\tau_{\mathrm{quiet}},\tau_{\mathrm{active}}\in\{0.5,1,2,3.5,5,7,10\}$ 小時，共 49 組；每組用 25 場 L2 重新估一個共同 $G$，選合併 RMSE 最低者。

最低格點是 $\tau_{\mathrm{quiet}}=5$ h、$\tau_{\mathrm{active}}=2$ h，$G=2.235241\times10^{-4}\,\mathrm{nT}^{-1}$。此結果描述完整 MSIS 的**剩餘誤差修正**，不能解讀成熱層在強磁暴時的真實反應時間較短。2024-05-11 附近七圈，上一圈 SME 平均約 1,362–2,087 nT，對應 $\tau_j$ 約 2.53–2.75 h。

## 驗證與界線

當規則兩端都設 3.5 h，新程式的相位響應與原固定時間常數結果最大相差 $1.52\times10^{-11}$ nT，合併 RMSE 也重現 0.105434。輸出有 49 組格點、2,325 個逐圈值、214,907 個有效相位錨點與 25 場摘要，SQLite `integrity_check=ok`。

這仍是**樣本內擬合**：規則與 $G$ 用這 25 場 L2 選出，固定的 $R_k$ 先前也用了事件期間 L2。重疊事件依各自 Phase 2 相位與窗口起點狀態分別試算，不能拼成全三年唯一的變動-$\tau$ 曲線。0.14% 的改善不足以支持改動主線或宣稱預報效果。

完整結果是本機 `phases/phase3-trial/data/sqlite/swarm_a_m2_orbit_tau_phase2_v1.sqlite`：`m2_phase2_tau_rule_grid` 存 49 組規則，`m2_phase2_tau_orbit` 存每圈 SME 與 $\tau_j$，`m2_phase2_tau_minute` 存 M2 密度與相位響應，`m2_phase2_tau_event` 存逐場 RMSE。重算入口為 `phases/phase3-trial/code/prep_m2_orbit_tau_phase2.py`。
