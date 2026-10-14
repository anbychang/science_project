# Space Weather Data Lineage

範圍：CelesTrak `SW-All.csv` -> 3-hour `space_weather` rows -> P1.6 solar / Ap features。

狀態：raw table 完成；P1.6 join 未建立。

## 1. 下載 daily CSV

資料：CelesTrak `SW-All.csv`。

程式：`down_space_weather.py` -> `download_space_weather()`。

動作：下載 daily CSV；已有本機檔時直接返回。

輸出：`data/space_weather/SW-All.csv`。

Shape：

```text
weather_day = {
  day,
  f107_obs,
  f107_center81,
  f107_last81,
  ap_daily,
  ap_slots: [ap_00, ap_03, ap_06, ap_09, ap_12, ap_15, ap_18, ap_21],
  f107_data_type
}
```

例：一個 `weather_day` 會展開為 `00:00` 到 `21:00 UTC` 的 8 個 rows。

## 2. daily row -> 3-hour raw row

資料：`weather_day`；前一日 `weather_day`；過去 57 小時 Ap slots。

程式：`prep_raw_database.py` -> `write_sqlite_database()`；`prep_raw_weather.py` -> `write_space_weather()` -> `weather_row()`；`load_space_weather.py` -> `load_space_weather()`。

動作：daily row 展開為 8 個 official 3-hour blocks；計算 Ap history；前日 `f107_obs` -> `f107_sfu`；保存 centered / trailing 81-day values。

輸出：`space_weather`。

Shape：

```text
space_weather_row = {
  time_us,
  f107_sfu,
  f107a_sfu,
  f107a_last81_sfu,
  ap_values: [
    daily,
    now,
    minus_3h,
    minus_6h,
    minus_9h,
    avg_12_to_33h,
    avg_36_to_57h
  ],
  f107_data_type
}
```

例：target `2024-05-10 14:20 UTC` -> 使用 `12:00 UTC` 的 `space_weather_row`；它的 `f107_sfu` 來自 `2024-05-09`。

## 3. 未建立：P1.6 solar / Ap feature

資料：`swarm_a_orbit_10min_row + space_weather_row`。

程式：未建立；規則在 `P1.6_ANALYSIS_SCHEMA.md`。

動作：Ap 用 target 所在 official 3-hour block；F10.7 與 F10.7A 都用前一日 source；analysis F10.7A 用 `f107a_last81_sfu`，不用 centered `f107a_sfu`。

預計輸出：

```text
solar_ap_feature = {
  ap: {
    ap_now,
    ap_source_time_us
  },
  solar: {
    f107_sfu,
    f107_source_time_us,
    f107a_sfu,
    f107a_source_time_us,
    f107_data_type
  }
}
```

缺資料：weather feature -> `NULL`；orbit row 保留。
