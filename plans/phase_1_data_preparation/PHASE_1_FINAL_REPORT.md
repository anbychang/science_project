# Phase 1 最終整理

## 狀態

本文件記錄舊 10 分鐘 P1.7 run；該 SQLite 已退出現行資料集。現行資料是
`data/sqlite/` 內兩份 P1.5.1 checkpoint 與兩份 v2 working copy；
兩份 working copy 的 P1.7 v2 audit 已通過，但尚非已校準的正式 decay release。
mean-orbit cache 與重算結果一致，
只用於避免昂貴的重算；它不形成第二個 database 或 release。
P1.7 metadata 為 `status = working_audit_pass`、`rebuild_status = not_executed`、
`audit_outcome = pass`。archive/cache 只保留復原與比較證據。

## 範圍與排除項目

Phase 1 的交付物是可追溯的 10 分鐘分析 table。

- 包含：POD 轉換、品質/chunk、mean orbit、10-minute bins、decay rate、causal weather/geomagnetic features、SQLite provenance/audit。
- 排除：ML、atmospheric drag propagator、XYZ prediction、DNSAACC density core join、Q4 maneuver rejection rule。
- Density 保留 raw `swarm_a_density`，供後續 Phase 2 獨立研究。

## 舊版 10 分鐘輸出（歷史紀錄）

```text
swarm_a_states                    14,558,400
  -> swarm_a_orbital_elements     14,558,400
  -> swarm_a_pod_quality          13,495,680 usable rows; 9 chunks
  -> swarm_a_mean_orbital_elements
                                  13,495,680 usable rows
  -> swarm_a_orbit_10min             224,928
  -> swarm_a_orbit_decay_10min       224,280
  -> swarm_a_analysis_10min          224,280
```

當時 target 的 mean table 只含 13,495,680 個 usable rows。archive/cache 早於
campaign date-level exclusion 的 rows 只供比較，不作交付依據。

`swarm_a_analysis_10min` UTC coverage：`2022-01-01 12:10` 至 `2026-08-13 00:00`，中間有
frame transition 與兩段公告 orbit-raise campaign 的排除區間。

| chunk | rows | UTC coverage |
| ---: | ---: | --- |
| 1 | 17,496 | 2022-01-01 12:10 to 2022-05-03 00:00 |
| 2 | 20,376 | 2022-07-09 12:10 to 2022-11-28 00:00 |
| 3 | 21,384 | 2022-11-28 12:10 to 2023-04-26 00:00 |
| 4 | 87,192 | 2023-06-08 12:10 to 2025-02-03 00:00 |
| 5 | 49,320 | 2025-02-03 12:10 to 2026-01-12 00:00 |
| 6 | 30,600 | 2026-01-12 12:10 to 2026-08-13 00:00 |

## Raw-to-derived pipeline

```text
POD ZIP
  -> source_files + swarm_a_states {GPS -> UTC; km -> m; dm/s -> m/s}
  -> swarm_a_orbital_elements {ITRF -> GCRF; two-body osculating a}
  -> swarm_a_pod_quality {finite/bound/cadence/gap; chunk_id}
  -> swarm_a_mean_orbital_elements {Orekit Brouwer-Lyddane mean a}
  -> swarm_a_orbit_10min {UTC [end-600 s, end); arithmetic mean}
  -> swarm_a_orbit_decay_10min {chunk-local 3h/6h/12h backward differences}
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
for H in {3h, 6h, 12h}: (a(t) - a(t - H)) / H * 86400
each continuous run removes its first 72 10-minute rows

causal features
Ap / F10.7 / F10.7A source_time <= orbit_time
SYM-H exact or <= 2-minute bounded interpolation
```

Q4 residual candidate is audit-only. ESA-published orbit-raise campaigns are separately marked
`planned_orbit_raise_campaign` and split chunks.

## 當時 10 分鐘資料庫品質證據

- SQLite `integrity_check = ok`.
- Foreign-key check has no violations.
- Final decay/analysis keys and `chunk_id` agree one-to-one.
- `swarm_a_orbit_10min` has `pod_count = 58..60`; `max_pod_gap_s = 10 s`.
- Required derived fields have no NULL, NaN, or infinity. Optional feature groups must be wholly present or wholly NULL and agree with `quality_flags`.
- `quality_flags` has 226,367 `ok` rows and one `missing_sym_h` row; it is retained without future-value filling.
- Ap, F10.7, F10.7A and SYM-H causal-source audit found no prohibited future reference.
- P1.3 與 P1.5 以 exact source/state match 驗證 cache 後直接重用；本次不重算 mean orbit。

上述條件均在當時 target 的舊 P1.7 audit 驗證。所有 missingness、future-reference、
chunk continuity、foreign-key 與 integrity failure count 都是 0。

## 未校準的 decay-rate 異常

`da_dt_12h_backward_m_day` 全部是 finite，但這不等於物理品質已校準。

```text
range: -5,312.47 .. +712.99 m/day
abs(rate) > 10 m/day:  217,679 rows
abs(rate) > 100 m/day: 141,094 rows
```

Q4 目前是 audit-only；沒有 external maneuver labels 或已校準 rejection rule，這些 rows 必須保留。
因此 `swarm_a_analysis_10min` 是可追溯的 Phase 1 working output，不可直接當作已清除 maneuver / source / method anomaly 的 geomagnetic-decay inference dataset。

## Provenance 與可重建性

P1.7 audit 在 `metadata` 記錄 raw signature aggregate、coverage、Git revision、row counts、missingness、frame policy、algorithms、rebuild commands 與 implementation SHA-256 digest。`rebuild_status` 只記錄再現方式，不代表另一份資料產品。

`source_files` is immutable raw history. Parsed SP3 frame, cadence, coverage, epoch count, and time system live in derived `swarm_a_pod_source_provenance`, keyed by `source_id`.

Raw tables are immutable. Derived calculations write separate tables. 現行 SQLite 不提交至 Git；archive/cache 也不是正式輸出。

## Cache-reuse 證據

已執行：

   ```powershell
   python -m satellite_orbit.phase1.prep_phase1_rebuild CACHE_DATABASE RECOVERY_DATABASE
   ```

P1.3 與 mean-orbit 在 source/state exact-match 驗證後可重用 cache；其值不會形成另一個
research version。10-minute orbit、3/6/12h decay、P1.6 causal analysis 與 P1.7 audit 的
本報告的 P1.7 結果只保留歷史紀錄，不是現行資料產品。

## Phase 2 handoff

上述是舊 10 分鐘分支的 Phase 2 handoff；現行 Phase 2 來源應以
[PHASE_1_EXECUTION_PLAN.md](PHASE_1_EXECUTION_PLAN.md) 與 Phase 2 計畫重新對接，
不得把已退出主線的 `swarm_a_analysis_10min` 當作現行輸入。

- Select storm windows and define the scientific comparison.
- Decide whether density becomes a separate aligned product; do not silently join it into the core table.
- Calibrate or label the extreme `da_dt_12h_backward_m_day` rows before using it for scientific inference.
- If maneuver labels become available, define a new Q4 version and rebuild chunks; do not retroactively interpret audit residuals as rejection evidence.

## 文件地圖

| 文件 | 用途 |
| --- | --- |
| [PLAN.md](PLAN.md) | Normative rules and contracts |
| [P1.4 quality control](P1.4_QUALITY_CONTROL.md) | Q1--Q4 evidence and policy |
| [P1.5 resample and decay](P1.5_RESAMPLE_AND_DECAY.md) | Method gates and decay design |
| [P1.6 schema](P1.6_ANALYSIS_SCHEMA.md) | Final feature columns and causal rules |
| [SQLite lineage](../../data_lineage/orbit_analysis.md) | Current table shapes |
| [Data lineage index](../../data_lineage/README.md) | Cross-phase source-to-table documents |
| [TIMELOG.md](../../TIMELOG.md) | Dated historical evidence |
| [P1.4 to P1.7 plan](P1.4_TO_P1.7_EXECUTION_PLAN.md) | Superseded historical execution plan |
