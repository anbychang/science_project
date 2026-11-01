# Phase 6 論文 rate + NRLMSIS scale 跨時間檢查資料血緣

狀態：[done]。本步只用 2024-05-04 決定一次 conversion scale，再固定套用至 2026-01-31。輸出在本機 `phases/phase6/data/sqlite/swarm_a_phase6_paper_msis_scale_check_v1.sqlite`；Phase 1、DNSAPOD raw ZIP 與既有 Phase 6 輸出不修改。

#### [P6.9] 2024 paper rate + quiet NRLMSIS -> fixed scale -> 2026 rate check [done]

```text
calc_phase6_paper_msis_scale_check.py -> run()

兩天都沿當日 DNSAPOD 原生 30-second 軌道位置計算 NRLMSIS 2.0。
保留 Phase 1 的 prior-day F10.7 與 centered F10.7A；七欄 Ap 全固定為 4。
每日 mean semi-major axis 讀 Phase 1 的 15 圈 phase-orbit mean。

conversion scale = published 2024 rate / (mean quiet density * sqrt(mu * mean a))
predicted 2026 rate = fixed scale * 2026 density-orbit factor
```

```text
DNSAPOD raw ZIP + space_weather + swarm_a_phase_orbit_mean_v2 + paper rates (欄位節錄)
[
  {
    time_us: 1714780800000000 (us),
    latitude_deg: 6.369e1 (deg),
    longitude_deg: 1.220e2 (deg),
    altitude_m: 4.806e5 (m),
    validity_flag: 0,
    source_file: SW_OPER_DNSAPOD_2__20240504T000000_20240504T235930_0301.ZIP
  },
  {
    time_us: 1714780800000000 (us),
    f107_sfu: 1.560e2 (sfu),
    f107a_sfu: 1.756e2 (sfu)
  },
  {
    time_us: 1714785442000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.846e6 (m),
    chunk_id: 11,
    algorithm_version: phase_weighted_orbit_h2_h3_local_ols_v1
  },
  ...,
]
```

```text
phase6_paper_msis_daily_anchor_v1 + phase6_paper_msis_scale_check_v1 (derived；欄位節錄)
[
  {
    day_utc: 2024-05-04,
    day_start_time_us: 1714780800000000 (us),
    density_sample_count: 2880,
    orbit_count: 15,
    mean_altitude_m: 4.829e5 (m),
    mean_semi_major_axis_m: 6.846e6 (m),
    mean_quiet_density_kg_m3: 1.262e-12 (kg/m^3),
    published_rate_m_day: 1.991e1 (m/day),
    algorithm_version: phase6_paper_msis_scale_check_v1
  },
  {
    day_utc: 2026-01-31,
    day_start_time_us: 1769817600000000 (us),
    density_sample_count: 2880,
    orbit_count: 15,
    mean_altitude_m: 4.354e5 (m),
    mean_quiet_density_kg_m3: 1.479e-12 (kg/m^3),
    published_rate_m_day: 7.943e1 (m/day),
    algorithm_version: phase6_paper_msis_scale_check_v1
  },
  {
    calibration_day_utc: 2024-05-04,
    validation_day_utc: 2026-01-31,
    conversion_scale_m2_kg: 3.495e-3 (m^2/kg),
    predicted_validation_rate_m_day: 2.325e1 (m/day),
    signed_error_m_day: -5.618e1 (m/day),
    relative_error_percent: -7.073e1 (%),
    algorithm_version: phase6_paper_msis_scale_check_v1
  }
]
```

`day_start_time_us` 是 UTC 日起點；DNSAPOD `time_us` 是原生 30-second 樣本時刻，Phase 1 `time_us` 是 orbit end。2026 未重新校準。結果只檢查「NRLMSIS quiet density ratio + 固定 2024 scale」能否重現另一個論文 daily rate；conversion scale 是 model-specific empirical scale，不是已校準的 physical ballistic coefficient。
