# Density Data Lineage

範圍：本機 Swarm DNSAACC density ZIP -> raw `swarm_a_density`。

狀態：raw table 完成；沒有 downloader；不 join P1.6。

## 1. 放入本機

資料：Swarm DNSAACC density product ZIP。

程式：無 downloader。

動作：人工放入資料夾。

輸出：`data/swarm_density_acc/*.ZIP`。

## 2. CDF -> density observation

資料：ZIP 內的 CDF。

程式：`load_swarm_density.py` -> `load_swarm_density()`。

動作：讀 `time`、`density`、`altitude`、`latitude`、`longitude`、`local_solar_time`；濾除 `density <= 0` 與 fill value。

輸出：`density_observations = [density_row, ...]`。

Shape：

```text
density_row = {
  time,
  density_kg_m3,
  altitude_m,
  latitude_deg,
  longitude_deg,
  local_solar_time_h
}
```

例：`density = 1e31` -> fill value -> 不產生 `density_row`。

## 3. density observation -> raw SQLite

資料：`density_observations`。

程式：`prep_raw_database.py` -> `write_sqlite_database()`；`prep_raw_density.py` -> `write_density_folder()`。

動作：`time -> time_us`；同一 `time_us` 使用 `INSERT OR IGNORE`；已有相同 `source_file_name` 的檔案跳過。

輸出：`swarm_a_density`。

Shape：

```text
swarm_a_density_row = {
  time_us,
  density_kg_m3,
  altitude_m,
  latitude_deg,
  longitude_deg,
  local_solar_time_h,
  source_file_name
}
```

## 4. 停止點

資料：`swarm_a_density_row`。

程式：沒有 downstream caller。

動作：不對齊 `swarm_a_orbit_10min`；不寫入 `swarm_a_analysis_10min`。

輸出：raw density table only。

原因：density 的研究角色、時間規則、是否屬於 target / control / validation 尚未定義。
