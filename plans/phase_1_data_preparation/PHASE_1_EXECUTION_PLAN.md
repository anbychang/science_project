# Phase 1 完整執行計畫

## 目標

由四種 raw data 建立可重建的 `swarm_a_analysis_10min`：每 10 分鐘一列，
可追溯 POD、品質區間、space-weather source time 與 geomagnetic source time。

```text
raw POD / weather / geomagnetic
  -> raw SQLite {immutable}
  -> quality + mean orbit
  -> 10-minute orbit + decay rate
  -> causal feature join
  -> reproducible release
```

不做：ML、drag propagator、把 DNSAACC density 強行放入 core table。

## 已固定規則

```text
same chunk
{
  same product stream {not merely same ZIP/source_id},
  same SP3 frame,
  same cadence,
  no time gap
}

any uncertainty or change
  -> close chunk
  -> start new chunk
```

`chunk_id` 是唯一必要的 chunk metadata。不記 `chunk_reason`；多切可以接受，少切不可以。
mean orbit、10-minute bin、smoothing、derivative 都不可跨 `chunk_id`。

```text
10-minute POD bin
{
  expected: 60 observations,
  accepted: pod_count >= 56,
  excluded: pod_count <= 55
}
```

## 現在資料狀態

| stage | 狀態 | 證據 / 輸出 |
| --- | --- | --- |
| P1.1/P1.2 raw intake | [done] | 1,685 POD ZIP；14,558,400 `swarm_a_states` |
| P1.3 osculating element | [done] | 14,558,400 `swarm_a_orbital_elements` |
| P1.4-A/B chunk rebuild | [done] | 14,558,400 quality rows；4 final chunks |
| P1.4-C provenance + Q3 | [done] | `source_files` SP3 metadata；`quality_source: unavailable` |
| P1.4-D Q4 residual audit | [done: audit-only] | synthetic jump sensitivity；不設 rejection threshold |
| P1.5-A mean-orbit method | [done] | Brouwer-Lyddane；3 intervals suppression 99.33--99.45% |
| P1.5 full mean batch | [done] | 14,558,400 mean rows；missing 0；rejection 0；SQLite integrity `ok` |
| P1.5-B 10-minute orbit | [done] | 242,640 `swarm_a_orbit_10min`；4 chunks；`pod_count = 58..60` |
| P1.5-C/D smoothing / derivative | [done] | centered Savitzky-Golay；每個 run 兩端各排除 36 列 |
| P1.6 causal join | [done] | 242,352 `swarm_a_analysis_10min`；所有 final feature 均有來源時間 |
| P1.7 current-database audit | [done] | integrity / foreign keys / counts / finite values / causal-source audit 通過 |
| P1.7 fresh rebuild | [pending] | weather preparation v2/v3 修正後，尚未由 raw files 重建並重跑 audit |

## 依賴

```text
P1.4 final policy
  + P1.5 full mean batch
      -> P1.5-B {10-minute orbit}
      -> P1.5-C/D {smooth, derivative, release gate}
      -> P1.6-A tests + P1.6-B {causal join}
      -> P1.7 {metadata, rebuild, export}
```

## 已鎖定決策

```text
P1.4 chunk
same {product stream, SP3 frame, cadence, continuous time}
  -> same chunk
anything different or unknown
  -> new chunk

Q4 maneuver
audit-only
  -> preserve rows
  -> no residual rejection threshold

P1.5 10-minute bin
[time - 10 min, time)
time = bin end
mean_a = arithmetic mean
pod_count >= 56
max_pod_gap_s = 10
one chunk only

P1.6
weather / geomagnetic source time <= orbit time
density stays outside core analysis table
```

`pod_count = 56..59` 只允許出現在 chunk 邊緣；chunk 中間應為 60。

## Full mean batch 完成後的收尾順序

```text
[1] mean table audit
    row_count == usable State count
    missing == 0
    finite mean_a
    rejection reason
    per-source completeness

[2] remove temporary parallel runner
    delete ProcessPool / --workers / worker tests
    restore single source -> calculate -> SQLite write path

[3] P1.5-B
    swarm_a_orbit_10min
    tests: full bin / 56-row edge bin / gap / chunk boundary

[4] P1.5-C/D
    chunk-local smoothing + derivative + decay rate
    tests: constant / linear decline / gap

[5] P1.6
    swarm_a_analysis_10min
    weather + geomagnetic causal join

[6] P1.7
    integrity / counts / UTC coverage / missingness / metadata / rebuild check

[7] final records
    TIMELOG + plan status + data lineage + test evidence
```

P1.1--P1.4 不重新寫 raw data；只在 P1.7 做 final audit。

## Current database evidence

```text
14,558,400 usable POD
  -> 14,558,400 mean-orbit rows
  -> 242,640 UTC 10-minute orbit rows
  -> centered Savitzky-Golay per contiguous chunk/run
  -> 242,352 final analysis rows
```

- `swarm_a_orbit_10min`：4 個 `chunk_id`；`pod_count = 58..60`；`max_pod_gap_s = 10`；演算法 `utc_10min_mean_brouwer_lyddane_v1`。
- bin contract：`[end - 600 s, end)`，end 為 `time_us`；同一 `chunk_id`；至少 56 筆。
- smooth / derivative：`centered_savgol_mean_orbit_v1`，window 73 個 10-minute samples，polynomial order 2；連續 run 兩端各排除 36 列，不跨 chunk 或 600 s gap。
- `swarm_a_analysis_10min`：242,352 列，4 個 `chunk_id`，演算法 `causal_space_weather_geomagnetic_v1`；`quality_flags = ok` 全數成立。
- causal join：Ap、F10.7、F10.7A source time 不晚於 orbit time；SYM-H 只允許有完整左右端點的 <= 2 分鐘內插。P1.7 audit 無 future reference。
- DNSAACC density 保留在 raw `swarm_a_density`，未放入 core analysis table。
- P1.7 current-database audit：SQLite `integrity_check = ok`、foreign-key check 空、final table 無 NULL/NaN/inf、無跨 chunk/gap。
- WARNING: weather preparation v2/v3 修正後，尚未在 fresh database 重建 raw -> P1.6 並重跑此 audit；不可把目前結果稱為 frozen release。

## 工作包 0：固定 P1.4 final policy

目的：明確定義哪些 POD 可以進 P1.5，不讓未校準規則暗中刪資料。

已知：

```text
Q1 / Q5: implemented
Q2: provenance/frame/cadence/gap change -> new chunk
Q3: quality_source = unavailable
Q4: residual calculation verified; no defensible threshold yet
```

決定：Q4 為 audit-only；保留全部 rows，不設 rejection threshold。缺少 external maneuver label
前，不得用統計 residual 門檻排除資料。

完成：已將 derived `interval_id` 改成 final `chunk_id` semantics。每日 ZIP 不是自動
boundary；只有 provenance/frame/cadence/gap 有任何不一致時才切 chunk。

輸出：P1.4 quality report，包含 Q1--Q5 policy、chunk list、rejection count、
frame transition report。

驗收：每個規則都有 `{implemented | unavailable | explicitly deferred}`；每個 chunk 都符合
已固定規則；不留下隱含 boundary。

限制：不得自行把 `median + k * MAD` 當正式 threshold。

## 工作包 1：完成 P1.5 mean-orbit batch

目的：對每筆 usable POD 建立可重建的 Brouwer-Lyddane mean semi-major axis。

輸入：`swarm_a_states` + `swarm_a_pod_quality {is_usable = 1}`。

工作：

1. 從既有 checkpoint 執行 `prep_derived_mean_orbit`；不可同時有第二個 SQLite writer。
2. 本次 exceptional full rebuild 可暫時用 3 個 read-only calculator + 1 個 writer；完成後刪除平行 code。
3. 驗證 count、missing、rejection、首尾 UTC、每 source completeness。

輸出：`swarm_a_mean_orbital_elements {time_us, mean_semi_major_axis_m, rejection_reason}`。

驗收：14,558,400 usable POD 都有一列；rejection 有明確原因；不改 raw table。

完成證據：14,558,400 usable POD 都有 mean row；每 source completeness 差異 0；
mean semi-major axis 均為有限正值，範圍 6,787,017.63--6,860,042.07 m；rejection 0；
SQLite `integrity_check = ok`。一次性 3-worker runner 已移除，程式回復單線 source -> calculate -> SQLite write。

## 工作包 2：P1.5-B 建立 10-minute orbit table [done]

目的：把 mean orbit 轉成不跨 chunk 的 UTC 10-minute candidate rows。

輸入：完整 mean table + quality chunk。

工作：

1. 固定 bin contract：UTC boundary、`pod_count >= 56`、maximum gap、edge exclusion。
2. 先寫 synthetic tests：完整 bin、gap、same-stream cross-ZIP、chunk boundary、首尾 window。
3. 寫 `swarm_a_orbit_10min` writer；每列保留 `pod_count`、`max_pod_gap_s`、`chunk_id`。

驗收：每列只來自單一 chunk；沒有跨 gap；完整 10-second bin 的預期 count 是 60，
但只要 `pod_count >= 56` 就可接受。

## 工作包 3：P1.5-C/D smoothing、derivative、release gate [done]

目的：由 mean-like 10-minute series 產生可解釋的 decay rate。

輸入：`swarm_a_orbit_10min`。

工作：

1. 以每個 chunk 獨立處理；使用已通過 mean-like synthetic gate 的候選 policy。
2. 再以 fixed synthetic constant / linear decline / gap tests 驗證參數與符號。
3. 寫 smooth semi-major axis、derivative、正值 decay rate 與 algorithm metadata。

輸出：canonical P1.5 10-minute orbit output。

驗收：constant derivative 接近零；linear decline sign/size 正確；沒有 NaN/inf 或跨 chunk fit。

## 工作包 4：P1.6 causal feature join [done]

目的：為每一筆 P1.5 row 加入不使用 future value 的 SYM-H、Ap、F10.7、F10.7A。

工作：

1. 先補 pure contract tests：SYM-H exact/interpolation/gap、Ap boundary、F10.7/F10.7A source date。
2. 寫 `swarm_a_analysis_10min` writer。
3. 缺 feature 時保留 orbit row，寫 controlled `quality_flags`；不補 future value。

驗收：每個 source time 都可追溯；除合法 SYM-H right endpoint 外，source time `<= orbit time`。

## 工作包 5：P1.7 release [current-database audit done; fresh rebuild pending]

目的：把 final table、metadata 與 clean rebuild procedure 固定為可交付資料集。

工作：

1. 寫 metadata：raw signature、coverage、code revision、frame policy、P1.4/P1.5/P1.6 policy、row count、missingness。
2. 在新 SQLite 驗證 raw -> P1.3 -> P1.4 -> P1.5 -> P1.6 rebuild。weather preparation v2/v3 修正後此項仍待執行。
3. 可選 CSV/Parquet export；SQLite 保留 working database 角色。

驗收：fresh rebuild 的 schema、row count、UTC range、quality flag、source provenance 均通過 audit。現有 database audit 不是此驗收的替代。

## 每個工作包的固定記錄

```text
before: git status + relevant tests
work: input / algorithm / output table
after: row count / UTC range / missing / parameters
record: TIMELOG.md + linked test
```

詳細規格：[PLAN.md](PLAN.md)。P1.4--P1.7 的歷史設計、實驗與欄位規格留在既有文件；
本文件只管理當前順序、gate 與 blocker。
