# Phase 1 Space-Weather Lineage

```text
SW-All.csv
  -> space_weather
  -> Ap / F10.7 / F10.7A in swarm_a_analysis_10min
```

## Raw table

```text
prep_raw_weather.py -> write_space_weather()

{
  space_weather: [
    {
      time_us,
      f107_sfu,
      f107a_sfu,
      ap_now,
      ap_3h,
      ap_6h,
      ap_9h,
      f107_data_type
    },
    ...
  ]
}
```

一個完整 UTC day 產生八個 3-hour rows；缺少任一 Ap slot 就拒絕該 day。

## Analysis fields

```text
prep_08_analysis_10min.py -> align_space_weather()

{
  ap_now,
  ap_source_time_us,
  f107_sfu,
  f107_source_time_us,
  f107a_sfu,
  f107a_source_time_us,
  f107_data_type
}
```

每個 source time 必須是 `<= orbit time`。
