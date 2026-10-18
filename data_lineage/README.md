# Phase 1 Data Lineage

## 現行資料庫

唯一正式資料庫是 `data/swarm_a_analysis.sqlite`。

```text
POD + weather + geomagnetic
  -> orbit / rate
  -> analysis
  -> P1.7 audit
```

`working_audit_pass` 表示現行資料庫已通過 audit。cache 只避免重跑相同的
mean-orbit work，不是第二份資料或 release。

## 主線

```text
POD ZIP
  -> swarm_a_states
  -> orbital elements + POD quality + mean orbit
  -> swarm_a_orbit_10min
  -> swarm_a_orbit_decay_10min

weather CSV + geomagnetic CSV
  -> causal fields

orbit decay + causal fields
  -> swarm_a_analysis_10min
  -> metadata.p1_7_release_manifest
```

## 規則

- Raw table immutable；derived writer 只重建自己的 table。
- Mean orbit、10-minute bin 與 rate 不跨 `chunk_id`。
- Weather source time 不晚於 orbit time。
- SYM-H 只允許右端點在 orbit time 後 120 seconds 內。
- Density 不進 Phase 1 core analysis。

## 文件

- [Orbit lineage](orbit_analysis.md): POD 到 final orbit / rate / audit。
- [Space-weather lineage](space_weather.md): Ap、F10.7、F10.7A。
- [Geomagnetic lineage](geomagnetic.md): SYM-H。
