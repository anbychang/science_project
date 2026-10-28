# 軌道分析資料血緣

```text
current P1.5.1 checkpoints:
  research_workspace/phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite
  research_workspace/phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite
```

兩個 current checkpoint 都含 P1.1–P1.4 與完成的 P1.5.1 mean elements。三年 working copy `research_workspace/phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite` 與 12 年 working copy `research_workspace/phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite` 均已寫入 P1.5.6 v2、P1.6 feature v2 和通過的 P1.7 audit v2。兩者均沒有再次呼叫 Orekit。三年 checkpoint 的 raw states 仍是全期資料；只有 mean-element table 限定三年。
舊 P1.5.2--P1.7 10-minute branch 與三年 v1 long-candidate branch 是 retained legacy，不是 current input。
範例浮點數只顯示三位小數的科學記號，運算須用 SQLite 原值。
12h backward rate 有大量極端值，maneuver、source、method anomaly 尚未校準。這些結果只能追溯與描述，不能宣稱已乾淨量到地磁暴造成的衰減。

### [P1.1] ESA archive -> local POD ZIP [done]

```text
down_swarm_pod.py -> download_swarm_a_pod()

ESA 清單 -> ZIP 檔名結束日 -> 指定日期的 Swarm-A POD
同一天多個版本 -> 取最高版本
本機同名且大小相符 -> 沿用 ZIP
否則 -> 下載 -> 與 ESA 清單核對大小 -> 保留 ZIP
```

```text
ESA Swarm-A POD archive
[
  {
    day: 2023-07-01,
    ZIP: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.ZIP"
  },
  ...
]
```

```text
research_workspace/phases/phase0/data/raw/swarm_a_pod (local archive)
[
  {
    file_name: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.ZIP",
    ZIP: {
      orbit: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.sp3",
      header: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.HDR"
    }
  },
  ...
]
```

### [P1.2] POD ZIP -> raw POD SQLite [done]

```text
load_swarm_pod.py -> load_swarm_pod()
prep_01_raw_pod.py -> write_pod_file()

ZIP .sp3 -> GPS epoch + P (km) + V (dm/s)
GPS -> UTC -> time_us
P (km) -> position (m)；V (dm/s) -> velocity (m/s)；state frame = ITRF
UTC -> 所在三小時區塊起點 -> weather_time_us
該區塊不存在 -> 不寫入 state
ZIP + 簽章 -> source_files -> source_id -> swarm_a_states
```

```text
research_workspace/phases/phase0/data/raw/swarm_a_pod (local archive)
{
  file_name: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.ZIP",
  ZIP: {
    orbit: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.sp3",
    header: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.HDR"
  }
}
```

```text
SQLite
{
  source_files (raw):
  [
    {
      source_id: 3459,
      file_name: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.ZIP",
      signature: "439935:1789741157714505500"
    },
    ...
  ],
  swarm_a_states (raw; ITRF):
  [
    {
      time_us: 1688173252000000 (us),
      x_m: -6.225e6 (m),
      y_m: 2.894e6 (m),
      z_m: 2.234e4 (m),
      vx_m_s: 9.498e1 (m/s),
      vy_m_s: 1.206e2 (m/s),
      vz_m_s: 7.614e3 (m/s),
      weather_time_us: 1688169600000000 (us),
      source_id: 3459
    },
    ...
  ]
}
```

### [P1.3] raw POD -> instantaneous orbital element [done]

```text
prep_03_orbital_elements.py -> write_orbital_elements()

swarm_a_states (ITRF) -> GCRF state
GCRF (r, v) -> specific orbital energy E = v^2 / 2 - mu / r
E -> osculating semi-major axis a = -mu / (2E)
mu = 地球重力參數。
距離、速度或能量無效 -> 保留 time_us + 寫入 rejection_reason
這是 osculating semi-major axis，不是直接量到的 drag 或衰減率。
```

```text
SQLite
{
  swarm_a_states (raw; ITRF):
  [
    {
      time_us: 1688173252000000 (us),
      x_m: -6.225e6 (m),
      y_m: 2.894e6 (m),
      z_m: 2.234e4 (m),
      vx_m_s: 9.498e1 (m/s),
      vy_m_s: 1.206e2 (m/s),
      vz_m_s: 7.614e3 (m/s),
      weather_time_us: 1688169600000000 (us),
      source_id: 3459
    },
    ...
  ]
}
```

```text
SQLite
{
  swarm_a_orbital_elements (derived):
  [
    {
      time_us: 1688173252000000 (us),
      semi_major_axis_m: 6.869e6 (m),
      rejection_reason: null
    },
    ...
  ]
}
```

### [P1.4] raw POD + orbital element -> quality / chunk [done]

```text
prep_02_source_provenance.py -> write_source_provenance()
prep_05_pod_quality.py -> write_pod_quality()

ZIP + source_files
  -> SP3 header -> frame + UTC 覆蓋端點 + epoch 數 + cadence
  -> swarm_a_pod_source_provenance

state + 瞬時半長軸 + source_files + provenance
  -> 數值 + 軌道元素 + 已確認的軌道事件檢查
  -> swarm_a_pod_quality（可用性與拒絕原因）

相鄰可用點的 product stream / frame / cadence 不同，或時間差 != cadence -> 新 chunk
只換 ZIP 檔 -> 不一定切 chunk
不可用點 -> chunk_id = null；其後第一個可用點 -> 新 chunk
```

```text
research_workspace/phases/phase0/data/raw/swarm_a_pod (local archive)
{
  file_name: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.ZIP",
  ZIP: {
    orbit: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.sp3",
    header: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.HDR"
  }
}

SQLite
{
  source_files (raw):
  [
    {
      source_id: 3459,
      file_name: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.ZIP",
      signature: "439935:1789741157714505500"
    },
    ...
  ],
  swarm_a_states (raw; ITRF):
  [
    {
      time_us: 1688173252000000 (us),
      x_m: -6.225e6 (m),
      y_m: 2.894e6 (m),
      z_m: 2.234e4 (m),
      vx_m_s: 9.498e1 (m/s),
      vy_m_s: 1.206e2 (m/s),
      vz_m_s: 7.614e3 (m/s),
      weather_time_us: 1688169600000000 (us),
      source_id: 3459
    },
    ...
  ],
  swarm_a_orbital_elements (derived):
  [
    {
      time_us: 1688173252000000 (us),
      semi_major_axis_m: 6.869e6 (m),
      rejection_reason: null
    },
    ...
  ]
}
```

```text
SQLite
{
  swarm_a_pod_source_provenance (derived):
  [
    {
      source_id: 3459,
      sp3_frame_label: "IGS20",
      coverage_start_time_us: 1688169582000000 (us),
      coverage_end_time_us: 1688255972000000 (us),
      epoch_count: 8640,
      cadence_s: 1.000e1 (s),
      time_system: "GPS"
    },
    ...
  ],
  swarm_a_pod_quality (derived):
  [
    {
      time_us: 1688173252000000 (us),
      is_usable: 1,
      rejection_reason: null,
      chunk_id: 11
    },
    ...
  ]
}
```

### [P1.5] mean orbit -> 10-minute / phase-defined decay candidates [working]

#### [P1.5.1] raw POD -> mean elements [done]

```text
prep_04_mean_orbit.py -> write_mean_orbit_elements()

P1.3 半長軸存在且 rejection_reason = null -> 選取同一 time_us 的 raw state
ITRF -> GCRF -> Orekit Brouwer-Lyddane (J2 至 J5；M2 = 0) -> mean elements
fixed-point convergence epsilon = 1e-13；maxIterations = 5000。
每個 epoch 保留原 time_us；版本 = orekit_brouwer_lyddane_j2_to_j5_m2_0_v3。
P1.4 quality / chunk 不參與此轉換，只在 P1.5.2 篩選。
新版 checkpoint 沿用已在 200 iterations 內收斂的 v2 row；只重算 v2 明確記錄的 rejection。
全期重算 233 row；三年版沒有 rejection，不需重算 row。
完成驗證後寫入 `p1_5` checkpoint；一般下游 rebuild 只能複製它，不可重新計算。
```

```text
SQLite
{
  swarm_a_states (raw; ITRF):
  [
    {
      time_us: 1688173252000000 (us),
      x_m: -6.225e6 (m),
      y_m: 2.894e6 (m),
      z_m: 2.234e4 (m),
      vx_m_s: 9.498e1 (m/s),
      vy_m_s: 1.206e2 (m/s),
      vz_m_s: 7.614e3 (m/s),
      weather_time_us: 1688169600000000 (us),
      source_id: 3459
    },
    ...
  ],
  swarm_a_orbital_elements (derived):
  [
    {
      time_us: 1688173252000000 (us),
      semi_major_axis_m: 6.869e6 (m),
      rejection_reason: null
    },
    ...
  ]
}
```

```text
SQLite
{
  swarm_a_mean_orbit_elements_v1 (derived):
  [
    {
      time_us: 1688173252000000 (us),
      mean_semi_major_axis_m: 6.859e6 (m),
      mean_eccentricity: 8.822e-4,
      mean_inclination_rad: 1.527e0 (rad),
      mean_longitude_rad: 1.556e0 (rad),
      mean_eccentric_longitude_rad: 1.556e0 (rad),
      mean_true_longitude_rad: 1.556e0 (rad),
      mean_equinoctial_ex: -1.331e-4,
      mean_equinoctial_ey: -8.721e-4,
      mean_equinoctial_hx: 1.982e-2,
      mean_equinoctial_hy: 9.569e-1,
      mean_keplerian_period_s: 5.654e3 (s),
      mean_keplerian_mean_motion_rad_s: 1.111e-3 (rad/s),
      mean_argument_of_perigee_rad: 3.011e0 (rad),
      mean_raan_rad: 1.550e0 (rad),
      mean_anomaly_rad: -3.005e0 (rad),
      mean_eccentric_anomaly_rad: -3.005e0 (rad),
      mean_true_anomaly_rad: -3.005e0 (rad),
      mean_x_m: 1.405e5 (m),
      mean_y_m: 6.864e6 (m),
      mean_z_m: 3.900e4 (m),
      mean_vx_m_s: -3.347e2 (m/s),
      mean_vy_m_s: -3.730e1 (m/s),
      mean_vz_m_s: 7.609e3 (m/s),
      rejection_reason: null
    },
    ...
  ]
}
```

全期 current checkpoint 有 39,346,558 筆（2014-01-01 至 2026-07-01 UTC），rejection 0 筆。
三年 current checkpoint 有 9,469,438 筆（2023-07-01 至 2026-07-01 UTC），rejection 0 筆。
全期 raw／quality 各有 39,346,560 筆；多出的兩筆 `time_us` 是
1388534384000000 與 1388534394000000 (us)，即 2013-12-31 23:59:44／23:59:54
UTC，在 mean-element 起始範圍之外。quality 中 38,378,880 筆可用，
扣除這兩筆後與 12 年 P1.5.6 v2 的 38,378,878 個來源鍵一致。
兩者所有 mean element 欄位皆為有限值，SQLite integrity check 為 `ok`，foreign-key violation 為 0。

#### [P1.5.2] mean elements -> 10-minute mean [retained]

```text
prep_06_orbit_10min.py -> write_orbit_10min()

p1_5 checkpoint -> 完整複製至 working database -> 讀取既有 mean elements
mean elements + P1.4 quality -> 依 time_us 對齊 -> 可用且 mean a 有值的點
可用點 -> 依 chunk_id 分開 -> 依 UTC 10 分鐘結束時間分 bin
每個 bin -> mean a 平均 + POD 點數 + 最大相鄰時間差
POD 點數 >= 56 且最大時間差 <= 10 s -> 保留 bin
非 chunk 首尾的 bin 還須剛好 60 點；不同 chunk 不合併。
```

```text
SQLite
{
  swarm_a_mean_orbit_elements_v1 (derived):
  [
    {
      time_us: 1688173252000000 (us),
      mean_semi_major_axis_m: 6.859e6 (m),
      mean_eccentricity: 8.822e-4,
      mean_inclination_rad: 1.527e0 (rad),
      mean_longitude_rad: 1.556e0 (rad),
      mean_eccentric_longitude_rad: 1.556e0 (rad),
      mean_true_longitude_rad: 1.556e0 (rad),
      mean_equinoctial_ex: -1.331e-4,
      mean_equinoctial_ey: -8.721e-4,
      mean_equinoctial_hx: 1.982e-2,
      mean_equinoctial_hy: 9.569e-1,
      mean_keplerian_period_s: 5.654e3 (s),
      mean_keplerian_mean_motion_rad_s: 1.111e-3 (rad/s),
      mean_argument_of_perigee_rad: 3.011e0 (rad),
      mean_raan_rad: 1.550e0 (rad),
      mean_anomaly_rad: -3.005e0 (rad),
      mean_eccentric_anomaly_rad: -3.005e0 (rad),
      mean_true_anomaly_rad: -3.005e0 (rad),
      mean_x_m: 1.405e5 (m),
      mean_y_m: 6.864e6 (m),
      mean_z_m: 3.900e4 (m),
      mean_vx_m_s: -3.347e2 (m/s),
      mean_vy_m_s: -3.730e1 (m/s),
      mean_vz_m_s: 7.609e3 (m/s),
      rejection_reason: null
    },
    ...
  ],
  swarm_a_pod_quality (derived):
  [
    {
      time_us: 1688173252000000 (us),
      is_usable: 1,
      rejection_reason: null,
      chunk_id: 11
    },
    ...
  ]
}
```

```text
SQLite
{
  swarm_a_orbit_10min (derived):
  [
    {
      time_us: 1688173800000000 (us),
      semi_major_axis_orbit_mean_m: 6.859e6 (m),
      pod_count: 60,
      max_pod_gap_s: 1.000e1 (s),
      chunk_id: 11,
      algorithm_version: "utc_10min_mean_brouwer_lyddane_v1"
    },
    ...
  ]
}
```

已刪除的舊 `p1_7` 複本曾記錄 157,824 筆 10-minute row；該數量與上例是歷史紀錄，現有四份 SQLite 無法重新查驗。`time_us` 原定義是 bin 結束時間。

#### [P1.5.3] 10-minute mean -> backward rate [retained]

```text
prep_07_decay_rate.py -> write_decay_rates()

10-minute mean -> 依 chunk_id、time_us 排序 -> 連續序列
chunk 改變或相鄰 bin 時差 != 10 分鐘 -> 切斷序列
每筆輸出都須在同一連續序列找到 3、6、12 小時前的 bin。

t-3h   -> a(t-3h)  --\
t-6h   -> a(t-6h)  ---+-> 各自與目前的 a(t) 相減，再除以對應秒數
t-12h  -> a(t-12h) --/

差值 / 對應秒數 -> 3/6/12 h backward rate (m/s) -> 乘 86400 -> m/day
連續序列未滿 12 小時 -> 無 rate 輸出
```

```text
SQLite
{
  swarm_a_orbit_10min (derived):
  [
    {
      time_us: 1688217000000000 (us),
      semi_major_axis_orbit_mean_m: 6.859e6 (m),
      pod_count: 60,
      max_pod_gap_s: 1.000e1 (s),
      chunk_id: 11,
      algorithm_version: "utc_10min_mean_brouwer_lyddane_v1"
    },
    ...
  ]
}
```

```text
SQLite
{
  swarm_a_orbit_decay_10min (derived):
  [
    {
      time_us: 1688217000000000 (us),
      semi_major_axis_orbit_mean_m: 6.859e6 (m),
      da_dt_3h_backward_m_s: -7.310e-3 (m/s),
      da_dt_3h_backward_m_day: -6.316e2 (m/day),
      da_dt_6h_backward_m_s: -8.664e-3 (m/s),
      da_dt_6h_backward_m_day: -7.485e2 (m/day),
      da_dt_12h_backward_m_s: -5.016e-3 (m/s),
      da_dt_12h_backward_m_day: -4.334e2 (m/day),
      chunk_id: 11,
      algorithm_version: "backward_difference_3h_6h_12h_mean_orbit_v3"
    },
    ...
  ]
}
```

已刪除的舊 `p1_7` 複本曾記錄 157,608 筆 rate row；該數量與上例是歷史紀錄，現有四份 SQLite 無法重新查驗。`time_us` 原定義是目前 bin 結束時間。

#### [P1.5.4] mean elements -> phase-weighted complete-orbit mean [working]

```text
prep_10_phase_orbit_mean.py -> write_phase_orbit_means()

u = (mean_argument_of_perigee_rad + mean_anomaly_rad) mod 2pi
H2/H3 Fourier expansion: Hn(u) = Cn cos(nu) + Sn sin(nu)

u 定義 orbit phase，不使用固定 UTC 46-minute clock。`chunk_id` 改變或 POD gap > 10 s 時重設 phase；只保留完整 phase orbit。
```

```text
swarm_a_mean_orbit_elements_v1 (derived；欄位節錄)
[
  {
    time_us: 1688173252000000 (us),
    mean_semi_major_axis_m: 6.859e6 (m),
    mean_argument_of_perigee_rad: 3.011e0 (rad),
    mean_anomaly_rad: -3.005e0 (rad),
    rejection_reason: null
  },
  ...
]

swarm_a_pod_quality (derived；欄位節錄)
[
  {
    time_us: 1688173252000000 (us),
    is_usable: 1,
    chunk_id: 11
  },
  ...
]
```

```text
swarm_a_phase_orbit_mean_v2 (derived)
[
  {
    time_us: 1688178902000000 (us),
    orbit_start_time_us: 1688173252000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.859e6 (m),
    h2_cosine_m: 6.314e1 (m),
    h2_sine_m: -2.631e0 (m),
    h2_amplitude_m: 6.319e1 (m),
    h3_cosine_m: 4.391e1 (m),
    h3_sine_m: 4.040e1 (m),
    h3_amplitude_m: 5.967e1 (m),
    pod_count: 566,
    phase_coverage_rad: 6.271e0 (rad),
    max_pod_gap_s: 1.000e1 (s),
    chunk_id: 11,
    algorithm_version: "phase_weighted_orbit_h2_h3_local_ols_v1"
  },
  ...
]
```

`time_us` 是該完整 phase orbit 最後一筆 POD 的 UTC epoch。三年 working copy 有 16,844 rows；這是週期項分離的 candidate，不是已校準的物理 decay。

#### [P1.5.5] phase-orbit mean -> H2/H3 diagnostic [working]

```text
prep_10_phase_orbit_mean.py -> write_harmonic_diagnostics()

P1.5.4 每圈 H2/H3 amplitude -> 依 chunk_id 彙整 median 與 max
只描述仍存在的 phase harmonic；不以 amplitude 門檻刪除 orbit，也不改寫 P1.5.4 mean。
```

```text
swarm_a_phase_orbit_mean_v2 (derived；欄位節錄)
[
  {
    time_us: 1688178902000000 (us),
    h2_amplitude_m: 6.319e1 (m),
    h3_amplitude_m: 5.967e1 (m),
    chunk_id: 11
  },
  ...
]
```

```text
swarm_a_phase_harmonic_diagnostic_v1 (derived)
[
  {
    chunk_id: 11,
    orbit_count: 8924,
    h2_amplitude_median_m: 6.474e1 (m),
    h2_amplitude_max_m: 9.770e1 (m),
    h3_amplitude_median_m: 3.921e1 (m),
    h3_amplitude_max_m: 6.686e1 (m),
    algorithm_version: "phase_weighted_orbit_h2_h3_local_ols_v1"
  },
  ...
]
```

三年 working copy 有 3 個 chunk diagnostic rows；此 table 沒有 `time_us`，key 是 phase estimator 的 `chunk_id`。

#### [P1.5.6] phase-defined local decay candidates [working]

```text
prep_14_phase_harmonic_decay_candidates.py -> write_decay_candidates()

u = unwrap(mean_argument_of_perigee_rad + mean_anomaly_rad)
u_start = u_end - N * 2pi, N in {3, 5}

每筆可用 10 s mean element 都是 window 右端點。`u_start` 落在兩筆 source 間時，對 time 與 a 線性內插一筆邊界；window 內其餘點保持原始 cadence。
raw rate = OLS slope of a(t)
joint rate = b1 in a(t) = b0 + b1(t - t0) + H2(u) + H3(u) + residual
H2(u) + H3(u) = C2 cos(2u) + S2 sin(2u) + C3 cos(3u) + S3 sin(3u)

window 不跨 `chunk_id`、source gap > 20 s 或非單調 u。無完整 N-orbit 範圍時 rate 為 null 並記錄 `reject_reason`；不因 residual 或 1-sigma 刪除已完成的 fit。raw B-L 與 joint H2/H3 各寫一張 table，兩者有相同 `time_us` key。
```

```text
swarm_a_mean_orbit_elements_v1 (derived；欄位節錄)
[
  {
    time_us: 1688173252000000 (us),
    mean_semi_major_axis_m: 6.859e6 (m),
    mean_argument_of_perigee_rad: 3.011e0 (rad),
    mean_anomaly_rad: -3.005e0 (rad)
  },
  ...
]
```

```text
swarm_a_phase_harmonic_decay_candidates_v1 (derived；retained legacy)
[
  {
    time_us: 1688190222000000 (us),
    decay_method: "joint_h2_h3_local_ols",
    orbit_window: 3,
    decay_rate_m_day: 2.266e1 (m/day),
    decay_rate_1sigma_m_day: 1.584e1 (m/day),
    fit_residual_std_m: 3.657e1 (m),
    sample_count: 1698,
    window_start_time_us: 1688173252000000 (us),
    chunk_id: 11,
    harmonic_orders: "2,3",
    algorithm_version: "raw_and_joint_h2_h3_trailing_orbit_ols_v1"
  },
  ...
]

swarm_a_phase_harmonic_decay_raw_b_l_sets_v1 (derived)
[
  {
    time_us: 1688201552000000 (us),
    chunk_id: 11,
    available_window_count: 2,
    orbit_3_window_start_time_us: 1688184572000000 (us),
    orbit_3_sample_count: 1699,
    orbit_3_decay_rate_m_day: -3.135e1 (m/day),
    orbit_3_decay_rate_1sigma_m_day: 1.804e1 (m/day),
    orbit_3_fit_residual_std_m: 4.220e1 (m),
    orbit_5_window_start_time_us: 1688173252000000 (us),
    orbit_5_sample_count: 2831,
    orbit_5_decay_rate_m_day: -2.865e1 (m/day),
    orbit_5_decay_rate_1sigma_m_day: 1.006e1 (m/day),
    orbit_5_fit_residual_std_m: 5.065e1 (m),
    harmonic_orders: "",
    algorithm_version: "phase_harmonic_decay_raw_b_l_sets_v1"
  },
  ...
]

swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v1 (derived)
[
  {
    time_us: 1688201552000000 (us),
    chunk_id: 11,
    available_window_count: 2,
    orbit_3_window_start_time_us: 1688184572000000 (us),
    orbit_3_sample_count: 1699,
    orbit_3_decay_rate_m_day: -4.309e1 (m/day),
    orbit_3_decay_rate_1sigma_m_day: 1.335e1 (m/day),
    orbit_3_fit_residual_std_m: 3.086e1 (m),
    orbit_5_window_start_time_us: 1688173252000000 (us),
    orbit_5_sample_count: 2831,
    orbit_5_decay_rate_m_day: -2.171e1 (m/day),
    orbit_5_decay_rate_1sigma_m_day: 8.022e0 (m/day),
    orbit_5_fit_residual_std_m: 4.020e1 (m),
    harmonic_orders: "2,3",
    algorithm_version: "phase_harmonic_decay_joint_h2_h3_sets_v1"
  },
  ...
]
```

`v1` long table 與其 two wide tables 保留給既有 P1.6/P1.7 branch，不是 current P1.5.6 output。

```text
swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 (derived)
[
  {
    time_us: 1688197912000000 (us),
    chunk_id: 11,
    orbit_3_window_start_time_us: 1688180928017213 (us),
    orbit_3_sample_count: 1700,
    orbit_3_phase_span_rad: 1.885e1 (rad),
    orbit_3_decay_rate_m_s: -4.365e-4 (m/s),
    orbit_3_decay_rate_1sigma_m_s: 2.044e-4 (m/s),
    orbit_3_fit_residual_std_m: 4.136e1 (m),
    orbit_3_reject_reason: null,
    orbit_5_window_start_time_us: 1688169605602071 (us),
    orbit_5_sample_count: 2832,
    orbit_5_phase_span_rad: 3.142e1 (rad),
    orbit_5_decay_rate_m_s: -6.799e-4 (m/s),
    orbit_5_reject_reason: null,
    algorithm_version: "trailing_exact_phase_h2_h3_rolling_ols_v2"
  },
  ...
]

swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2 (derived)
[
  {
    time_us: 1688197912000000 (us),
    chunk_id: 11,
    orbit_3_decay_rate_m_s: 2.765e-4 (m/s),
    orbit_3_h2_cos_m: 2.369e1 (m),
    orbit_3_h2_sin_m: -2.194e0 (m),
    orbit_3_h3_cos_m: -1.721e1 (m),
    orbit_3_h3_sin_m: 1.616e1 (m),
    orbit_5_decay_rate_m_s: -3.023e-4 (m/s),
    orbit_5_h2_cos_m: 4.364e1 (m),
    orbit_5_h2_sin_m: -5.945e-1 (m),
    orbit_5_h3_cos_m: 5.950e0 (m),
    orbit_5_h3_sin_m: 2.503e1 (m),
    harmonic_orders: "2,3",
    algorithm_version: "trailing_exact_phase_h2_h3_rolling_ols_v2"
  },
  ...
]
```

三年 working copy 的 raw 與 joint table 各有 9,469,438 rows；每個可用 10 s source epoch 一列。3-orbit 有 9,464,376 valid fits，5-orbit 有 9,461,003 valid fits；其餘分別是 5,062 與 8,435 個 `insufficient_N_orbits`。`time_us` 是 trailing window 的右端點。OLS slope 是 descriptive candidate；maneuver、source、method anomaly 未校準前不得解讀為 storm-caused decay。

#### [P1.6] phase-harmonic causal features v2 [working]

```text
prep_15_phase_harmonic_features_v2.py -> write_phase_harmonic_features()

raw B-L v2 + joint H2/H3 v2 share `time_us` -> one causal feature record.
SYM-H is exact or linearly interpolated only when adjacent observations span <= 120 s.
Ap, F10.7, and F10.7A source times must not be later than `time_us`.
```

```text
swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 (derived; key) +
swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2 (derived; same key) +
geomagnetic (raw) + space_weather (raw)
[
  {
    time_us: 1688197912000000 (us)
  },
  ...
]
```

```text
swarm_a_phase_harmonic_features_v2 (derived)
[
  {
    time_us: 1688197912000000 (us),
    sym_h_nt: -1.600e1 (nT),
    sym_h_left_time_us: 1688197860000000 (us),
    sym_h_right_time_us: 1688197920000000 (us),
    ap_now: 3.000e0,
    ap_source_time_us: 1688191200000000 (us),
    f107_sfu: 1.622e2 (sfu),
    f107_source_time_us: 1688083200000000 (us),
    f107a_sfu: 1.571e2 (sfu),
    f107a_source_time_us: 1688083200000000 (us),
    quality_flags: "ok",
    algorithm_version: "causal_features_phase_harmonic_v2"
  },
  ...
]
```

P1.6 不複製四種 rate；rate 留在兩張 P1.5.6 table，feature 只以 `time_us` 一對一寫一次。三年 feature table 有 9,469,438 rows；12 年 writer metadata 記錄 38,378,878 rows，P1.7 已驗證 feature 與 rate 的 time key 一致。

#### [P1.7] phase-harmonic v2 audit [done]

```text
prep_16_phase_harmonic_audit_v2.py -> write_phase_harmonic_audit_v2()

raw B-L v2 + joint H2/H3 v2 + P1.6 features v2 -> key identity, rate-validity parity,
feature causality, finite values, SQLite integrity -> audit rows + manifest metadata.
```

```text
swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 (derived；欄位節錄) +
swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2 (derived；欄位節錄) +
swarm_a_phase_harmonic_features_v2 (derived；欄位節錄)
[
  {
    time_us: 1688197912000000 (us)
  },
  ...
]
```

```text
swarm_a_phase_harmonic_audit_v2 (derived；欄位節錄)
[
  {
    audit_name: "raw_joint_time_key_identity",
    violation_count: 0,
    scope_start_time_us: 1388534404000000 (us),
    scope_stop_time_us: 1782863972000000 (us),
    algorithm_version: "phase_harmonic_audit_v2"
  },
  ...
]
```

兩份 working copy 的 audit table 均有 6 rows，所有 `violation_count = 0`；metadata `p1_7_phase_harmonic_v2_status = pass`。上例取自 12 年 working copy；scope start/end 是該 rate table 首末 `time_us`，不是 Phase 2 的事件窗。三年 audit scope 為 1688169602000000 至 1782863972000000 (us)。audit pass 只表示資料結構可追溯，不表示 decay 已校準。

#### [P1.6] phase-candidate causal features v1 [retained]

```text
prep_10_phase_harmonic_decay_analysis.py -> write_phase_harmonic_decay_analysis()

candidate key `(time_us, decay_method, orbit_window)` 原樣保留。
SYM-H 用同時刻原值，或左右 observation 總間隔 <= 2 分鐘時線性插值。
Ap 取 candidate 所在 3-hour block；F10.7 與 F10.7A 取前一個 UTC day，避免 future feature。
```

```text
swarm_a_phase_harmonic_decay_candidates_v1 (derived；欄位節錄)
[
  {
    time_us: 1688190222000000 (us),
    decay_method: "joint_h2_h3_local_ols",
    orbit_window: 3,
    decay_rate_m_day: 2.266e1 (m/day),
    chunk_id: 11
  },
  ...
]

geomagnetic (raw；欄位節錄)
[
  {
    time_us: 1688190180000000 (us),
    sym_h_nt: -1.800e1 (nT)
  },
  {
    time_us: 1688190240000000 (us),
    sym_h_nt: -1.800e1 (nT)
  },
  ...
]

space_weather (raw；欄位節錄)
[
  {
    time_us: 1688180400000000 (us),
    ap_now: 7.000e0
  },
  {
    time_us: 1688083200000000 (us),
    f107_sfu: 1.622e2 (sfu),
    f107a_last81_sfu: 1.571e2 (sfu),
    f107_data_type: "OBS"
  },
  ...
]
```

```text
swarm_a_phase_harmonic_decay_analysis_v1 (derived)
[
  {
    time_us: 1688190222000000 (us),
    decay_method: "joint_h2_h3_local_ols",
    orbit_window: 3,
    decay_rate_m_day: 2.266e1 (m/day),
    decay_rate_1sigma_m_day: 1.584e1 (m/day),
    fit_residual_std_m: 3.657e1 (m),
    sample_count: 1698,
    window_start_time_us: 1688173252000000 (us),
    chunk_id: 11,
    harmonic_orders: "2,3",
    sym_h_nt: -1.800e1 (nT),
    sym_h_left_time_us: 1688190180000000 (us),
    sym_h_right_time_us: 1688190240000000 (us),
    ap_now: 7.000e0,
    ap_source_time_us: 1688180400000000 (us),
    f107_sfu: 1.622e2 (sfu),
    f107_source_time_us: 1688083200000000 (us),
    f107a_sfu: 1.571e2 (sfu),
    f107a_source_time_us: 1688083200000000 (us),
    quality_flags: "ok",
    algorithm_version: "causal_features_phase_harmonic_decay_v1"
  },
  ...
]
```

三年 working copy 有 67,328 rows。Feature source time 不可晚於 candidate time；SYM-H right endpoint 最多可晚 120 s。這是 candidate 與同時可用 feature 的對齊，不是 storm-caused decay 的證據。

#### [P1.7] phase-candidate audit v1 [retained]

```text
prep_11_phase_harmonic_decay_audit.py -> write_phase_harmonic_decay_audit()

P1.5.6 candidate + P1.6 analysis -> identity、causality、finite values、scope、branch-table SQLite integrity、P1.6 foreign keys 稽核
```

```text
swarm_a_phase_harmonic_decay_candidates_v1 (derived) + swarm_a_phase_harmonic_decay_analysis_v1 (derived)
```

```text
metadata
[
  {
    name: "p1_7_phase_harmonic_audit_status",
    value: "working_audit_pass"
  },
  ...
]
```

三年 audit 有 67,328 P1.5.6 candidates 與 67,328 P1.6 rows；candidate identity、future feature reference、non-finite value、scope、field mismatch 與 P1.6 foreign-key violation 都是 0。scope 固定為 [2023-07-01, 2026-07-01) UTC。`working_audit_pass` 只表示資料契約通過，不表示 decay 已校準。

## 資料與範例

以下用真實的 2023-07-01 POD row 作範例。浮點數用科學記號（尾數小數三位）；`time_us`、ID、計數保留原值。
顯示精度不供差分或擬合，計算須用 SQLite 原值。SP3 的 `time_system` 是 GPS；SQLite 的 `time_us` 是 UTC Unix 微秒。

```text
SQLite
{
  raw:
  {
    source_files: [row, ...],
    swarm_a_states: [row, ...],
    space_weather: [row, ...],
    geomagnetic: [row, ...]
  },

  derived:
  {
    swarm_a_pod_source_provenance: [row, ...],
    swarm_a_orbital_elements: [row, ...],
    swarm_a_pod_quality: [row, ...],
    swarm_a_mean_orbit_elements_v1: [row, ...],
    swarm_a_orbit_10min: [row, ...],
    swarm_a_orbit_decay_10min: [row, ...],
    swarm_a_analysis_10min: [row, ...],
    swarm_a_phase_orbit_mean_v2: [row, ...],
    swarm_a_phase_harmonic_diagnostic_v1: [row, ...],
    swarm_a_phase_harmonic_decay_candidates_v1: [row, ...],
    swarm_a_phase_harmonic_decay_raw_b_l_sets_v1: [row, ...],
    swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v1: [row, ...],
    swarm_a_phase_harmonic_decay_analysis_v1: [row, ...]
  },

  metadata: [row, ...]
}
```

以下數量來自三年 phase-candidate working copy。legacy 10-minute branch 不參與這條 candidate audit。

```text
Mean-element checkpoint: 9,469,438 mean-element rows
  -> full copy -> phase-candidate working copy
                    |-> P1.5.4: 16,844 PhaseOrbitMean
                                  -> P1.5.5: 3 H2/H3 diagnostics
                                  -> P1.5.6: 67,328 long candidates
                                      |-> 16,836 raw-B-L one-row sets
                                      |-> 16,836 joint-H2/H3 one-row sets
                                      -> P1.6: 67,328 candidate analysis rows
                                          -> P1.7: working_audit_pass
```

legacy P1.5 的 10-minute bin 不跨 `chunk_id`；3/6/12 h rate 用 backward difference，並非目前 phase-candidate chain 的輸入。
P1.5.4 phase orbit 在 `chunk_id` 改變或 POD gap > 10 s 時切斷；P1.5.6 視窗同樣不跨 `chunk_id` 或 source gap。

```text
swarm_a_states: [{time_us, x_m, y_m, z_m, vx_m_s, vy_m_s, vz_m_s, source_id}, ...]
swarm_a_orbital_elements: [{time_us, semi_major_axis_m, rejection_reason}, ...]
swarm_a_pod_quality: [{time_us, is_usable, chunk_id, rejection_reason}, ...]
swarm_a_mean_orbit_elements_v1: [{time_us, mean_semi_major_axis_m, ...}, ...]
swarm_a_orbit_10min: [{time_us, semi_major_axis_orbit_mean_m, pod_count, chunk_id}, ...]
swarm_a_orbit_decay_10min:
  [{time_us, da_dt_3h_backward_m_s, da_dt_6h_backward_m_s,
    da_dt_12h_backward_m_s, ...}, ...]
swarm_a_analysis_10min: [{time_us, backward rates, weather, geomagnetic, quality_flags}, ...]
swarm_a_phase_orbit_mean_v2: [{time_us, orbit_start_time_us, phase_weighted_mean_semi_major_axis_m, h2_amplitude_m, h3_amplitude_m, ...}, ...]
swarm_a_phase_harmonic_diagnostic_v1: [{chunk_id, h2_amplitude_median_m, h3_amplitude_median_m, ...}, ...]
swarm_a_phase_harmonic_decay_candidates_v1:
  [{time_us, decay_method, orbit_window, decay_rate_m_day,
    decay_rate_1sigma_m_day, sample_count, ...}, ...]
swarm_a_phase_harmonic_decay_raw_b_l_sets_v1:
  [{time_us, orbit_3_decay_rate_m_day, orbit_5_decay_rate_m_day, ...}, ...]
swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v1:
  [{time_us, orbit_3_decay_rate_m_day, orbit_5_decay_rate_m_day, ...}, ...]
swarm_a_phase_harmonic_decay_analysis_v1:
  [{time_us, decay_method, orbit_window, decay_rate_m_day,
    sym_h_nt, ap_now, f107_sfu, f107a_sfu, quality_flags, ...}, ...]
metadata: [{name, value}, ...]
```

```text
source_files:
[
  {
    source_id: 3459,
    file_name: "SW_OPER_SP3ACOM_2__20230630T235942_20230701T235942_0203.ZIP",
    signature: "439935:1789741157714505500"
  },
  ...
]

swarm_a_pod_source_provenance:
[
  {
    source_id: 3459,
    sp3_frame_label: "IGS20",
    coverage_start_time_us: 1688169582000000 (us),
    coverage_end_time_us: 1688255972000000 (us),
    epoch_count: 8640 (epochs),
    cadence_s: 10 (s),
    time_system: "GPS"
  },
  ...
]

swarm_a_states:
[
  {
    time_us: 1688173252000000 (us),
    x_m: -6.225e6 (m),
    y_m: 2.894e6 (m),
    z_m: 2.234e4 (m),
    vx_m_s: 9.498e1 (m/s),
    vy_m_s: 1.206e2 (m/s),
    vz_m_s: 7.614e3 (m/s),
    weather_time_us: 1688169600000000 (us),
    source_id: 3459
  },
  ...
]

space_weather:
[
  {
    time_us: 1688212800000000 (us),
    ap_now: 3
  },
  {
    time_us: 1688083200000000 (us),
    f107_sfu: 1.622e2 (sfu),
    f107a_last81_sfu: 1.571e2 (sfu)
  },
  ...
]

geomagnetic:
[
  {
    time_us: 1688217000000000 (us),
    sym_h_nt: -10 (nT)
  },
  ...
]

swarm_a_orbital_elements:
[
  {
    time_us: 1688173252000000 (us),
    semi_major_axis_m: 6.869e6 (m),
    rejection_reason: null
  },
  ...
]

swarm_a_pod_quality:
[
  {
    time_us: 1688173252000000 (us),
    is_usable: 1,
    rejection_reason: null,
    chunk_id: 11
  },
  ...
]

swarm_a_mean_orbit_elements_v1:
[
  {
    time_us: 1688173252000000 (us),
    mean_semi_major_axis_m: 6.859e6 (m),
    mean_eccentricity: 8.822e-4,
    mean_inclination_rad: 1.527e0 (rad),
    mean_longitude_rad: 1.556e0 (rad),
    mean_eccentric_longitude_rad: 1.556e0 (rad),
    mean_true_longitude_rad: 1.556e0 (rad),
    mean_equinoctial_ex: -1.331e-4,
    mean_equinoctial_ey: -8.721e-4,
    mean_equinoctial_hx: 1.982e-2,
    mean_equinoctial_hy: 9.569e-1,
    mean_keplerian_period_s: 5.654e3 (s),
    mean_keplerian_mean_motion_rad_s: 1.111e-3 (rad/s),
    mean_argument_of_perigee_rad: 3.011e0 (rad),
    mean_raan_rad: 1.550e0 (rad),
    mean_anomaly_rad: -3.005e0 (rad),
    mean_eccentric_anomaly_rad: -3.005e0 (rad),
    mean_true_anomaly_rad: -3.005e0 (rad),
    mean_x_m: 1.405e5 (m),
    mean_y_m: 6.864e6 (m),
    mean_z_m: 3.900e4 (m),
    mean_vx_m_s: -3.347e2 (m/s),
    mean_vy_m_s: -3.730e1 (m/s),
    mean_vz_m_s: 7.609e3 (m/s),
    rejection_reason: null
  },
  ...
]

swarm_a_orbit_10min:
[
  {
    time_us: 1688173800000000 (us),
    semi_major_axis_orbit_mean_m: 6.859e6 (m),
    pod_count: 60,
    max_pod_gap_s: 10 (s),
    chunk_id: 11,
    algorithm_version: "utc_10min_mean_brouwer_lyddane_v1"
  },
  ...
]

swarm_a_orbit_decay_10min:
[
  {
    time_us: 1688217000000000 (us),
    semi_major_axis_orbit_mean_m: 6.859e6 (m),
    da_dt_3h_backward_m_s: -7.310e-3 (m/s),
    da_dt_3h_backward_m_day: -6.316e2 (m/day),
    da_dt_6h_backward_m_s: -8.664e-3 (m/s),
    da_dt_6h_backward_m_day: -7.485e2 (m/day),
    da_dt_12h_backward_m_s: -5.016e-3 (m/s),
    da_dt_12h_backward_m_day: -4.334e2 (m/day),
    chunk_id: 11,
    algorithm_version: "backward_difference_3h_6h_12h_mean_orbit_v3"
  },
  ...
]

swarm_a_analysis_10min:
[
  {
    time_us: 1688217000000000 (us),
    semi_major_axis_orbit_mean_m: 6.859e6 (m),
    da_dt_3h_backward_m_s: -7.310e-3 (m/s),
    da_dt_3h_backward_m_day: -6.316e2 (m/day),
    da_dt_6h_backward_m_s: -8.664e-3 (m/s),
    da_dt_6h_backward_m_day: -7.485e2 (m/day),
    da_dt_12h_backward_m_s: -5.016e-3 (m/s),
    da_dt_12h_backward_m_day: -4.334e2 (m/day),
    pod_count: 60,
    max_pod_gap_s: 10 (s),
    chunk_id: 11,
    sym_h_nt: -10 (nT),
    sym_h_left_time_us: 1688217000000000 (us),
    sym_h_right_time_us: 1688217000000000 (us),
    ap_now: 3,
    ap_source_time_us: 1688212800000000 (us),
    f107_sfu: 1.622e2 (sfu),
    f107_source_time_us: 1688083200000000 (us),
    f107a_sfu: 1.571e2 (sfu),
    f107a_source_time_us: 1688083200000000 (us),
    f107_data_type: "OBS",
    quality_flags: "ok",
    algorithm_version: "causal_space_weather_geomagnetic_backward_3h_6h_12h_v3"
  },
  ...
]

swarm_a_phase_orbit_mean_v2:
[
  {
    time_us: 1688178902000000 (us),
    orbit_start_time_us: 1688173252000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.859e6 (m),
    h2_cosine_m: 6.314e1 (m),
    h2_sine_m: -2.631e0 (m),
    h2_amplitude_m: 6.319e1 (m),
    h3_cosine_m: 4.391e1 (m),
    h3_sine_m: 4.040e1 (m),
    h3_amplitude_m: 5.967e1 (m),
    pod_count: 566,
    phase_coverage_rad: 6.271e0 (rad),
    max_pod_gap_s: 1.000e1 (s),
    chunk_id: 11,
    algorithm_version: "phase_weighted_orbit_h2_h3_local_ols_v1"
  },
  ...
]

swarm_a_phase_harmonic_diagnostic_v1:
[
  {
    chunk_id: 11,
    orbit_count: 8924,
    h2_amplitude_median_m: 6.474e1 (m),
    h2_amplitude_max_m: 9.770e1 (m),
    h3_amplitude_median_m: 3.921e1 (m),
    h3_amplitude_max_m: 6.686e1 (m),
    algorithm_version: "phase_weighted_orbit_h2_h3_local_ols_v1"
  },
  ...
]

swarm_a_phase_harmonic_decay_candidates_v1:
[
  {
    time_us: 1688190222000000 (us),
    decay_method: "joint_h2_h3_local_ols",
    orbit_window: 3,
    decay_rate_m_day: 2.266e1 (m/day),
    decay_rate_1sigma_m_day: 1.584e1 (m/day),
    fit_residual_std_m: 3.657e1 (m),
    sample_count: 1698,
    window_start_time_us: 1688173252000000 (us),
    chunk_id: 11,
    algorithm_version: "raw_and_joint_h2_h3_trailing_orbit_ols_v1"
  },
  ...
]

swarm_a_phase_harmonic_decay_analysis_v1:
[
  {
    time_us: 1688190222000000 (us),
    decay_method: "joint_h2_h3_local_ols",
    orbit_window: 3,
    decay_rate_m_day: 2.266e1 (m/day),
    sym_h_nt: -1.800e1 (nT),
    ap_now: 7.000e0,
    f107_sfu: 1.622e2 (sfu),
    f107a_sfu: 1.571e2 (sfu),
    chunk_id: 11,
    quality_flags: "ok",
    algorithm_version: "causal_features_phase_harmonic_decay_v1"
  },
  ...
]

metadata:
[
  {
    name: "p1_7_release_status",
    value: "working_audit_pass"
  },
  ...
]
```
