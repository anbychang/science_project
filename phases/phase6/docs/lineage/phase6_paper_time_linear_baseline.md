# Phase 6 論文時間線性背景資料血緣

狀態：[working]。本步不再從本機平靜日估背景。輸出在本機 `phases/phase6/data/sqlite/swarm_a_phase6_paper_time_linear_baseline_v3.sqlite`；Phase 1 與 Phase 4 只讀，既有平靜背景輸出保留但不作目前判定輸入。

#### [P6.8] 論文時間線性 rate + 完整六天逐圈半長軸 -> 額外下降量 [done]

```text
calc_phase6_paper_time_linear_baseline.py -> run()

2024-05-04 與 2026-01-31 使用 Tulasi Ram et al. (2026) 的 quiet-time rate 錨點。
每日 rate 在兩錨點之間連續線性內插；2023、錨點前的 2024 與錨點後的 2026 事件沿同一直線外推。

rate(t) = -19.91 - 0.093438 * elapsed days since 2024-05-04 12:00 UTC
paper expected change = rate(t0) * event duration
extra loss = paper expected change - observed event change

完整事件窗為 [t0 - 2 day, t0 + 4 day)。前後端點以 4/6/8 圈擬合；6 圈是 reference。
```

```text
swarm_a_phase_orbit_mean_v2 + trial4_25storm_overview + paper anchors (欄位節錄)
[
  {
    time_us: 1715225722000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.845e6 (m),
    chunk_id: 11,
    algorithm_version: phase_weighted_orbit_h2_h3_local_ols_v1
  },
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us)
  },
  {
    anchor_time_us: 1714824000000000 (us),
    rate_m_day: -1.991e1 (m/day),
    source_date: 2024-05-04
  },
  ...,
]
```

```text
phase6_paper_time_anchor_v3 + phase6_paper_time_linear_excess_decay_v3 (derived；欄位節錄)
[
  {
    anchor_time_us: 1769860800000000 (us),
    rate_m_day: -7.943e1 (m/day),
    source_date: 2026-01-31,
    algorithm_version: phase6_paper_time_linear_baseline_v3
  },
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    event_rate_m_day: 5.623e0 (m/day),
    source_role: backward_extrapolation,
    observed_delta_a_6_m: -1.639e2 (m),
    paper_background_delta_a_m: 3.352e1 (m),
    excess_decay_6_m: 1.974e2 (m),
    increased_decay: 1,
    status: evaluated,
    algorithm_version: phase6_paper_time_linear_baseline_v3
  },
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    event_rate_m_day: -2.053e1 (m/day),
    source_role: linear_interpolation,
    first_orbit_time_us: 1715225722000000 (us),
    last_orbit_time_us: 1715733692000000 (us),
    duration_days: 5.879e0 (day),
    observed_delta_a_6_m: -4.230e2 (m),
    paper_background_delta_a_m: -1.207e2 (m),
    excess_decay_6_m: 3.024e2 (m),
    increased_decay: 1,
    status: evaluated,
    algorithm_version: phase6_paper_time_linear_baseline_v3
  },
  ...,
]
```

`time_us` 是 UTC orbit end、錨點日中央或事件 `t0`。25 場全部可評估。2023 的 4 場都是長距離向前外推；其中 `S20230805T0546` 得到正的背景 rate，表示公式預期半長軸上升，不能作物理 drag 解釋。時間公式是刻意簡化的 empirical proxy，兩個錨點同時受高度與 local time 差異影響；不可寫成已校準的物理背景。
