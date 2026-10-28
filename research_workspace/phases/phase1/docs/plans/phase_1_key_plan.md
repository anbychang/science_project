# Phase 1 重點計畫 [historical summary]

此檔保留 2026-10-17 之前的執行重點，不再是 current status。

現行結果與狀態：[phase_1_execution_plan.md](phase_1_execution_plan.md)。
舊 10 分鐘 run 見 [phase_1_final_report.md](../../reports/phase_1_final_report.md)。

> NOTE: 以下 `Now` / `Next` 是歷史計畫，不代表現況。

## 終點

```text
swarm_a_analysis_10min
{
  time_us,
  mean / smooth semi_major_axis,
  decay_rate,
  chunk_id + provenance,
  SYM-H, Ap, F10.7, F10.7A,
  feature source times,
  quality_flags
}
```

## Done

```text
raw SQLite
  -> osculating semi-major axis
  -> basic QC + provisional intervals
  -> SP3 provenance + Q3 unavailable policy
  -> Brouwer-Lyddane method validation
  -> Q4 residual audit + synthetic jump sensitivity
```

## Now

```text
1. decide P1.4 Q4 policy
   {preserve rows / obtain maneuver labels}

2. rebuild provisional intervals into final chunks

3. resume P1.5 full mean batch
   {2,021,760 / 14,558,400 complete}
```

## Next

```text
full mean table
  -> chunk-safe 10-minute orbit table {pod_count >= 56}
  -> smoothing + decay rate
  -> causal weather / geomagnetic join
  -> metadata + clean rebuild + release
```

## Do not do

```text
no direct smoothing of osculating a
any provenance/frame/cadence/gap change -> new chunk
no cross-chunk fit
no future weather value
no raw-table mutation
no ML / drag propagator / density core join
```

完整工作、輸入、輸出、驗收與 blocker：
[phase_1_execution_plan.md](phase_1_execution_plan.md)。
