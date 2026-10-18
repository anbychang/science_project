# Orbit Analysis Data Products

新 release 的 analysis shape 使用 3/6/12 小時 backward decay definitions。P1.7 對每個 window 驗證同 chunk predecessor、差分與 m/day 換算；frozen metadata 只在 audit 通過後寫入。

```text
SQLite
{
  raw:
  {
    source_files: [SourceFile, ...],
    swarm_a_states: [State, ...],
    space_weather: [WeatherRecord, ...],
    geomagnetic: [GeomagneticRecord, ...],
    swarm_a_density: [DensityRecord, ...]
  },

  derived:
  {
    swarm_a_orbital_elements: [OsculatingOrbitElement, ...],
    swarm_a_pod_quality: [PodQuality, ...],
    swarm_a_mean_orbital_elements: [MeanOrbitElement, ...],
    swarm_a_orbit_10min: [Orbit10Minute, ...],
    swarm_a_analysis_10min: [Analysis10Minute, ...]
  },

  metadata: [MetadataEntry, ...]
}
```

歷史 frozen release 已存在 raw 五類、六個 derived 類與 `metadata`；新 release 的 row count 以 P1.7 manifest 為準。

```text
legacy frozen release:
14,558,400 State
  -> 13,495,680 usable MeanOrbitElement
  -> 224,928 Orbit10Minute
  -> 224,280 Analysis10Minute
```

`Orbit10Minute` 使用 `utc_10min_mean_brouwer_lyddane_v1`；每個 contiguous run 的前 72 列
排除後，`Analysis10Minute` 使用 `causal_space_weather_geomagnetic_backward_3h_6h_12h_v3`。`chunk_id`
是唯一的 chunk metadata；density 不 join core analysis table。

```text
swarm_a_orbital_elements: [{time, semi_major_axis_m, ...}, ...]
swarm_a_pod_quality: [{time, is_usable, chunk_id, rejection_reason}, ...]
swarm_a_mean_orbital_elements: [{time, mean_semi_major_axis_m, rejection_reason}, ...]
swarm_a_orbit_10min: [{time, mean_a, pod_count, max_gap, chunk_id}, ...]
swarm_a_orbit_decay_10min: [{time, mean_a, da_dt_3h_backward, da_dt_6h_backward, da_dt_12h_backward, chunk_id}, ...]
swarm_a_analysis_10min: [{orbit-decay fields, causal feature fields, quality_flags}, ...]
metadata: [{name, value}, ...]
```

```text
source_files:
[
  {
    file_name: "SW_OPER_SP3ACOM_2__20240510...0102.ZIP",
    coverage: [2024-05-10 00:00:02, 2024-05-10 23:59:52] UTC,
    frame: "IGS20",
    cadence: 10 s
  },
  ...
]

swarm_a_states:
[
  {
    time: 2024-05-10 14:20:02 UTC,
    position: [6871000.0, 0.0, 0.0] m,
    velocity: [0.0, 7500.0, 0.0] m/s,
    source_id: 17
  },
  {
    time: 2024-05-10 14:20:12 UTC,
    position: [... ] m,
    velocity: [... ] m/s,
    source_id: 17
  },
  ...
]

space_weather:
[
  {
    time: 2024-05-10 12:00:00 UTC,
    f107: 149.4 sfu,
    f107a: 145.8 sfu,
    ap: [8, 10, 8, 6, 5, 7.5, 6.1]
  },
  ...
]

geomagnetic:
[
  {
    time: 2024-05-10 14:20:00 UTC,
    sym_h: -42 nT,
    ae: 527 nT
  },
  ...
]

swarm_a_density:
[
  {
    time: 2024-05-10 14:20:00 UTC,
    density: 3.2e-12 kg/m^3,
    altitude: 465000 m,
    latitude: 42.1 deg,
    longitude: 121.4 deg
  },
  ...
]

swarm_a_orbit_10min:
[
  {
    time: 2024-05-10 14:30:00 UTC,
    semi_major_axis_orbit_mean_m: 6791100.4 m,
    pod_count: 60,
    max_pod_gap_s: 10 s,
    algorithm_version: "utc_10min_mean_brouwer_lyddane_v1",
    chunk_id: 2
  },
  ...
]

swarm_a_orbital_elements:
[
  {
    time: 2024-05-10 14:20:02 UTC,
    semi_major_axis_m: 6791172.2 m
  },
  ...
]

swarm_a_pod_quality:
[
  {
    time: 2024-05-10 14:20:02 UTC,
    is_usable: true,
    chunk_id: 2,
    rejection_reason: null
  },
  ...
]

swarm_a_mean_orbital_elements:
[
  {
    time: 2024-05-10 14:20:02 UTC,
    mean_semi_major_axis_m: 6791100.4 m,
    rejection_reason: null
  },
  ...
]

swarm_a_orbit_decay_10min:
[
  {
    time: 2024-05-10 14:30:00 UTC,
    semi_major_axis_orbit_mean_m: 6791100.1 m,
    da_dt_3h_backward_m_s: -0.00001 m/s,
    da_dt_3h_backward_m_day: -0.864 m/day,
    da_dt_6h_backward_m_s: -0.00001 m/s,
    da_dt_6h_backward_m_day: -0.864 m/day,
    da_dt_12h_backward_m_s: -0.00001 m/s,
    da_dt_12h_backward_m_day: -0.864 m/day,
    chunk_id: 2
  },
  ...
]

swarm_a_analysis_10min:
[
  {
    time: 2024-05-10 14:30:00 UTC,
    semi_major_axis_orbit_mean_m: 6791100.1 m,
    da_dt_3h_backward_m_s: -0.00001 m/s,
    da_dt_3h_backward_m_day: -0.864 m/day,
    da_dt_6h_backward_m_s: -0.00001 m/s,
    da_dt_6h_backward_m_day: -0.864 m/day,
    da_dt_12h_backward_m_s: -0.00001 m/s,
    da_dt_12h_backward_m_day: -0.864 m/day,
    pod_count: 60,
    max_pod_gap_s: 10 s,
    chunk_id: 2,
    sym_h_nt: -42 nT,
    sym_h_left_time: 2024-05-10 14:30:00 UTC,
    sym_h_right_time: 2024-05-10 14:30:00 UTC,
    ap_now: 8,
    ap_source_time: 2024-05-10 12:00:00 UTC,
    f107_sfu: 149.4 sfu,
    f107_source_time: 2024-05-09 00:00:00 UTC,
    f107a_sfu: 145.8 sfu,
    f107a_source_time: 2024-05-09 00:00:00 UTC,
    f107_data_type: "OBSERVED",
    quality_flags: "ok",
    algorithm_version: "causal_space_weather_geomagnetic_v1"
  },
  ...
]
```
