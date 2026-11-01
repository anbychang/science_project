# Phase 6 磁暴前三個月背景斜率資料血緣

狀態：[working]。本步比較每場磁暴前 90 天的全部逐圈半長軸斜率，以及同期間只使用已通過平靜日規則的斜率。它回答背景斜率是否可視為固定；不把長期趨勢解釋成純 drag。輸出是本機 `phases/phase6/data/sqlite/swarm_a_phase6_prestorm_baseline_v1.sqlite`。

#### [P6.3] Phase 1 逐圈半長軸 + 平靜日 -> 每場磁暴前背景斜率 [done]

```text
calc_phase6_prestorm_baseline.py -> run()

對 Phase 4 固定的 25 個 `t0_time_us`，讀取同一 pre-t0 `chunk_id` 內最近 90 天的 `swarm_a_phase_orbit_mean_v2`。
全部逐圈點作一次 OLS；結束日在 `phase6_quiet_day_v1` 的逐圈點另作 quiet-only OLS。
不跨 chunk，也不讀 t0 之後的資料。來源不足 90 天時照實保存 coverage，不補其他 chunk。
```

```text
trial4_25storm_overview (derived；Phase 4；欄位節錄)
[
  {
    storm_id: S20231021T0728,
    t0_time_us: 1697873280000000 (us),
  },
  ...,
]

swarm_a_phase_orbit_mean_v2 (derived；Phase 1；欄位節錄)
[
  {
    time_us: 1694308752000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.857e6 (m),
    chunk_id: 11,
  },
  ...,
]

phase6_quiet_day_v1 (derived；Phase 6；欄位節錄)
[
  {
    day_start_time_us: 1694304000000000 (us),
    ap_max: 5.000e0,
    sme_max_nt: 2.364e2 (nT),
  },
  ...,
]
```

```text
phase6_prestorm_baseline_v1 (derived；欄位節錄)
[
  {
    storm_id: S20231021T0728,
    t0_time_us: 1697873280000000 (us),
    lookback_start_time_us: 1690097280000000 (us),
    chunk_id: 11,
    all_orbit_count: 1375,
    all_coverage_days: 9.005e1 (day),
    all_rate_m_day: -3.802e1 (m/day),
    all_rate_1sigma_m_day: 1.702e-1 (m/day),
    quiet_day_count: 7,
    quiet_orbit_count: 106,
    quiet_rate_m_day: -4.188e1 (m/day),
    quiet_rate_1sigma_m_day: 6.101e-1 (m/day),
    status: evaluated,
  },
  ...,
]
```

`all_coverage_days` 是第一圈起點至最後一圈終點的跨度。`quiet_coverage_days` 是首末 quiet-day 逐圈點的時間跨度，不代表中間每一天都平靜。OLS sigma 未處理 orbit-to-orbit autocorrelation；背景斜率仍是 descriptive candidate。
