# P6.2：Phase 4 D-model density -> 半長軸下降

## 決定

Phase 4 D-model 是本專案建立的 density model。P6.2 固定使用 P6.1 的
`B_eff=0.0092292068 m²/kg`，把 Phase 4 density 轉成半長軸下降，不重新擬合
Phase 4，也不重新擬合 `B_eff`。

```text
我們的 Phase 4 D-model density
  + P6.1 fixed B_eff
  + P6.1 POD minute semi-major axis
  -> Phase 4 predicted semi-major-axis change
  -> compare with POD observed change
```

## 計算

相鄰分鐘使用 60 秒梯形積分：

\[
K_n=\sum_k
\frac{\rho_{k-1}\sqrt{\mu a_{k-1}}+\rho_k\sqrt{\mu a_k}}{2}\times60.
\]

Phase 4 預測下降為：

\[
\Delta a_{P4,n}=-B_{eff}K_n.
\]

Phase 4 只有 25 場磁暴的 `-2` 至 `+4` 天窗口。每場磁暴各自歸零、各自估計，下一場不延續前一場的積分。事件內缺分鐘或 `chunk_id` 改變時切成新 block；不補值、不跨缺口積分。單場結果是該場所有有資料 blocks 的 endpoint change 加總。

## 比較基準

同一批分鐘也使用 Phase 4 SQLite 保存的 `rho_l2_phase_kg_m3` 計算 L2 phase-density 下降。這條線只用來判斷 D-model 與其 L2 參考相差多少；P6.2 的模型結果仍是 `rho_trial4_joint_phase_kg_m3`。

## 主張界線

- Phase 4 D-model 是我們的模型，不是官方 density model。
- Phase 4 的 `R_k`、`tau_k` 與共同 `G` 曾用這 25 場 L2 density 回溯擬合。
- P6.2 檢查 density-to-decay 的閉合，不是未見事件 forecast。
- P6.1 `B_eff` 來自 instantaneous L2 density；Phase 4 使用 phase-averaged density。P6.2 固定比例，並用同表的 L2 phase density 作 representation sensitivity。
