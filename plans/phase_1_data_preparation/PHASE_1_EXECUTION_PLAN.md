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
mean orbit、10-minute bin、3/6/12 小時 derivative 都不可跨 `chunk_id`。

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
| P1.4-A/B chunk rebuild | [done] | 14,558,400 quality rows；13,495,680 usable rows；9 final chunks |
| P1.4-C provenance + Q3 | [done] | `swarm_a_pod_source_provenance` SP3 metadata；`quality_source: unavailable` |
| P1.4-D Q4 residual audit | [done: audit-only] | synthetic jump sensitivity；不設 rejection threshold |
| P1.5-A mean-orbit method | [done] | Brouwer-Lyddane；3 intervals suppression 99.33--99.45% |
| P1.5 mean-orbit cache | [done] | P1.3 與 mean-orbit 可重用已驗證 cache；13,495,680 usable mean rows；不形成第二個資料庫 |
| P1.5-B 10-minute orbit | [done] | 224,928 `swarm_a_orbit_10min`；9 chunks；`pod_count = 58..60` |
| P1.5-C/D derivative | [legacy] | 12 小時 backward difference；已由 3/6/12 小時契約取代 |
| P1.6 causal join | [done] | 224,280 `swarm_a_analysis_10min`；所有 final feature 均有來源時間 |
| P1.7 legacy working-DB audit | [done] | 226,368 rows；core fields、optional feature groups、causality、chunk continuity 與 SQLite checks 通過 |
| P1.7 current 3h/6h/12h output | [done] | `data/swarm_a_analysis.sqlite`；224,280 rows；`working_audit_pass`、integrity/fk/audit 通過 |

## 依賴

```text
P1.4 final policy
  + P1.5 full mean batch
      -> P1.5-B {10-minute orbit}
      -> P1.5-C/D {3h/6h/12h backward derivatives, release gate}
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
    chunk-local 3h/6h/12h backward differences + decay rates
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

## Legacy cache evidence

```text
13,495,680 usable POD
  -> 13,495,680 mean-orbit rows
  -> 224,928 UTC 10-minute orbit rows
  -> legacy backward 12-hour difference per contiguous chunk/run
  -> 224,280 final analysis rows
```

- `swarm_a_orbit_10min`：6 個 `chunk_id`；`pod_count = 58..60`；`max_pod_gap_s = 10`；演算法 `utc_10min_mean_brouwer_lyddane_v1`。
- bin contract：`[end - 600 s, end)`，end 為 `time_us`；同一 `chunk_id`；至少 56 筆。
- derivative：legacy `backward_difference_12h_mean_orbit_v1`；新 release 使用 `backward_difference_3h_6h_12h_mean_orbit_v3`，每個 window 都比較 `a(t)` 與 `a(t - H h)`，連續 run 前 72 列排除，不跨 chunk 或 600 s gap。
- `swarm_a_analysis_10min`：此段 226,368 列與 `causal_space_weather_geomagnetic_backward_12h_v1` 都是 legacy evidence；新 release 的 row count 與 audit 結果以 P1.7 manifest 為準。
- causal join：Ap、F10.7、F10.7A source time 不晚於 orbit time；SYM-H 只允許有完整左右端點的 <= 2 分鐘內插。P1.7 audit 無 future reference。
- DNSAACC density 保留在 raw `swarm_a_density`，未放入 core analysis table。
- P1.7 cache audit：SQLite `integrity_check = ok`、foreign-key check 空、core fields 無 NULL/NaN/inf、optional feature groups 與 `quality_flags` 一致、無跨 chunk/gap 或 future reference；這是 cache provenance，不是第二個交付物。

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

目的：在 P1.4 前，對每筆 P1.3 valid POD 建立可重建的 Brouwer-Lyddane mean semi-major axis。

輸入：`swarm_a_states` + `swarm_a_orbital_elements {semi_major_axis_m != NULL, rejection_reason = NULL}`。

工作：

1. 從既有 checkpoint 執行 `prep_04_mean_orbit`；不可同時有第二個 SQLite writer。
2. 本次 exceptional full rebuild 可暫時用 3 個 read-only calculator + 1 個 writer；完成後刪除平行 code。
3. 驗證 count、missing、rejection、首尾 UTC、每 source completeness。

輸出：`swarm_a_mean_orbital_elements {time_us, mean_semi_major_axis_m, rejection_reason}`。

驗收：所有 P1.3 valid POD 都有一列；P1.4 在下游排除官方 orbit event 與其他不可用 row；不改 raw table。

歷史完成證據：campaign date-level exclusion 加入前，14,558,400 POD 有 mean row；每 source
completeness 差異 0；mean semi-major axis 均為有限正值，範圍
6,787,017.63--6,860,042.07 m；rejection 0。新版 policy 的 fresh rebuild 已另在 cache
target 為 13,608,000 個 usable POD 產生 mean rows。

## 工作包 2：P1.5-B 建立 10-minute orbit table [done]

目的：把 mean orbit 轉成不跨 chunk 的 UTC 10-minute candidate rows。

輸入：完整 mean table + quality chunk。

工作：

1. 固定 bin contract：UTC boundary、`pod_count >= 56`、maximum gap、edge exclusion。
2. 先寫 synthetic tests：完整 bin、gap、same-stream cross-ZIP、chunk boundary、首尾 window。
3. 寫 `swarm_a_orbit_10min` writer；每列保留 `pod_count`、`max_pod_gap_s`、`chunk_id`。

驗收：每列只來自單一 chunk；沒有跨 gap；完整 10-second bin 的預期 count 是 60，
但只要 `pod_count >= 56` 就可接受。

## 工作包 3：P1.5-C/D backward difference、release gate [done]

目的：由 mean-like 10-minute series 產生可解釋的 decay rate。

輸入：`swarm_a_orbit_10min`。

工作：

1. 以每個 chunk 的連續 600 s run 獨立處理。
2. 以 fixed synthetic constant / linear decline / gap tests 驗證 3、6、12 小時 backward interval 與符號。
3. 寫 orbit-mean semi-major axis、三組 backward derivative 與 algorithm metadata。

輸出：canonical P1.5 10-minute orbit output。

驗收：constant derivative 為零；linear decline sign/size 正確；沒有 NaN/inf、跨 chunk 或跨 gap interval。

## 工作包 4：P1.6 causal feature join [done]

目的：為每一筆 P1.5 row 加入不使用 future value 的 SYM-H、Ap、F10.7、F10.7A。

工作：

1. 先補 pure contract tests：SYM-H exact/interpolation/gap、Ap boundary、F10.7/F10.7A source date。
2. 寫 `swarm_a_analysis_10min` writer。
3. 缺 feature 時保留 orbit row，寫 controlled `quality_flags`；不補 future value。

驗收：每個 source time 都可追溯；除合法 SYM-H right endpoint 外，source time `<= orbit time`。

## 工作包 5：P1.7 release [done]

目的：把 final table、metadata 與 clean rebuild procedure 固定為可交付資料集。

工作：

1. 寫 metadata：raw signature、coverage、code revision、frame policy、P1.4/P1.5/P1.6 policy、row count、missingness。
2. 已在 `data/swarm_a_phase1_rebuild.sqlite` 驗證 raw -> P1.3 -> P1.4 -> P1.5 -> P1.6 rebuild 與 P1.7 audit。
3. 可選 CSV/Parquet export；`data/swarm_a_analysis.sqlite` 是唯一正式交付，archive/cache 只保留比較或復原用途。

驗收：fresh rebuild 的 schema、row count、UTC range、quality flag、source provenance 均已通過 audit。

## 每個工作包的固定記錄

```text
before: git status + relevant tests
work: input / algorithm / output table
after: row count / UTC range / missing / parameters
record: TIMELOG.md + linked test
```

詳細規格：[PLAN.md](PLAN.md)。P1.4--P1.7 的歷史設計、實驗與欄位規格留在既有文件；
本文件只管理當前順序、gate 與 blocker。
