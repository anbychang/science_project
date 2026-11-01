# Phase 1 mean anomaly 與 Phase 5 density-to-decay 接法

## 決定

狀態：[done: read-only research]。

`mean_anomaly_rad` 可以用來定義軌道相位、共同的一圈邊界與配對權重，但不能單獨把密度轉成 semi-major-axis decay。本文件核對的 `phase5_orbit_prediction.rho_pooled_gpr_kg_m3` 是**歷史 Trial9** 的條件性輸出，需要上一圈 L2；它是放在 UTC 分鐘中心鍵上的 centered one-orbit density mean，不是逐分鐘點密度，也不是已積分的 drag 或 decay。[Phase 5 無同場 L2 終版](../../../phase5/reports/phase_5_report.md)沒有選用這條 GPR 曲線。

候選轉換至少還需要：

- 與 Phase 5 相同 centered orbit window 的 mean semi-major axis；
- `B = C_D A_perp / m`，或從獨立資料校準的等效 density-to-decay scale；
- 明確的 total decay 或 storm-excess decay 定義；
- near-circular、姿態與 relative-velocity 等假設。

Phase 1、Phase 2/3 frozen checkpoint、Phase 4 與 Phase 5 均未修改。本研究只新增本文件。

## 唯讀資料範圍

```text
Phase 1 mean-element checkpoint
  phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite

Phase 1 current working copy used by frozen Phase 2 phase construction
  phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite

Phase 5 historical Trial9 output
  phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite
```

兩份 Phase 1 三年 SQLite 的 `swarm_a_mean_orbit_elements_v1` 均有 9,469,438 筆，key 與值相同。下列統計以 checkpoint 查核；Phase 2 程式實際讀 current working copy。

## Phase 1 mean anomaly 的實際欄位與用途

### 欄位來源與語意

`mean_anomaly_rad` 是 `swarm_a_mean_orbit_elements_v1` 的 nullable `REAL` 欄位，row key 是 `time_us`。表的完整 mean-element 欄位清單定義於 [`prep_04_mean_orbit.py:31`](../../../phase1/code/prep_04_mean_orbit.py#L31)，table 與 foreign key 定義於 [`prep_04_mean_orbit.py:93`](../../../phase1/code/prep_04_mean_orbit.py#L93)。

其計算不是由 elapsed time 或固定 period 推算。流程是 ITRF state 轉 GCRF，建立 osculating orbit，再用 Orekit Brouwer-Lyddane J2--J5、`M2=0` 轉成 mean orbit；最後由 mean `KeplerianOrbit.getMeanAnomaly()` 取值。[`calc_mean_orbit.py:38`](../../../phase1/code/calc_mean_orbit.py#L38) 是 conversion，[`calc_mean_orbit.py:105`](../../../phase1/code/calc_mean_orbit.py#L105) 是欄位 extraction。SQLite metadata 實查的 algorithm 是 `orekit_brouwer_lyddane_j2_to_j5_m2_0_v3`，input frame 是 GCRF，gravity field degree/order 是 `5,0`。

三年 checkpoint 實查：

```text
swarm_a_mean_orbit_elements_v1 (derived；欄位節錄)
[
  {
    time_us: 1688169602000000 (us),
    UTC: 2023-07-01 00:00:02,
    mean_semi_major_axis_m: 6.859120546e6 (m),
    mean_argument_of_perigee_rad: -7.748173541e-1 (rad),
    mean_anomaly_rad: 3.012903794e0 (rad),
    mean_keplerian_period_s: 5.653451019e3 (s),
    rejection_reason: NULL
  },
  ...
]
```

| 查核 | 結果 |
| --- | ---: |
| rows | 9,469,438 |
| non-null `mean_anomaly_rad` | 9,469,438 |
| non-null `rejection_reason` | 0 |
| UTC coverage | 2023-07-01 00:00:02 -- 2026-06-30 23:59:32 |
| 原始 epoch 間隔 | 通常 10 s |
| `mean_anomaly_rad` 範圍 | -3.141592614 -- 3.141592627 rad |

這是一個 mean-element phase coordinate。它不是 orbit-mean density、elapsed orbit count 或 decay rate。

### 現行 Phase 1 用法

現行 Phase 1 以

\[
u = \operatorname{unwrap}(\omega + M)
\]

定義 mean argument of latitude，其中 \(\omega\) 是 `mean_argument_of_perigee_rad`，\(M\) 是 `mean_anomaly_rad`。程式在同一 `chunk_id` 內 unwrap，遇到 gap 或非單調 phase 就切段；再以精確 3 圈與 5 圈視窗擬合 raw B-L 或 joint H2/H3 slope。[`prep_14_phase_harmonic_decay_candidates.py:136`](../../../phase1/code/prep_14_phase_harmonic_decay_candidates.py#L136) 讀欄位，[`prep_14_phase_harmonic_decay_candidates.py:152`](../../../phase1/code/prep_14_phase_harmonic_decay_candidates.py#L152) 建 phase series，[`phase_1_execution_plan.md:266`](../../../phase1/docs/plans/phase_1_execution_plan.md#L266) 記錄現行 v2 contract。

`swarm_a_phase_orbit_mean_v2` 也以相同 \(u\) 切完整圈，用 phase trapezoid weight 計算 mean semi-major axis 與 H2/H3。[`prep_10_phase_orbit_mean.py:128`](../../../phase1/code/prep_10_phase_orbit_mean.py#L128) 讀 source，[`prep_10_phase_orbit_mean.py:145`](../../../phase1/code/prep_10_phase_orbit_mean.py#L145) unwrap，[`prep_10_phase_orbit_mean.py:178`](../../../phase1/code/prep_10_phase_orbit_mean.py#L178) 接受完整圈。

### Phase 5 已經間接使用 mean anomaly

Frozen Phase 2 不是另造固定軌道週期。它直接讀 Phase 1 current working copy 的 10 s `mean_argument_of_perigee_rad` 與 `mean_anomaly_rad`，以 `u=(omega+M) mod 2pi` unwrap，再插值到整分鐘。[`prep_23_t0_phase_window.py:32`](../../../phase2/code/prep_23_t0_phase_window.py#L32) 固定來源路徑，[`prep_23_t0_phase_window.py:70`](../../../phase2/code/prep_23_t0_phase_window.py#L70) 定義 phase，[`prep_23_t0_phase_window.py:96`](../../../phase2/code/prep_23_t0_phase_window.py#L96) 與 [`prep_23_t0_phase_window.py:192`](../../../phase2/code/prep_23_t0_phase_window.py#L192) 執行 time/phase 插值。

因此 Phase 4 的 `u_rel_rad` 與 Phase 5 的每圈錨點已經繼承 Phase 1 mean anomaly。重新把 `mean_anomaly_rad` 當 GPR feature 或再乘進 density 沒有物理依據。

## Phase 5 GPR 修正密度的實際輸出

### 歷史 Trial9 table 與欄位

本文件核對的歷史衍生 SQLite 是 `phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite`。修正密度在 `phase5_orbit_prediction.rho_pooled_gpr_kg_m3`；完整欄位為：

```text
phase5_orbit_prediction (derived)
[
  {
    storm_id: TEXT,
    time_us: INTEGER,
    previous_time_us: INTEGER,
    fold_index: INTEGER,
    comparable_2115: INTEGER,
    rho_l2_phase_kg_m3: REAL,
    rho_trial4_phase_kg_m3: REAL,
    actual_log_residual: REAL,
    previous_log_residual: REAL,
    pooled_gpr_log_residual: REAL,
    pooled_gpr_log_std: REAL,
    rho_pooled_gpr_kg_m3: REAL,
    algorithm_version: TEXT
  },
  ...
]
```

Primary key 是 `{storm_id, time_us}`。`previous_time_us < time_us`，兩個時間鍵都 foreign-key 到 `phase5_orbit_anchor`。[`prep_phase5_gpr_sqlite.py:39`](../../../phase5/code/prep_phase5_gpr_sqlite.py#L39) 是實際 schema。

GPR 寫入值為

\[
\widehat{\rho}_{n}
= \rho_{D,n}\exp(\widehat e_n),
\]

其中 `rho_trial4_phase_kg_m3` 是 \(\rho_{D,n}\)，`pooled_gpr_log_residual` 是 \(\widehat e_n\)。實際 writer 見 [`prep_phase5_direct_gpr.py:101`](../../../phase5/code/prep_phase5_direct_gpr.py#L101)。

一筆可查回的 row：

```text
phase5_orbit_prediction JOIN phase5_orbit_anchor (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691050200000000 (us),
    UTC: 2023-08-03 08:10:00,
    previous_time_us: 1691044560000000 (us),
    previous_UTC: 2023-08-03 06:36:00,
    u_rel_rad: -1.822310507e2 (rad),
    rho_l2_phase_kg_m3: 6.695663833e-13 (kg/m^3),
    rho_trial4_phase_kg_m3: 6.637486093e-13 (kg/m^3),
    pooled_gpr_log_residual: -1.096999750e-3,
    pooled_gpr_log_std: 1.413057742e-1,
    rho_pooled_gpr_kg_m3: 6.630208764e-13 (kg/m^3),
    fold_index: 4,
    comparable_2115: 0,
    algorithm_version: phase4_direct_trial4_pooled_orbit_gpr_v1
  }
]
```

### 時間與軌道粒度

Phase 5 先從 Phase 4 分鐘表挑 `phase_is_valid_80pct=1` 的列，再對每個 integer grid \(k\) 保留最接近 \(u_{rel}=2\pi k\) 的分鐘；容許距離是 `0.02*pi`。[`load_phase5_trial4_orbits.py:19`](../../../phase5/code/load_phase5_trial4_orbits.py#L19) 是選點程式。相鄰 pair 只接受 `current_grid = previous_grid + 1`，不跨缺圈；見 [`prep_trial9_pooled_orbit_gpr.py:37`](../../../phase5-trial9/code/prep_trial9_pooled_orbit_gpr.py#L37)。

每個 density 值本身不是該分鐘的 point sample。Phase 4 contract 明定 density 是以該分鐘為中心的 `u +/- pi` 相位平均。[`trial4_joint_fit_tau15.md:11`](../../../phase4/docs/lineage/trial4_joint_fit_tau15.md#L11) 記錄該契約；實作以 native paired sample count 加權，要求完整 phase window、paired coverage >= 80%，見 [`calc_h_tau.py:21`](../../../phase4/code/calc_h_tau.py#L21) 與 [`prep_quiet_msis.py:92`](../../../phase3/code/prep_quiet_msis.py#L92)。

所以一列的正確語意是：

```text
UTC minute center at u_rel ~= 2pi*k
  -> centered [u_rel-pi, u_rel+pi] one-orbit density mean
  -> one held-out next-orbit GPR correction at that center
```

SQLite 實查：

| table / quantity | 結果 |
| --- | ---: |
| `phase5_orbit_anchor` | 2,295 rows；25 storms |
| `phase5_orbit_prediction` | 2,265 rows；25 storms |
| primary comparable subset | 2,115 rows |
| 每場 prediction rows | 87--91 |
| `time_us - previous_time_us` | 5520--5700 s |
| prediction UTC envelope | 2023-08-03 08:10:00 -- 2026-04-22 06:26:00 |
| `rho_pooled_gpr_kg_m3` 範圍 | 5.549e-13 -- 5.929e-12 kg/m^3 |

UTC envelope 只包住 25 個離散 storm windows，不是連續 coverage。2,265 列是五折 held-out prediction；全部 25 場訓練的 `all_25.joblib` 只供後續推論，`predict_next_orbit()` 回傳 in-memory `rho_gpr_kg_m3`，沒有另一張已保存的 final-model prediction table。[`prep_phase5_direct_gpr.py:27`](../../../phase5/code/prep_phase5_direct_gpr.py#L27) 定義 final model，[`prep_phase5_direct_gpr.py:37`](../../../phase5/code/prep_phase5_direct_gpr.py#L37) 定義推論輸出。

### Repo 目前沒有 Phase 5 density-to-decay consumer

`rho_pooled_gpr_kg_m3` 的 Python 使用者只有 Phase 5 writer、overview plot 與測試；沒有程式把它讀進 semi-major-axis decay。現有 Phase 6 quiet closure 是另一條資料鏈：它讀 `phase6_quiet_orbit_pair_v1.rho_l2_orbitmean_kg_m3`，再計算 `sum(rho*sqrt(mu*a)*dt)` 的 empirical closure kernel，不讀 Phase 5。[`calc_phase6_quiet_closure.py:62`](../../code/calc_phase6_quiet_closure.py#L62) 是 input query，[`calc_phase6_quiet_closure.py:101`](../../code/calc_phase6_quiet_closure.py#L101) 是 kernel。不可把該 closure 寫成 Phase 5 已完成的物理轉換。

## density 轉 semi-major-axis decay

### mean anomaly 的角色

`mean_anomaly_rad` 應只負責以下工作：

1. 以 `u=unwrap(omega+M)` 建立連續 phase。
2. 以 Phase 5 anchor 為中心定義 `[u-pi,u+pi]` 的共同 orbit window。
3. 在同一 window 內取得 Phase 1 mean semi-major axis，並保存 density 與 orbit observable 的對齊關係。
4. 若改用沿軌密度，再以 phase/time 權重做一圈積分。

它不提供 drag coefficient、迎風面積、質量或 relative velocity。Phase 5 schema 也沒有這些欄位，因此 `mean_anomaly_rad + rho_pooled_gpr_kg_m3` 仍不足以得到絕對 decay。

### 可用的近圓軌道候選式

定義

\[
B = \frac{C_D A_{\perp}}{m},
\]

其中 \(C_D\) 是 drag coefficient，\(A_{\perp}\) 是迎風投影面積，\(m\) 是衛星質量。若採用

- near-circular orbit；
- \(v_{rel}\simeq v=\sqrt{\mu/a}\)；
- 一圈內 \(a\)、\(B\) 近似固定；
- Phase 5 centered density mean 可代表該圈 drag-weighted density；

則

\[
\dot a_n \simeq -B\,\bar\rho_n\sqrt{\mu a_n},
\]

\[
\Delta a_n \simeq -2\pi B\,a_n^2\bar\rho_n.
\]

此處 \(\bar\rho_n\) 才可代入 `rho_pooled_gpr_kg_m3`。`time_us` 是 centered window 標籤；不可未說明就把它當成左端點，對 `[time_us_n,time_us_{n+1}]` 作 left-rule integration。

若要 storm-excess decay，而非 total drag decay，還要另取同 window 的 quiet density \(\bar\rho_{q,n}\)：

\[
\Delta\dot a_{storm,n}
\simeq -B(\bar\rho_n-\bar\rho_{q,n})\sqrt{\mu a_n}.
\]

Phase 5 table 沒有 quiet-density 欄位，不能只靠該庫計算 storm excess。

### 更完整的物理路徑

若不接受上述近圓近似，應從

\[
\mathbf a_D=-\frac12\rho B\lvert\mathbf v_{rel}\rvert\mathbf v_{rel},
\qquad
\dot a=\frac{2a^2}{\mu}\mathbf v\cdot\mathbf a_D
\]

沿一圈積分。這需要沿軌 density、GCRF state、Earth-relative atmosphere velocity、姿態與 \(B\)。Phase 5 只有 centered one-orbit mean，mean anomaly 無法重建已平均掉的 latitude、local-time 或 velocity weighting。

## 對齊與驗證限制

- 不可用 `time_us` exact join Phase 1 與 Phase 5。Phase 1 epoch 通常在 `...:02`、`...:12`；Phase 5 是整分鐘。上例 `1691050200000000` 在 Phase 1 由 08:09:52 與 08:10:02 兩筆 bracket，exact key match 是 0。應沿用 frozen Phase 2 的 phase interpolation，或以明確 window overlap 配對。
- 不可直接拿 `swarm_a_phase_orbit_mean_v2.time_us` 當 Phase 5 key。前者是固定 absolute-`u` orbit 的右端點；後者是 event-relative `u_rel=2pi*k` centered window。兩者都是一圈量，但 boundary 不同。
- Phase 5 density mean 使用 native sample-count weighting；Phase 1 complete-orbit mean 使用 delta-`u` trapezoid weighting。Phase 6 必須先選定一個共同 window 與 weighting，不能把兩者因名稱含 `orbit` 就視為同一 estimator。
- Phase 5 GPR 需要上一圈已觀測 L2，且 Phase 4 event parameters 用完整事件 L2 擬合。轉出的 decay 仍是 retrospective descriptive estimate，不是端到端 forecast。
- Phase 1 3/5-orbit slope 仍是未校準 candidate。可用來做 closure、估等效 scale 或比較方向與量級，不能當成無誤差 drag truth。

## 建議的最小 Phase 6 接法

```text
Phase 5 phase5_orbit_prediction
  {storm_id, time_us, rho_pooled_gpr_kg_m3, pooled_gpr_log_std}
  + phase5_orbit_anchor
  {storm_id, time_us, u_rel_rad}
  + Phase 1 mean elements
  {time_us, mean_semi_major_axis_m, mean_argument_of_perigee_rad, mean_anomaly_rad}
  -> interpolate Phase 1 u and a to the Phase 5 centered window
  -> calculate same-window a_n
  -> apply physical B or independently calibrated effective scale
  -> write a new Phase 6 SQLite table
  {storm_id, time_us, density_kg_m3, semi_major_axis_m,
    decay_rate_m_s or orbit_delta_a_m, method, algorithm_version}
```

第一版若沒有可信的 `C_D A_perp/m`，只應做 dimensionally explicit 的 scale sensitivity 或 independent quiet-window calibration。不要把 `mean_anomaly_rad` 當成缺失 ballistic coefficient 的替代品，也不要回寫 Phase 1 或 Phase 5。

## SQLite 查核指令

Phase 1 field、coverage 與值域：

```sql
SELECT count(*) AS rows,
       count(mean_anomaly_rad) AS nonnull_mean_anomaly,
       sum(rejection_reason IS NOT NULL) AS rejected,
       min(time_us), max(time_us),
       min(mean_anomaly_rad), max(mean_anomaly_rad)
FROM swarm_a_mean_orbit_elements_v1;
```

Phase 5 output 與 orbit-pair 間隔：

```sql
SELECT count(*) AS rows,
       count(DISTINCT storm_id) AS storms,
       min(time_us), max(time_us),
       min(rho_pooled_gpr_kg_m3), max(rho_pooled_gpr_kg_m3),
       sum(comparable_2115)
FROM phase5_orbit_prediction;

SELECT (time_us - previous_time_us) / 1000000 AS pair_gap_s,
       count(*) AS rows
FROM phase5_orbit_prediction
GROUP BY pair_gap_s
ORDER BY pair_gap_s;
```
