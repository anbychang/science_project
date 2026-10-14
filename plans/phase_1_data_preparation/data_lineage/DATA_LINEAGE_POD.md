# POD Data Lineage

範圍：ESA Swarm-A POD ZIP -> raw orbit state -> 瞬時半長軸 -> POD quality。

狀態：P1.4 完成；P1.5 10-minute orbit table 未建立。

## 1. 下載 POD

資料：`ESA POD product = {day, version, ZIP}`。

程式：`down_swarm_pod.py` -> `download_swarm_a_pod_since()`。

動作：同一天只取最高 `version`；檢查 ZIP size。

輸出：`data/swarm_a_pod/*.ZIP`。

Shape：

```text
pod_file = {
  path,
  source_day,
  product_version,
  ZIP: {SP3}
}
```

例：同日有 version `0101`、`0102` -> 只下載 `0102`。

## 2. SP3 -> ITRF state

資料：

```text
sp3_epoch = {
  gps_time,
  P: [x_km, y_km, z_km],
  V: [vx_dm_s, vy_dm_s, vz_dm_s]
}
```

程式：`load_swarm_pod.py` -> `load_swarm_pod()`；`calc_time.py` -> `gps_times_to_utc()`。

動作：`GPS -> UTC`；`km -> m`；`dm/s -> m/s`。

輸出：`orbit_series = [state, ...]`。

Shape：

```text
state = {
  time,
  frame: ITRF,
  position_m: [x, y, z],
  velocity_m_s: [vx, vy, vz]
}
```

例：`P:[6871, 0, 0] km` -> `position_m:[6871000, 0, 0]`。

## 3. state -> raw SQLite

資料：`state`。

程式：`prep_raw_database.py` -> `write_sqlite_database()`；`prep_raw_pod.py` -> `write_pod_folder()` -> `write_pod_file()` -> `pod_row()`。

動作：`time -> time_us`；找 state 所在 3-hour weather block；沒有 weather block 的 row 不寫入。

輸出：`swarm_a_states`；`source_files`。

Shape：

```text
swarm_a_states_row = {
  time_us,
  position_m: [x_m, y_m, z_m],
  velocity_m_s: [vx_m_s, vy_m_s, vz_m_s],
  weather_time_us,
  source_id
}

source_files_row = {
  source_id,
  file_name,
  signature: size:mtime
}
```

例：`14:20:02 UTC` -> `time_us:1715350802000000`；它在 `12:00 UTC` block -> `weather_time_us:1715342400000000`。

## 4. raw state -> 瞬時半長軸

資料：`swarm_a_states_row`。

程式：`prep_derived_orbital_elements.py` -> `write_orbital_elements()`；`calc_coordinates.py` -> `itrf_states_to_gcrf()`；`calc_orbital_response.py` -> `calculate_semi_major_axis()`。

動作：`ITRF -> GCRF`；two-body specific energy -> `semi_major_axis_m`。

輸出：`swarm_a_orbital_elements`。

Shape：

```text
orbital_element_row = {
  time_us,
  semi_major_axis_m,
  rejection_reason
}
```

例：unbound energy -> `{semi_major_axis_m: NULL, rejection_reason: ...}`。

## 5. 半長軸 -> quality / interval

資料：`swarm_a_states_row + orbital_element_row`。

程式：`prep_derived_pod_quality.py` -> `write_pod_quality()`；`quality_row()`；`starts_new_interval()`。

動作：檢查 finite state、有效半長軸、時間遞增；source boundary、rejected row、`gap > native_cadence` -> 新 interval。

輸出：`swarm_a_pod_quality`。

Shape：

```text
pod_quality_row = {
  time_us,
  is_usable,
  rejection_reason,
  interval_id
}
```

例：一個 40 s gap 出現在 10 s native cadence 中 -> gap 後的 row 取得新的 `interval_id`。

## 6. 未建立：P1.5 10-minute orbit data

資料：`pod_quality_row` 中 `{is_usable:1}` 且相同 `interval_id` 的 series。

程式：未建立。

動作：orbit-average / mean-element；short-period treatment；smoothing；不跨 interval。

預計輸出：

```text
swarm_a_orbit_10min_row = {
  time_us,
  semi_major_axis_smooth_m,
  da_dt_smooth_m_s,
  decay_rate_smooth_m_day,
  pod_count,
  max_pod_gap_s,
  interval_id
}
```

限制：不能直接把每 10 s `semi_major_axis_m` 當 decay rate。J2 short-period variation 會造成假訊號。
