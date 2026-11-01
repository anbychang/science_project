# P6.3：Phase 5 V2 Ridge 密度推回半長軸下降

## 決定

P6.3 與 P6.2 分開。P6.3 固定使用 P6.1 的 `B_eff=0.0092292068 m²/kg`，把 Phase 5 V2 的 `rho_ridge_phase_kg_m3` 轉成每場磁暴的半長軸下降，再與 POD 實際下降比較。

P6.3 不重新擬合 `B_eff`，也不在本步與 M0 判定勝負。P6.4 才統整 P6.2 與 P6.3。

```text
Phase 5 V2 Ridge density
  + P6.1 fixed B_eff
  + P6.1 POD minute semi-major axis
  -> Ridge predicted semi-major-axis change
  -> event error against POD observed change
```

## 計算

相鄰分鐘使用 60 秒梯形積分：

\[
K_{Ridge,n}=\sum_k
\frac{\rho_{k-1}\sqrt{\mu a_{k-1}}+\rho_k\sqrt{\mu a_k}}{2}\times60.
\]

Ridge 預測下降為：

\[
\Delta a_{Ridge,n}=-B_{eff}K_{Ridge,n}.
\]

每場磁暴的 `t0-2 days` 至 `t0+4 days` 窗口各自歸零。事件內缺分鐘或 `chunk_id` 改變時切新 block；不補值、不跨缺口積分。

## 誤差

每場定義：

\[
e_k=\Delta a_{Ridge,k}-\Delta a_{POD,k}.
\]

- `e_k > 0`：Ridge 預測下降絕對值較小，屬於少估。
- `e_k < 0`：Ridge 預測下降絕對值較大，屬於多估。

25 場保存 signed error、absolute error、absolute percentage error，並計算 MAE、RMSE、mean error 與 MAPE。

## 主張界線

- 使用 Phase 5 V2 每場留出的 Ridge `R_k` 密度，不使用全 25 場重新擬合後對同場的 fitted prediction。
- Ridge 的三個特徵曾用同一批 25 場的算分結果選出，因此 P6.3 仍是探索性回溯檢查，不是獨立外測。
- P6.1 使用逐分鐘 L2 density；Phase 5 V2 Ridge 是逐分鐘保存的 orbit-phase average。兩者時間平滑方式不同。
- P6.3 使用 POD 半長軸計算積分核，不是脫離 POD 的自由軌道 propagation。
