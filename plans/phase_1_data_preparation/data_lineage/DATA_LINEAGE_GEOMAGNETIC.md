# Geomagnetic Data Lineage

範圍：WDC Kyoto SYM-H / AE -> minute `geomagnetic` rows -> P1.6 SYM-H feature。

狀態：raw table 完成；P1.6 join 未建立；AE 不進 final schema。

## 1. 下載 minute data

資料：WDC Kyoto HAPI：`min_asysym` (SYM-H)；`min_ae` (AE)。

程式：`down_geomagnetic.py` -> `download_geomagnetic()`。

動作：每 request 最多 180 days；確認 CSV 最後一筆覆蓋 requested end date；失敗 `.download` 不保留。

輸出：

```text
data/geomagnetic/
  sym_h_<first_day>_<last_day>.csv
  ae_<first_day>_<last_day>.csv
```

## 2. CSV -> minute observation

資料：`csv_row = {iso_time, value_nt, version}`。

程式：`load_geomagnetic.py` -> `load_geomagnetic_file()`。

動作：跳過 header、空列、`99999`；`ISO UTC -> datetime`。

輸出：`geomagnetic_observations = [{time, value_nt, version}, ...]`。

例：`99999` -> 不產生 observation。

## 3. minute observation -> raw SQLite

資料：`geomagnetic_observations`。

程式：`prep_raw_database.py` -> `write_sqlite_database()`；`prep_raw_geomagnetic.py` -> `write_sym_h()` / `write_ae()`。

動作：`time -> time_us`；SYM-H / AE 可補進同一 timestamp；既有同類 index 不覆寫。

輸出：`geomagnetic`。

Shape：

```text
geomagnetic_row = {
  time_us,
  sym_h_nt,
  ae_nt,
  sym_h_version,
  ae_version
}
```

## 4. 未建立：P1.6 SYM-H feature

資料：`swarm_a_orbit_10min_row + geomagnetic_row`。

程式：未建立；規則在 `P1.6_ANALYSIS_SCHEMA.md`。

動作：exact match -> direct value；左右 observation 都存在且總 gap `<= 2 min` -> linear interpolation；其他情況 -> missing。

預計輸出：

```text
sym_h_feature = {
  sym_h_nt,
  sym_h_left_time_us,
  sym_h_right_time_us
}
```

例：target `14:20`；source `14:19`、`14:21` -> interpolation。只有 `14:21` -> `{sym_h_nt: NULL}`。

AE：保留在 `geomagnetic.ae_nt`；不進 `swarm_a_analysis_10min`。
