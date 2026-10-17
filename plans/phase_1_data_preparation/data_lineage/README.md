# Phase 1 Data Lineage

五份文件追 raw sources 與 SQLite final shape。資料庫所示流程是 current working release；weather v2/v3 fresh rebuild 尚待完成，詳見 [Phase 1 Final Report](../PHASE_1_FINAL_REPORT.md)。

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

例如：

```text
source_files: [{...}, ...]
swarm_a_states: [{...}, ...]
space_weather: [{...}, ...]
geomagnetic: [{...}, ...]
swarm_a_density: [{...}, ...]
```

- [POD data lineage](DATA_LINEAGE_POD.md)
- [Space weather data lineage](DATA_LINEAGE_SPACE_WEATHER.md)
- [Geomagnetic data lineage](DATA_LINEAGE_GEOMAGNETIC.md)
- [Density data lineage](DATA_LINEAGE_DENSITY.md)
- [SQLite final structure](DATA_LINEAGE_SQLITE.md)

固定格式記在 [Phase 1 計畫](../PLAN.md#資料血緣文件格式)。
