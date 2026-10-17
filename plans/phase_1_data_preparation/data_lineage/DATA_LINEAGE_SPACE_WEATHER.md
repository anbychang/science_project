# Space Weather Data Lineage

```text
SW-All.csv -> daily values -> 3-hour WeatherRecord -> SQLite
```

## [1] local CSV -> daily weather rows

```text
load_space_weather.py -> _load_weather_file()
prep_raw_weather.py -> weather_days()

check AP1..AP8
```

```text
{
  DATE: 2024-05-10,
  F10.7_OBS: 150.2,
  F10.7_OBS_CENTER81: 145.8,
  AP_AVG: 8,
  AP1: 6,
  ...,
  AP8: 12
}
```

```text
[
  {
    day: 2024-05-10 UTC,
    f107: 150.2 sfu,
    f107a: 145.8 sfu,
    ap_slots: [6, 8, 10, 12, 9, 7, 5, 12]
  },
  ...
]
```

## [2] one 3-hour time -> one WeatherRecord

```text
load_space_weather.py -> load_space_weather()

previous-day F10.7
previous-day causal F10.7A
current / previous Ap slots
```

```text
{time: 2024-05-10 12:00:00 UTC}
```

```text
{
  time: 2024-05-10 12:00:00 UTC,
  f107: 149.4 sfu,
  f107a: 145.8 sfu,
  ap: [8, 10, 8, 6, 5, 7.5, 6.1],
  f107_data_type: "OBS"
}
```

## [3] [WeatherRecord, ...] -> SQLite

```text
prep_raw_weather.py -> write_space_weather()
time_to_us() -> time_us
```

```text
[
  {time: 2024-05-10 12:00:00 UTC, f107: 149.4 sfu, f107a: 145.8 sfu, ap: [...]},
  ...
]
```

```text
SQLite
{
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
}
```

## [4] WeatherRecord -> analysis feature fields

```text
prep_derived_analysis_10min.py

Ap -> target official 3-hour block
F10.7 / F10.7A -> previous-day source_time
source_time <= orbit_time
```

```text
{
  time: 2024-05-10 12:00:00 UTC,
  f107: 149.4 sfu,
  f107a: 145.8 sfu,
  ap: [8, 10, 8, 6, 5, 7.5, 6.1]
}
```

```text
{
  orbit_time: 2024-05-10 14:30:00 UTC,
  ap_now: 8,
  ap_source_time: 2024-05-10 12:00:00 UTC,
  f107_sfu: 149.4 sfu,
  f107_source_time: 2024-05-09 00:00:00 UTC,
  f107a_sfu: 145.8 sfu,
  f107a_source_time: 2024-05-09 00:00:00 UTC
}
```

Current database has this causal join. weather v2/v3 fresh rebuild is pending; see `../PHASE_1_FINAL_REPORT.md`.
