# Phase 1 完整執行計畫

## 目標

現行主線由 mean-element checkpoint 建立逐 10 秒的 raw B-L 與 joint H2/H3
局部斜率候選、共用 causal feature，以及 P1.7 v2 working audit。
`swarm_a_analysis_10min` 是保留的舊分支，不是現行輸出。

```text
raw POD / weather / geomagnetic
  -> raw SQLite {immutable}
  -> quality + P1.5.1 mean-element checkpoint
  -> P1.5.6 raw / joint H2/H3 3／5 圈局部斜率
  -> P1.6 shared causal feature
  -> P1.7 v2 working audit
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
現行 phase-orbit window 與舊 10-minute bin、3/6/12 小時 derivative
都不可跨 `chunk_id`；下列 10-minute POD bin contract 只屬 retained legacy。

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
| P1.1/P1.2 raw intake | [done] | 12 年 checkpoint：4,554 `source_files`；39,346,560 `swarm_a_states`。三年 checkpoint 也保留這些全期 raw rows |
| P1.3 osculating element | [done] | 12 年 checkpoint：39,346,560 `swarm_a_orbital_elements` rows，依 P1.5.1 input contract 使用 |
| P1.4-A/B chunk rebuild | [done] | 12 年 checkpoint：39,346,560 quality rows；38,378,880 usable、967,680 unusable。舊 13,495,680 usable／9 chunks 統計不代表現行全期 |
| P1.4-C provenance + Q3 | [done] | `swarm_a_pod_source_provenance` SP3 metadata；`quality_source: unavailable` |
| P1.4-D Q4 residual audit | [done: audit-only] | synthetic jump sensitivity；不設 rejection threshold |
| P1.5-A mean-orbit method | [done] | Brouwer-Lyddane；主導 46.452 min 項抑制 99.33--99.45%，但 residual 非零 |
| P1.5.1 full checkpoint | [done] | `data/sqlite/swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite`；39,346,558 verified Orekit B-L mean rows；rejection 0 |
| P1.5.1 three-year checkpoint | [done] | `data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite`；9,469,438 verified Orekit B-L mean rows；rejection 0 |
| P1.5-B 10-minute orbit | [retained] | 224,928 `swarm_a_orbit_10min` 是舊範圍結果，不在現行 v2 主線 |
| P1.5-C/D derivative | [retained] | 10 分鐘分支的 3／6／12 小時 backward difference；不是現行 3／5 圈 OLS |
| P1.5.4 phase complete-orbit mean | [working] | 三年 16,844 `swarm_a_phase_orbit_mean_v2`；phase-weighted、chunk-local |
| P1.5.5 H2/H3 diagnostic | [working] | 三年 3 `swarm_a_phase_harmonic_diagnostic_v1` rows；只作週期殘留診斷 |
| P1.5.6 local decay candidates | [working] | active v2：三年 raw B-L / joint H2H3 各 9,469,438 rows；12 年各 38,378,878 rows；每個 usable 10 s epoch 一列。v1 long candidates retained legacy |
| P1.6 legacy causal join | [retained] | 224,280 `swarm_a_analysis_10min`；舊 10-minute backward-rate branch |
| P1.6 phase-candidate causal join | [working] | v1 long-table join retained legacy；active v2 feature 三年 9,469,438 rows、12 年 writer metadata 38,378,878 rows；每個 `time_us` 一列 |
| P1.7 legacy working-DB audit | [retained] | 226,368 rows；舊 10-minute backward-rate branch |
| P1.7 phase-candidate audit | [done] | 三年與 12 年 v2 audit 各 6 rows、violation 全為 0，metadata status 均為 `pass`；v1 audit retained legacy |
| P1.5.4--P1.7 current output | [working] | 三年 `phase_candidate_working_v1.sqlite` 與 12 年 `phase_candidate_working_v2.sqlite`；名稱版本不同，但現行 table 均為 v2 |

全期 raw／quality 有兩筆 2014-01-01 UTC 前的 state：
2013-12-31 23:59:44 與 23:59:54。它們的 `is_usable = 1`，但在
P1.5.1 起始範圍外。因此 39,346,560 raw rows 對應 39,346,558 mean rows；
38,378,880 usable quality rows 對應 38,378,878 個 P1.5.6 v2 source keys。
這是時間邊界，不是兩筆範圍內遺漏。

## 尚未由 P1.7 v2 證明的事項

- 6 項 audit 不包含逐列精確 phase span、source gap／chunk window 邊界與拒絕原因的獨立重算。
- 12 年工作庫的 audit scope 從 2014-01-01 起；2014-07-01 起的報告篩選結果尚未獨立稽核。
- maneuver、POD source 差異與模型偏差尚未校準；`pass` 不等於真實 drag 或正式 release。

## 依賴

```text
P1.4 final policy
  -> P1.5 Orekit mean-element checkpoint
      -> full copy to downstream working database
      -> P1.5.4 {phase-defined complete-orbit boundary and mean}
          -> P1.5.5 {H2/H3 diagnostic}
          -> P1.5.6 {raw B-L / joint H2/H3 x 3/5-orbit candidates}
              -> P1.6 {one causal feature row by time_us}
                  -> P1.7 {raw/joint/features v2 audit}

retained legacy: P1.5-B/C/D 10-minute bin -> 3h/6h/12h backward rate
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

P1.5.4--P1.5.6 phase candidate
u = omega + M, not a fixed 46-minute clock
chunk change or POD gap > 10 s -> reset phase and fit boundary
complete orbit -> trapezoidal delta-u weighted mean + H2/H3 diagnostic
P1.5.6 -> raw B-L or joint H2/H3, each over trailing 3/5 complete-orbit window

P1.6
weather / geomagnetic source time <= orbit time
density stays outside core analysis table
```

`pod_count = 56..59` 只允許出現在 chunk 邊緣；chunk 中間應為 60。

## 舊版 Full mean batch 收尾順序 [retained]

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

目的：對每筆 P1.3 valid POD 建立一次 Brouwer-Lyddane mean element，並凍結為可重用的 P1.5 SQLite checkpoint。

輸入：`swarm_a_states` + `swarm_a_orbital_elements {semi_major_axis_m != NULL, rejection_reason = NULL}`。

工作：

1. 只在首次建立或明確更換 B-L 模型版本時執行 `prep_04_mean_orbit`；不可同時有第二個 SQLite writer。
2. 驗證 count、missing、rejection、首尾 UTC、每 source completeness 後，寫入 versioned `p1_5` checkpoint。
3. P1.5.2 以後的工作一律複製 `p1_5`；一般 rebuild 沒有 cache path 必須失敗，不可默默重跑 Orekit。

輸出：現行 `swarm_a_mean_orbit_elements_v1 {time_us, mean_semi_major_axis_m, rejection_reason}`；舊 `swarm_a_mean_orbital_elements` 留作歷史比較。

驗收：所有 P1.3 valid POD 都有一列；P1.4 在下游排除官方 orbit event 與其他不可用 row；不改 raw table。

歷史完成證據：campaign date-level exclusion 加入前，14,558,400 POD 有 mean row；每 source
completeness 差異 0；mean semi-major axis 均為有限正值，範圍
6,787,017.63--6,860,042.07 m；rejection 0。新版 policy 的 fresh rebuild 已另在 cache
target 為 13,608,000 個 usable POD 產生 mean rows。

## 工作包 2：P1.5-B 建立 10-minute orbit table [retained]

目的：把 mean orbit 轉成不跨 chunk 的 UTC 10-minute candidate rows。

輸入：完整 mean table + quality chunk。

工作：

1. 固定 bin contract：UTC boundary、`pod_count >= 56`、maximum gap、edge exclusion。
2. 先寫 synthetic tests：完整 bin、gap、same-stream cross-ZIP、chunk boundary、首尾 window。
3. 寫 `swarm_a_orbit_10min` writer；每列保留 `pod_count`、`max_pod_gap_s`、`chunk_id`。

驗收：每列只來自單一 chunk；沒有跨 gap；完整 10-second bin 的預期 count 是 60，
但只要 `pod_count >= 56` 就可接受。

## 工作包 3：P1.5-C/D backward difference、release gate [retained]

目的：由 mean-like 10-minute series 產生可解釋的 decay rate。

輸入：`swarm_a_orbit_10min`。

工作：

1. 以每個 chunk 的連續 600 s run 獨立處理。
2. 以 fixed synthetic constant / linear decline / gap tests 驗證 3、6、12 小時 backward interval 與符號。
3. 寫 orbit-mean semi-major axis、三組 backward derivative 與 algorithm metadata。

輸出：舊版 P1.5 10-minute orbit output，不是現行主線。

驗收：constant derivative 為零；linear decline sign/size 正確；沒有 NaN/inf、跨 chunk 或跨 gap interval。

## 工作包 3.1：P1.5.4--P1.5.6 phase-defined candidate [working]

目的：以每筆 mean element 的 phase `u = omega + M` 定義完整 orbit，避免把固定 UTC window 當成軌道週期；先量化 H2/H3 殘留，再對同一個 3 或 5 complete-orbit window 保留 raw B-L 與 joint H2/H3 兩種局部 slope。

輸入：`swarm_a_mean_orbit_elements_v1` + `swarm_a_pod_quality`。

工作：

1. P1.5.4 依 `chunk_id` 和實際 10 s POD gap 切斷，對完整 phase orbit 做 trapezoidal `delta-u` weighted mean；每圈寫 H2/H3 Fourier coefficient。
2. P1.5.5 以每個 chunk 彙整 H2/H3 amplitude median/max；只作診斷，不設自動 rejection threshold。
3. P1.5.6 對每個可用 10 s B-L mean-element epoch，以 `u = unwrap(omega + M)` 向前取精確 3 或 5 個 phase orbit。起點落在兩筆間時直接內插 time 與 a；其餘點不重採樣。每個 window 都寫 raw B-L OLS 與 `trend + H2(u) + H3(u)` joint OLS 到兩張 v2 table；slope 存 m/s。視窗不可跨 chunk、source gap > 20 s 或非單調 u；沒有完整範圍只寫 null 與 reject reason。H1--H5 與 20-orbit H2/H3 sensitivity 不進 candidate table。v1 long candidates 只保留給舊 P1.6 branch。

現行輸出：`swarm_a_phase_harmonic_decay_raw_b_l_sets_v2` 與 `swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2`，兩表均以 `time_us` 為 key，每列保留 3／5 圈結果。三年的 `swarm_a_phase_orbit_mean_v2` 與 `swarm_a_phase_harmonic_diagnostic_v1` 是上游診斷。`swarm_a_phase_harmonic_decay_candidates_v1` 及兩張 `sets_v1` 僅供舊 P1.6/P1.7 branch 追溯，不是現行輸出。
`prep_13_orbit_decay_diagnostic_figures.py` 另寫 quiet periodogram、quiet raw-versus-complete-orbit mean、May-2024 four-candidate rate/residual 圖；圖是 working candidate 的視覺檢查，不是額外資料產品。SQLite 已有 active write lock 時，圖可用 read-only path 生成，derived table 保持未寫入。

驗收：synthetic periodogram、chunk boundary、known linear OLS slope 均通過。三年資料有 16,844 complete-orbit mean；2023-12-25 至 2024-01-01 quiet periodogram 的最大 peak 是 47.10 min。5-orbit quiet rate standard deviation 是 35.06 m/day。這些 slope 仍是 descriptive candidate，不是已校準 storm decay。

## 工作包 4：P1.6 causal feature join [working]

目的：每個 P1.5.6 v2 `time_us` 只寫一筆 causal feature，供兩張 rate table 共用；不複製四份 feature。

工作：`prep_15_phase_harmonic_features_v2.py` 讀取 raw/joint v2 的共同 `time_us`，寫入 `swarm_a_phase_harmonic_features_v2`。weather source time 不可晚於 target time；SYM-H 非 exact 時僅允許左右觀測總間距 <= 120 s 的內插。舊 `prep_10_phase_harmonic_decay_analysis.py` branch retained。

輸出：三年 9,469,438 筆 v2 feature rows；12 年 writer metadata 記錄 38,378,878 筆。舊三年 67,328 筆 v1 analysis rows retained。

驗收：兩張 v2 rate table 與 feature table 的 `time_us` 一致；future weather reference 由 P1.7 v2 稽核。

## 工作包 5：P1.7 phase-candidate audit [done]

目的：分別稽核三年與 12 年 v2 rate/feature branch，不把舊 `swarm_a_analysis_10min` 或 v1 candidate 的 audit 結果延伸為 v2 結果。

工作：`prep_16_phase_harmonic_audit_v2.py` 檢查三張 v2 table 的 key identity、rate validity parity、feature source causality、有限數值與 SQLite integrity。舊 `prep_11_phase_harmonic_decay_audit.py` branch retained。

輸出：兩份 working copy 各有 6 筆 `swarm_a_phase_harmonic_audit_v2` rows；metadata `p1_7_phase_harmonic_v2_status = pass` 與 v2 manifest。

驗收：三年與 12 年的 6 項 `violation_count` 均為 0。這是資料契約通過，不是 decay 已校準為真實 storm decay。

## 每個工作包的固定記錄

```text
before: git status + relevant tests
work: input / algorithm / output table
after: row count / UTC range / missing / parameters
record: TIMELOG.md + linked test
```

詳細規格：[PLAN.md](PLAN.md)。P1.4--P1.7 的歷史設計、實驗與欄位規格留在既有文件；
本文件前段狀態表與工作包 3.1--5 管理現行 v2；工作包 2--3 及舊版
Full mean batch 順序僅保留歷史契約。
