# POD Data Lineage

```text
ESA -> ZIP -> SP3 -> State -> SQLite -> mean orbit -> 10-minute analysis
```

## [1] ESA file list -> local ZIP files

```text
down_swarm_pod.py
  -> list_swarm_pod_files()
  -> select_latest_files()
  -> download_file()

same day -> highest version
same file + same size -> keep local ZIP
```

```text
[
  {day: 2024-05-10, version: 0101},
  {day: 2024-05-10, version: 0102}
]
```

```text
[
  {
    file_name: "SW_OPER_SP3ACOM_2__20240510...0102.ZIP",
    ZIP: {orbit.sp3}
  },
  ...
]
```

## [2] one ZIP -> SP3 records

```text
load_swarm_pod.py -> load_swarm_pod()

"*" -> GPS_time
"P" -> P [km]
"V" -> V [dm/s]
```

```text
{
  file_name: "SW_OPER_SP3ACOM_2__20240510...0102.ZIP",
  ZIP: {orbit.sp3}
}
```

```text
[
  {
    GPS_time: 2024-05-10 14:20:20,
    P: [6871.0, 0.0, 0.0] km,
    V: [0.0, 75000.0, 0.0] dm/s
  },
  ...
]
```

## [3] one SP3 record -> one State

```text
load_swarm_pod.py
calc_time.py -> gps_times_to_utc()

GPS -> UTC
P [km] -> position [m]
V [dm/s] -> velocity [m/s]
```

```text
{
  GPS_time: 2024-05-10 14:20:20,
  P: [6871.0, 0.0, 0.0] km,
  V: [0.0, 75000.0, 0.0] dm/s
}
```

```text
{
  time: 2024-05-10 14:20:02 UTC,
  frame: ITRF,
  position: [6871000.0, 0.0, 0.0] m,
  velocity: [0.0, 7500.0, 0.0] m/s
}
```

## [4] [State, ...] -> SQLite

```text
prep_raw_database.py -> write_pod_folder()
prep_raw_pod.py -> write_pod_file()

file_signature() -> source_files
time_to_us() -> time_us
weather_block_time() -> weather_time
```

```text
[
  {
    time: 2024-05-10 14:20:02 UTC,
    frame: ITRF,
    position: [6871000.0, 0.0, 0.0] m,
    velocity: [0.0, 7500.0, 0.0] m/s
  },
  ...
]
```

```text
SQLite
{
  source_files:
  [
    {
      source_id: 17,
      file_name: "SW_OPER_SP3ACOM_2__20240510...0102.ZIP",
      frame: "IGS20",
      coverage: [2024-05-10 00:00:02, 2024-05-10 23:59:52] UTC,
      cadence: 10 s,
      epoch_count: 8640
    },
    ...
  ],

  swarm_a_states:
  [
    {
      time: 2024-05-10 14:20:02 UTC,
      position: [6871000.0, 0.0, 0.0] m,
      velocity: [0.0, 7500.0, 0.0] m/s,
      weather_time: 2024-05-10 12:00:00 UTC,
      source_id: 17
    },
    ...
  ]
}
```

## [5] raw State -> derived mean orbit + quality

```text
prep_derived_orbital_elements.py
  -> instantaneous semi-major axis [m]
prep_derived_pod_quality.py
  -> usable + chunk_id
prep_derived_mean_orbit.py
  -> mean semi-major axis [m]
```

```text
{
  time: 2024-05-10 14:20:02 UTC,
  position: [6871000.0, 0.0, 0.0] m,
  velocity: [0.0, 7500.0, 0.0] m/s
}
```

```text
{
  instantaneous_semi_major_axis: 6791172.2 m,
  quality: {usable: true, chunk_id: 2},
  mean_semi_major_axis: 6791100.4 m
}
```

## [6] mean State list -> UTC 10-minute orbit

```text
prep_derived_orbit_10min.py

[end - 600 s, end)
same chunk only
pod_count >= 56
```

```text
[
  {time: 2024-05-10 14:20:02 UTC, mean_semi_major_axis: 6791100.4 m, chunk_id: 2},
  ...
]
```

```text
{
  time: 2024-05-10 14:30:00 UTC,
  semi_major_axis_orbit_mean_m: 6791100.4 m,
  pod_count: 60,
  max_pod_gap_s: 10 s,
  chunk_id: 2
}
```

## [7] Orbit10Minute list -> decay / analysis row

```text
prep_derived_decay_rate.py
  -> centered Savitzky-Golay {73 samples, order 2}
prep_derived_analysis_10min.py
  -> causal weather + geomagnetic join
```

```text
{
  time: 2024-05-10 14:30:00 UTC,
  semi_major_axis_orbit_mean_m: 6791100.4 m,
  chunk_id: 2
}
```

```text
{
  time: 2024-05-10 14:30:00 UTC,
  decay_rate_smooth_m_day: 0.864 m/day,
  chunk_id: 2,
  quality_flags: "ok"
}
```

Current database has completed steps [1]--[7]. weather v2/v3 fresh rebuild is pending; see `../PHASE_1_FINAL_REPORT.md`.
