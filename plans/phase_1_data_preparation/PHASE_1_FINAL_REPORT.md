# Phase 1 最終整理

## 狀態

現有 `data/swarm_a_data.sqlite` 已建立並通過 P1.7 current-database audit。

WARNING: weather preparation v2/v3 修正後，尚未從 raw files fresh rebuild 再重跑 P1.3--P1.7。Phase 1 的資料處理設計與 working output 已完成；frozen / fully reproducible release 尚未完成。

## 範圍與排除項目

Phase 1 的交付物是可追溯的 10 分鐘分析 table。

- 包含：POD 轉換、品質/chunk、mean orbit、10-minute bins、decay rate、causal weather/geomagnetic features、SQLite provenance/audit。
- 排除：ML、atmospheric drag propagator、XYZ prediction、DNSAACC density core join、Q4 maneuver rejection rule。
- Density 保留 raw `swarm_a_density`，供後續 Phase 2 獨立研究。

## Current canonical output

```text
swarm_a_states                    14,558,400
  -> swarm_a_orbital_elements     14,558,400
  -> swarm_a_pod_quality          14,558,400 usable rows; 4 chunks
  -> swarm_a_mean_orbital_elements
                                  14,558,400
  -> swarm_a_orbit_10min             242,640
  -> swarm_a_orbit_decay_10min       242,352
  -> swarm_a_analysis_10min          242,352
```

`swarm_a_analysis_10min` UTC coverage：`2022-01-01 06:10` 至 `2026-08-12 18:00`。

| chunk | rows | UTC coverage |
| ---: | ---: | --- |
| 1 | 47,592 | 2022-01-01 06:10 to 2022-11-27 18:00 |
| 2 | 114,840 | 2022-11-28 06:10 to 2025-02-02 18:00 |
| 3 | 49,320 | 2025-02-03 06:10 to 2026-01-11 18:00 |
| 4 | 30,600 | 2026-01-12 06:10 to 2026-08-12 18:00 |

## Raw-to-derived pipeline

```text
POD ZIP
  -> source_files + swarm_a_states {GPS -> UTC; km -> m; dm/s -> m/s}
  -> swarm_a_orbital_elements {ITRF -> GCRF; two-body osculating a}
  -> swarm_a_pod_quality {finite/bound/cadence/gap; chunk_id}
  -> swarm_a_mean_orbital_elements {Orekit Brouwer-Lyddane mean a}
  -> swarm_a_orbit_10min {UTC [end-600 s, end); arithmetic mean}
  -> swarm_a_orbit_decay_10min {chunk-local centered Savitzky-Golay}
  -> swarm_a_analysis_10min {causal SYM-H, Ap, F10.7, F10.7A}
```

`space_weather` and `geomagnetic` are raw inputs to the final join. `swarm_a_density` is intentionally outside it.

## 固定契約

```text
chunk
same {product stream, SP3 frame, cadence, continuous time}
anything different or unknown -> new chunk

10-minute bin
[end - 600 s, end)
same chunk only
pod_count >= 56
max_pod_gap_s = 10

decay
73 samples, order 2, centered Savitzky-Golay
each continuous run removes 36 rows at each edge

causal features
Ap / F10.7 / F10.7A source_time <= orbit_time
SYM-H exact or <= 2-minute bounded interpolation
```

Q4 is audit-only: residuals are evidence, not an acceptance threshold. Q4 does not reject rows and does not split chunks.

## Current-database 品質證據

- SQLite `integrity_check = ok`.
- Foreign-key check has no violations.
- Final decay/analysis keys and `chunk_id` agree one-to-one.
- `swarm_a_orbit_10min` has `pod_count = 58..60`; `max_pod_gap_s = 10 s`.
- Final tables have no NULL, NaN, or infinity in required derived fields.
- All 242,352 final rows have `quality_flags = ok`.
- Ap, F10.7, F10.7A and SYM-H causal-source audit found no prohibited future reference.
- P1.5 method gate: Brouwer-Lyddane reduced representative raw short-period amplitude by 99.33--99.45%; direct raw smoothing was rejected.

這些證據只證明 current database，不能證明 weather v2/v3 後的 fresh rebuild。

## 未校準的 decay-rate 異常

`decay_rate_smooth_m_day` 全部是 finite，但這不等於物理品質已校準。

```text
range: -14,436.50 .. +239.69 m/day
abs(rate) > 10 m/day:  42,099 rows
abs(rate) > 100 m/day: 20,307 rows
```

Q4 目前是 audit-only；沒有 external maneuver labels 或已校準 rejection rule，這些 rows 必須保留。
因此 `swarm_a_analysis_10min` 是可追溯的 Phase 1 working output，不可直接當作已清除 maneuver / source / method anomaly 的 geomagnetic-decay inference dataset。

## Provenance 與可重建性

`metadata` records raw signature aggregate, coverage, Git revision, row counts, missingness, frame policy, algorithms, rebuild commands, and a SHA-256 content digest of the Phase 1 implementation files. The current status is `working_audit_pass`; it is not a frozen release.

`source_files` is immutable raw history. Parsed SP3 frame, cadence, coverage, epoch count, and time system live in derived `swarm_a_pod_source_provenance`, keyed by `source_id`.

Raw tables are immutable. Derived calculations write separate tables. The working SQLite database is intentionally not committed to Git.

## 必要的 fresh-rebuild gate

1. Create a new SQLite target from local raw files using weather preparation v3:

   ```powershell
   python -m satellite_orbit.phase1.prep_phase1_rebuild data/swarm_a_phase1_rebuild.sqlite
   ```

   The target path must not exist; the command refuses to overwrite the working database.
2. Rebuild raw tables, P1.3/P1.4, mean-orbit, 10-minute orbit/decay, and P1.6 causal analysis in order.
3. Run the P1.7 audit again: counts, UTC coverage, chunks, finite values, foreign keys, source-time causality, metadata, and raw signatures.
4. Compare the rebuild outputs with the canonical counts and document any intentional difference before calling the result frozen.

Until this passes, do not claim that the current output has a verified clean rebuild.

## Phase 2 handoff

Phase 2 starts from `swarm_a_analysis_10min`, not raw 10-second osculating semi-major axis.

- Select storm windows and define the scientific comparison.
- Decide whether density becomes a separate aligned product; do not silently join it into the core table.
- Calibrate or label the extreme `decay_rate_smooth_m_day` rows before using it for scientific inference.
- If maneuver labels become available, define a new Q4 version and rebuild chunks; do not retroactively interpret audit residuals as rejection evidence.

## 文件地圖

| 文件 | 用途 |
| --- | --- |
| [PLAN.md](PLAN.md) | Normative rules and contracts |
| [P1.4 quality control](P1.4_QUALITY_CONTROL.md) | Q1--Q4 evidence and policy |
| [P1.5 resample and decay](P1.5_RESAMPLE_AND_DECAY.md) | Method gates and decay design |
| [P1.6 schema](P1.6_ANALYSIS_SCHEMA.md) | Final feature columns and causal rules |
| [SQLite lineage](data_lineage/DATA_LINEAGE_SQLITE.md) | Current table shapes |
| [Data lineage index](data_lineage/README.md) | Source-to-table documents |
| [TIMELOG.md](../../TIMELOG.md) | Dated historical evidence |
| [P1.4 to P1.7 plan](P1.4_TO_P1.7_EXECUTION_PLAN.md) | Superseded historical execution plan |
