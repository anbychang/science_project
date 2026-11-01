# Phase 6：L2 density 推導半長軸下降

## 決定與結果

狀態：[retained]。這是先前 25 場、2024 quiet-window scale 的候選結果。現行方法已改為不選窗口的三年 L2 全域積分與單一比例擬合；本報告只保留歷史比較。

固定使用 2024 三個 quiet windows 擬合的

\[
\widehat\beta_{eff}=0.0097928077\ \mathrm{m^2/kg}.
\]

對每個 L2 anchor (k)，Phase 1 以

\[
u=\operatorname{unwrap}(\omega+M)
\]

重建相同的 centered window ([u_k-\pi,u_k+\pi])，再計算該圈平均半長軸 \(\bar a_k\)。候選下降率與單圈變化是

\[
\widehat{\dot a}_k
=-\widehat\beta_{eff}\rho_{L2,k}\sqrt{\mu\bar a_k},
\]

\[
\widehat{\Delta a}_k
=\widehat{\dot a}_k T_k,
\]

其中 (T_k) 是同一 phase window 的實際 UTC 時長。

## 資料品質

| 檢查 | 結果 |
| --- | ---: |
| storms | 25 |
| L2 anchors | 2,295 |
| accepted centered windows | 2,295 |
| rejected anchors | 0 |
| 每圈 Phase 1 source samples | 558--566 |
| phase coverage | 完整 (2\pi) |
| maximum POD gap | 10 s |
| orbit period | 5,578.92--5,660.23 s |

Phase 5 本身在四場事件有缺少 integer phase grid，因此 cumulative path 切成 2 或 3 個 block；計算沒有跨過缺圈。

## 逐圈與逐事件量級

逐圈 L2 推導的下降率範圍為：

\[
-273.71\ \mathrm{m/day}
\leq
\widehat{\dot a}
\leq
-24.70\ \mathrm{m/day}.
\]

逐圈下降量範圍為 `-17.70` 至 `-1.62 m/orbit`。

在各事件實際有覆蓋的 blocks 上，L2 推導值與 Phase 1 boundary change 的 25 場比較為：

| Metric | Value |
| --- | ---: |
| MAE | 33.46 m |
| RMSE | 38.42 m |
| MAPE | 8.04% |
| mean prediction error | -26.20 m |

負的 mean error 表示 L2 路徑平均預測得比 Phase 1 boundary change 更往下降。25 場預測合計是 `-11,753.39 m`，Phase 1 covered-block change 合計是 `-11,098.41 m`；合計只用來核對符號與量級，不是統計獨立樣本。

## 使用界線

- 這是 total decay，不是「扣掉平靜背景後」的 storm-excess decay。
- `beta_eff` 是目前資料產品與 estimator 下的有效比例，不是實測 (C_DA/m)。
- L2 density 與 Phase 1 semi-major axis 都含 POD 資訊，兩者不是完全獨立。
- 結果是 retrospective closure。Phase 5 GPR／Phase 4 model density 尚未接入本計算。
- 事件誤差包含 density scale、姿態、relative wind、mean-element residual 與未標定 non-drag force。

正式 SQLite 是 `phases/phase6/data/sqlite/swarm_a_phase6_l2_density_decay_v1.sqlite`。來源 key、欄位與 window gate 見[資料血緣](../docs/lineage/phase6_l2_density_decay.md)。
