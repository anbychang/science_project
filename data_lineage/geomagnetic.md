# Geomagnetic Data Lineage

```text
SYM-H CSV + AE CSV -> minute observations -> SQLite
```

## [1] local CSV -> observations

```text
load_geomagnetic.py -> load_geomagnetic_file()

skip comment rows
skip 99999 fill values
```

```text
sym_h_202405.csv
[
  ["2024-05-10T14:20:00Z", -42, 1],
  ...
]

ae_202405.csv
[
  ["2024-05-10T14:20:00Z", 527, 1],
  ...
]
```

```text
[
  {time: 2024-05-10 14:20:00 UTC, value: -42 nT, version: 1},
  ...
]
```

## [2] SYM-H list + AE list -> GeomagneticRecord list

```text
prep_raw_geomagnetic.py -> write_sym_h()
prep_raw_geomagnetic.py -> write_ae()
time_to_us() -> time_us
```

```text
[
  {time: 2024-05-10 14:20:00 UTC, value: -42 nT, version: 1},
  ...
]

[
  {time: 2024-05-10 14:20:00 UTC, value: 527 nT, version: 1},
  ...
]
```

```text
[
  {
    time: 2024-05-10 14:20:00 UTC,
    sym_h: -42 nT,
    ae: 527 nT,
    versions: {sym_h: 1, ae: 1}
  },
  ...
]
```

## [3] [GeomagneticRecord, ...] -> SQLite

```text
write_sym_h() + write_ae()
```

```text
[
  {time: 2024-05-10 14:20:00 UTC, sym_h: -42 nT, ae: 527 nT},
  ...
]
```

```text
SQLite
{
  geomagnetic:
  [
    {
      time: 2024-05-10 14:20:00 UTC,
      sym_h: -42 nT,
      ae: 527 nT,
      versions: {sym_h: 1, ae: 1}
    },
    ...
  ]
}
```

## [4] GeomagneticRecord -> analysis feature fields

```text
prep_08_analysis_10min.py

exact minute -> direct
otherwise bounded linear interpolation
left/right total gap <= 2 min
```

```text
{
  time: 2024-05-10 14:20:00 UTC,
  sym_h: -42 nT,
  ae: 527 nT
}
```

```text
{
  orbit_time: 2024-05-10 14:30:00 UTC,
  sym_h_nt: -42 nT,
  sym_h_left_time: 2024-05-10 14:30:00 UTC,
  sym_h_right_time: 2024-05-10 14:30:00 UTC
}
```

AE remains raw-only in the orbit analysis table. Frozen release has the SYM-H join and passed the release audit; see [final report](../plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md).
