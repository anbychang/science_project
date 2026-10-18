# Phase 1 Orbit Lineage

```text
P1.1 POD ZIP
  -> P1.2 raw SQLite
  -> P1.3 orbital element
  -> P1.4 quality / chunk
  -> P1.5 mean orbit / 10-minute orbit / rate
  -> P1.6 causal feature join
  -> P1.7 audit manifest
```

唯一正式資料庫是 `data/swarm_a_analysis.sqlite`。以下每一段都是同一個 database
中的 table flow。

## P1.1 POD ZIP -> local POD archive

```text
down_swarm_pod.py

same day -> highest ZIP version
same name + same size -> keep local file
```

```text
[
  {day, version},
  ...
]
```

```text
[
  {
    file_name,
    ZIP: {orbit.sp3}
  },
  ...
]
```

## P1.2 POD ZIP -> raw SQLite

```text
load_swarm_pod.py -> load_swarm_pod()
prep_01_raw_pod.py -> write_pod_file()
prep_02_source_provenance.py -> write_source_provenance()

GPS -> UTC
position (km) -> position_m (m)
velocity (dm/s) -> velocity_m_s (m/s)
time -> time_us
```

```text
{
  file_name,
  ZIP: {orbit.sp3}
}
```

```text
{
  source_files: [
    {
      source_id,
      file_name,
      signature
    },
    ...
  ],
  swarm_a_pod_source_provenance: [
    {
      source_id,
      sp3_frame_label,
      cadence_s,
      time_system
    },
    ...
  ],
  swarm_a_states: [
    {
      time_us,
      position_m: [x_m, y_m, z_m],
      velocity_m_s: [vx_m_s, vy_m_s, vz_m_s],
      source_id
    },
    ...
  ]
}
```

## P1.3 raw state -> orbital element

```text
prep_03_orbital_elements.py -> write_orbital_elements()

ITRF state -> GCRF state
GCRF position + velocity -> instantaneous semi-major axis
```

```text
{
  time_us,
  position_m: [x_m, y_m, z_m],
  velocity_m_s: [
    vx_m_s,
    vy_m_s,
    vz_m_s
  ]
}
```

```text
{
  swarm_a_orbital_elements: [
    {
      time_us,
      semi_major_axis_m,
      rejection_reason
    },
    ...
  ]
}
```

## P1.4 orbital element -> quality / chunk

```text
prep_05_pod_quality.py -> write_pod_quality()

invalid state / orbital element -> is_usable = 0
official maneuver or orbit-raise day -> is_usable = 0
product stream / frame / cadence / time gap change -> new chunk_id
```

```text
{
  swarm_a_states: [
    State,
    ...
  ],
  swarm_a_orbital_elements: [
    OrbitalElement,
    ...
  ],
  swarm_a_pod_source_provenance: [
    SP3Provenance,
    ...
  ]
}
```

```text
{
  swarm_a_pod_quality: [
    {
      time_us,
      is_usable,
      rejection_reason,
      chunk_id
    },
    ...
  ]
}
```

## P1.5 quality -> mean orbit -> 10-minute orbit -> rate

```text
prep_04_mean_orbit.py -> write_mean_orbits()
prep_06_orbit_10min.py -> write_orbit_10min()
prep_07_decay_rate.py -> write_decay_rates()

verified cache reuse is allowed only after exact source/state validation
[end - 600 s, end) inside one chunk_id
pod_count >= 56 and max_pod_gap_s <= 10
for H in [3h, 6h, 12h]: da_dt_H = (a(t) - a(t - H)) / H
```

```text
{
  swarm_a_pod_quality: [
    PODQuality,
    ...
  ],
  swarm_a_orbital_elements: [
    OrbitalElement,
    ...
  ]
}
```

```text
{
  swarm_a_mean_orbital_elements: [
    {time_us, mean_semi_major_axis_m, rejection_reason},
    ...
  ],
  swarm_a_orbit_10min: [
    {
      time_us,
      semi_major_axis_orbit_mean_m,
      pod_count,
      max_pod_gap_s,
      chunk_id
    },
    ...
  ],
  swarm_a_orbit_decay_10min: [
    {
      time_us,
      da_dt_3h_backward_m_day,
      da_dt_6h_backward_m_day,
      da_dt_12h_backward_m_day,
      chunk_id
    },
    ...
  ]
}
```

每個 contiguous run 的前 72 個 10-minute samples 沒有完整 12-hour window，不進 rate table。

## P1.6 decay row + causal features -> analysis row

```text
prep_08_analysis_10min.py -> write_analysis_10min()

weather source time <= orbit time
SYM-H exact，或 right source <= orbit time + 120 seconds
density 不進 Phase 1 analysis table
```

```text
{
  swarm_a_orbit_decay_10min: [
    Decay10Min,
    ...
  ],
  space_weather: [
    WeatherBlock,
    ...
  ],
  geomagnetic: [
    GeomagneticMinute,
    ...
  ]
}
```

```text
{
  swarm_a_analysis_10min: [
    {
      time_us,
      semi_major_axis_orbit_mean_m,
      da_dt_3h_backward_m_day,
      da_dt_6h_backward_m_day,
      da_dt_12h_backward_m_day,
      pod_count,
      max_pod_gap_s,
      chunk_id,
      sym_h_nt,
      ap_now,
      f107_sfu,
      f107a_sfu,
      quality_flags
    },
    ...
  ]
}
```

## P1.7 analysis -> release manifest

```text
prep_09_release_audit.py -> write_release_metadata()

integrity + foreign key
table link + row count + chunk continuity
3h / 6h / 12h rate formula
causal feature source time + missingness
```

P1.7 不新增 orbit、rate 或 feature。它只驗證整條資料鏈：

```text
P1.1--P1.6 output
  -> table link / row count / chunk / rate / source time checks
  -> SQLite integrity + foreign-key check
  -> pass
  -> write p1_7_release_manifest
```

任何一項失敗都不寫新的 manifest，
因此 manifest 是「這份 database 當下可用」的證據。

```text
{
  metadata: {
    p1_7_release_status: "working_audit_pass",
    p1_7_release_manifest: {
      audit_outcome: "pass",
      row_counts: {
        ...
      },
      coverage_utc: {
        start,
        end
      },
      policies: {
        ...
      },
      code_content: {
        digest,
        files
      }
    }
  }
}
```
