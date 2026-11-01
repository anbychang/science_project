# Phase 6 最終報告：density 推回半長軸下降

## 決定

狀態：[done]。Phase 6 只有 P6.1 與 P6.2：

```text
P6.1
三年 L2 density + POD semi-major axis
  -> one fixed B_eff

P6.2
25 場 Phase 4 D-model density + fixed B_eff
  -> 每場磁暴的 predicted semi-major-axis change
  -> compare with POD observed change
```

Phase 6 不採用舊的 quiet-window scale、論文時間線性背景或 NRLMSIS scale 作正式結果。

## 研究問題

1. L2 density 的累積量能否用一個固定比例轉成 POD 半長軸變化？
2. 固定這個比例後，我們的 Phase 4 D-model density 能否推回 25 場磁暴各自的半長軸下降？

## P6.1：擬合固定 `B_eff`

### 資料

- UTC：2023-07-01 至 2026-06-30。
- DNSAPOD instantaneous density：原生約 30 秒。
- Phase 1 POD mean semi-major axis：原生 10 秒。
- complete paired minutes：1,575,708。
- continuous blocks：37。

每分鐘必須有 2 筆有效 density 與 6 筆可用 POD。缺分鐘或 `chunk_id` 改變時切新 block；不補值、不跨缺口積分。

### 方法

定義：

- `rho_k`：第 `k` 分鐘平均 L2 density，單位 `kg/m^3`。
- `a_k`：第 `k` 分鐘平均 POD mean semi-major axis，單位 `m`。
- `mu`：Earth gravitational parameter，單位 `m^3/s^2`。
- `Delta t = 60 s`。

相鄰分鐘使用梯形積分：

\[
K_n=\sum_{k=1}^{n}
\frac{\rho_{k-1}\sqrt{\mu a_{k-1}}+\rho_k\sqrt{\mu a_k}}{2}\Delta t.
\]

每個 continuous block 從零開始：

\[
\Delta a_{POD,n}=a_n-a_{block,start}.
\]

全三年只擬合一個通過原點的比例：

\[
B_{eff}=-\frac{\sum_n K_n\Delta a_{POD,n}}{\sum_n K_n^2}.
\]

### 結果

\[
\boxed{B_{eff}=0.0092292068\ \mathrm{m^2/kg}}
\]

這是 P6.2 唯一使用的 `B_eff`。不按年份、磁暴或 continuous block 重新調整。

## P6.2：Phase 4 D-model 推回磁暴下降

### 資料與方法

Phase 4 D-model 是本專案建立的 density model。P6.2 只使用 Phase 4 的 25 場磁暴窗口；每場範圍為 `t0-2 days` 至 `t0+4 days`。

每場磁暴各自歸零：

\[
\Delta a_{P4,n}=-B_{eff}K_{P4,n}.
\]

下一場磁暴不延續上一場的積分。事件內缺分鐘或 `chunk_id` 改變時切 block；單場結果加總該場有 density 支持的 block endpoint changes。

### 25 場逐場結果

| 磁暴 | POD 實際下降 (m) | Phase 4 預測下降 (m) | Phase 4 - POD (m) | 判斷 |
| --- | ---: | ---: | ---: | --- |
| 2023-08-05 | -231.40 | -176.06 | +55.34 | 少估 |
| 2023-10-21 | -309.23 | -286.24 | +23.00 | 少估 |
| 2023-11-05 | -378.29 | -381.78 | -3.49 | 多估 |
| 2023-12-01 | -239.50 | -277.39 | -37.89 | 多估 |
| 2024-03-03 | -369.14 | -312.94 | +56.20 | 少估 |
| 2024-03-24 | -389.99 | -414.84 | -24.85 | 多估 |
| 2024-04-19 | -426.17 | -472.76 | -46.59 | 多估 |
| 2024-05-11 | -457.64 | -439.70 | +17.94 | 少估 |
| 2024-06-28 | -412.91 | -348.68 | +64.23 | 少估 |
| 2024-08-04 | -411.14 | -400.16 | +10.98 | 少估 |
| 2024-08-12 | -683.56 | -637.11 | +46.45 | 少估 |
| 2024-09-17 | -368.99 | -391.34 | -22.35 | 多估 |
| 2024-10-10 | -578.22 | -568.01 | +10.21 | 少估 |
| 2024-11-09 | -694.82 | -671.04 | +23.78 | 少估 |
| 2025-01-01 | -636.33 | -625.87 | +10.46 | 少估 |
| 2025-04-16 | -519.79 | -523.75 | -3.96 | 多估 |
| 2025-05-17 | -293.00 | -293.39 | -0.38 | 多估 |
| 2025-06-01 | -405.45 | -302.51 | +102.94 | 少估 |
| 2025-06-13 | -304.20 | -260.14 | +44.06 | 少估 |
| 2025-09-30 | -641.43 | -671.44 | -30.01 | 多估 |
| 2025-11-12 | -642.34 | -633.28 | +9.06 | 少估 |
| 2026-01-20 | -646.56 | -615.85 | +30.72 | 少估 |
| 2026-03-21 | -399.10 | -416.31 | -17.21 | 多估 |
| 2026-04-02 | -539.22 | -566.06 | -26.84 | 多估 |
| 2026-04-18 | -330.31 | -323.49 | +6.82 | 少估 |

正誤差代表 Phase 4 預測的下降絕對值較小；負誤差代表預測下降較多。

### 描述性統計

| 項目 | 結果 |
| --- | ---: |
| 少估 | 15 場 |
| 多估 | 10 場 |
| endpoint MAE | 29.03 m |
| endpoint RMSE | 37.17 m |
| 最接近 | 2025-05-17，差 0.38 m |
| 最大差距 | 2025-06-01，少估 102.94 m |

Phase 4 有 214,907 個 minute rows，全部能精確連接 P6.1 的 POD minute data。4 場事件內有資料缺口，全體切成 31 個 continuous blocks。

## Phase 6 結論

Phase 6 建立了可重算的 density-to-decay 路徑：

```text
L2/POD -> fixed B_eff
Phase 4 density -> storm-by-storm predicted decay
```

一個固定 `B_eff` 已能把 Phase 4 density 轉成與 POD 磁暴窗口下降相同量級的結果。25 場中有 15 場少估、10 場多估；逐場 endpoint MAE 為 `29.03 m`。

結果支持把半長軸下降作為 density analysis 的 downstream closure quantity，但不建立獨立 forecast skill 或 geomagnetic-storm causality。

## 限制

- `B_eff` 由同一個三年區間的 L2 density 與 POD 半長軸 in-sample 擬合。
- DNSAPOD L2 與 semi-major axis 都依賴 POD 資訊，不是完全獨立資料源。
- `B_eff` 是有效比例，不是已校準的物理 `C_D A/m`。
- Phase 4 的 `R_k`、`tau_k` 與共同 `G` 曾用相同 25 場 L2 density 回溯擬合。
- P6.1 使用 instantaneous L2 density；Phase 4 輸出是 phase-averaged density。
- 未獨立處理 maneuver、姿態或其他 non-drag forces。
- POD minute semi-major axis 含短週期變化；逐場 endpoint difference 只作 descriptive closure。

## 正式輸出

| SQLite | 內容 |
| --- | --- |
| `swarm_a_phase6_1_l2_minute_pairs_v1.sqlite` | P6.1 的逐分鐘 L2/POD 配對 |
| `swarm_a_phase6_1_beff_v1.sqlite` | P6.1 的積分線與固定 `B_eff` |
| `swarm_a_phase6_2_phase4_decay_v1.sqlite` | P6.2 的逐分鐘積分與 25 場結果 |

詳細資料契約見 [P6.1 lineage](../docs/lineage/phase6_1_beff.md)與 [P6.2 lineage](../docs/lineage/phase6_2_phase4_decay.md)。
