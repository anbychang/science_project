# P6.2：Phase 3 M0 的半長軸下降誤差

## 決定

P6.2 固定使用 P6.1 的 `B_eff=0.0092292068 m²/kg`，把 Phase 3 M0 轉成半長軸下降，再與 POD 實際下降比較。M0 就是 NRLMSIS 2.0 full density，欄位為 `rho_msis_full_phase_kg_m3`。

P6.2 不再使用 Phase 4 D-model，也不重新擬合 `B_eff`。

```text
Phase 3 M0 (NRLMSIS 2.0 full density)
  + P6.1 fixed B_eff
  + P6.1 POD minute semi-major axis
  -> M0 predicted semi-major-axis change
  -> event error against POD observed change
```

## 計算

相鄰分鐘使用 60 秒梯形積分：

\[
K_{M0,n}=\sum_k
\frac{\rho_{k-1}\sqrt{\mu a_{k-1}}+\rho_k\sqrt{\mu a_k}}{2}\times60.
\]

M0 預測下降為：

\[
\Delta a_{M0,n}=-B_{eff}K_{M0,n}.
\]

每場磁暴的 `t0-2 days` 至 `t0+4 days` 窗口各自歸零。事件內缺分鐘或 `chunk_id` 改變時切新 block；不補值、不跨缺口積分。

## 誤差

每場定義：

\[
e_k=\Delta a_{M0,k}-\Delta a_{POD,k}.
\]

- `e_k > 0`：M0 預測下降絕對值較小，屬於少估。
- `e_k < 0`：M0 預測下降絕對值較大，屬於多估。

25 場保存 signed error、absolute error、absolute percentage error，並計算 MAE、RMSE、mean error 與 MAPE。

## 主張界線

- M0 是 Phase 3 對 NRLMSIS 2.0 full density 的名稱，不是另一個新模型。
- M0 的底層 NRLMSIS 是外部經驗大氣模型，不是本專案建立的模型。
- 使用 `rho_msis_full_phase_kg_m3`，不是 quiet-MSIS，也不是 Phase 4 D-model。
- `B_eff` 由 L2/POD in-sample 擬合，因此這是固定轉換下的描述性誤差，不是完全獨立的軌道預報測試。
- P6.1 使用逐分鐘 L2 density；Phase 3 M0 是逐分鐘保存的 orbit-phase average。兩者時間平滑方式不同。
- M0 density 讀自既有 frozen snapshot；P6.2 不修改上游資料。
