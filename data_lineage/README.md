# Data Lineage

這一頁是資料從下載到目前最後產物的完整答案。它定義每條 source-to-output path 必須可追溯，也記錄目前實際建立的 writer、SQLite table 與 read-only query。研究計畫只引用它，不擁有它。

目前資料庫 evidence 是 frozen release `data/swarm_a_phase1_rebuild.sqlite`；fresh rebuild 與 release audit 已通過，詳見 [final report](../plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md)。

```text
POD ZIP
  -> swarm_a_states -> mean orbit -> orbit 10-minute
  -> 3h/6h/12h same-chunk backward decay -> swarm_a_analysis_10min
space-weather CSV
  -> space_weather -> causal weather fields in swarm_a_analysis_10min
geomagnetic CSV
  -> geomagnetic -> SYM-H fields in swarm_a_analysis_10min
DNSAACC ZIP
  -> swarm_a_density -> swarm_a_density_10min [done]
  -> swarm_a_density_event_baseline_10min [done]
```

## Rules

- Raw SQLite tables immutable。
- 每個 derived writer 只建立自己的 derived table。
- density baseline writer 只能讀 raw `swarm_a_density` 與 `swarm_a_density_10min`，不得回寫任一 input table。
- 後續 density / orbit comparison 只能 read `swarm_a_density_event_baseline_10min` 與 `swarm_a_analysis_10min`，不得回寫任一 table。

## 固定文件格式

每個資料步驟固定寫成三個 block，順序不可改：

```text
## [N] input collection -> output collection

程式檔、function、必要轉換

input example

output example
```

不寫 `action`、`in`、`out` 標籤；block 的位置就是意義。

## 資料結構表示法

SQLite table 是具名的 List；List 內每一列是具名結構。

```text
SQLite
{
  table_name: [RecordType, ...]
}

RecordType
{
  scalar_field,
  vector_field: [x, y, z],
  time_range: [start_time, end_time]
}
```

固定使用：

```text
{}  named record / Dictionary
[]  List, vector, or [start, end] range
```

## Flows

- [POD lineage](pod.md): POD ZIP -> orbit analysis table
- [Space weather lineage](space_weather.md): weather CSV -> causal weather fields
- [Geomagnetic lineage](geomagnetic.md): geomagnetic CSV -> SYM-H fields
- [Density lineage](density.md): DNSAACC ZIP -> 10-minute density -> event baseline SQLite
- [Orbit analysis data products](orbit_analysis.md): actual SQLite table shapes
