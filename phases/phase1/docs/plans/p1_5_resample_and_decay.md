# P1.5 10 分鐘重採樣與衰減率

NOTE: 本頁的 10 分鐘 bin、3／6／12 小時差分和 14,558,400 筆等統計是
retained legacy。現行 P1.5.6 是每個可用 10 秒點回看完整 3／5 個 phase orbit，
分別寫 raw B-L 和 joint H2/H3 v2 slope；現行 Input、Output 與狀態見
[orbit_analysis.md](../lineage/orbit_analysis.md)。下文的「最終產物」
只指當時的 10 分鐘分支。

NOTE: `data/swarm_a_phase1_rebuild.sqlite` 缺少後續查到的兩個官方 Swarm-A maneuver
排除日，已不再是正式交付。v3 從 P1.4 起重建；本頁歷史 row count 不是 v3 output count。

## 目標

P1.5 要從每 10 秒一筆的 `mean_semi_major_axis_m`，在不跨越 `chunk_id` 的前提下，
建立 10 分鐘資料列：

```text
{
  time_us,
  semi_major_axis_orbit_mean_m,
  da_dt_3h_backward_m_s, da_dt_3h_backward_m_day,
  da_dt_6h_backward_m_s, da_dt_6h_backward_m_day,
  da_dt_12h_backward_m_s, da_dt_12h_backward_m_day,
  pod_count,
  max_pod_gap_s,
  chunk_id
}
```

- 每個 `H` 為 3、6、12 小時：`da_dt_Hh_backward_m_s = (a(t) - a(t - H h)) / H h`。
- `da_dt_Hh_backward_m_day = da_dt_Hh_backward_m_s * 86400`；負值表示軌道下降。
- `time_us` 是所有 backward interval 的終點；只發布三個 window 都完整的列，因此每個 run 前 72 個 10 分鐘點沒有 output。
- 每個輸出 bin 只能讀取同一個 chunk 的 POD。

P1.5 mean-orbit 的輸入是所有 P1.3 valid row，先於 P1.4 執行。P1.4 只決定哪些既有
mean-orbit row 可進入 chunk、10-minute bin 與 decay。這使新增官方 maneuver exclusion
只需要由 P1.4 往下重建，不必重新呼叫 Orekit。

## 已完成的輸入檢查

舊版 P1.4 曾提供 6 個 final chunks；v3 count 待下游重建完成後更新。native POD cadence
是 10 秒。一個完整 10 分鐘 bin
應有 60 筆 POD；`pod_count >= 56` 可輸出，`pod_count <= 55` 排除。

## 真實資料試跑結果

先對第一個 interval 試跑自然 cubic B-spline。這一步不是最終產物，只是確認
直接平滑 osculating semi-major axis 是否合理。

| 量測 | 結果 |
| --- | ---: |
| interval 內半長軸範圍 | 6,791,545.8 至 6,811,052.0 m |
| 相鄰 10 秒半長軸差的標準差 | 153.9 m |
| 自動 GCV spline 在第一個 UTC 10 分鐘點的導數 | -7.97 m/s |

最後一項相當於一天數十萬公尺的下降，物理上不可能是 Swarm-A 的大氣阻力。
這代表 spline 仍在追蹤短週期的 osculating variation，而不是長期衰減。

這符合軌道力學文獻：J2 會造成 osculating element 的短週期項，分析長期變化時
需要移除短週期項或取平均。[NASA 技術報告](https://ntrs.nasa.gov/api/citations/19720024752/downloads/19720024752.pdf)
記錄了從 osculating element 移除 J2 項與按一個軌道週期平均的作法；
[ESA 技術論文](https://conference.sdo.esoc.esa.int/proceedings/isdrw01/paper/6/ISDRW01-paper6.pdf)
也把 osculating-to-mean conversion 定義為移除 short-periodic variation。

## P1.5-A：direct Savitzky-Golay synthetic 檢驗

這個檢驗只回答一個狹窄問題：能不能直接對每 10 秒的 osculating
`semi_major_axis_m` 套 Savitzky-Golay filter，再把它的一階導數當成 decay？它不宣稱
輸出是 Brouwer-Lyddane mean element。

測試在一個 24 小時、每 10 秒一筆的可重現 synthetic series 上進行：

```text
a_true(t) = 6,800,000 m - 1 m/day * t
a_observed(t) = a_true(t)
                + 9,500 m * sin(2*pi*t/2,780 s)
                + 1,200 m * sin(4*pi*t/2,780 s + 0.6)
                + fixed-seed Gaussian noise (std = 25 m)
```

歷史 read-only audit 使用舊 `interval_id = 1, 2, 3, 1685` 的完整 8,640 筆資料，先用 linear
least-squares trend detrend，再取 real FFT。四個 interval 的半長軸 peak-to-peak 都約 19.5 km；
最強 short-period component 都是 46.452 分鐘，振幅為 9,535.3 至 9,675.1 m。
因此 synthetic 使用 2,780 s、9,500 m 的代表性 component，並加一個 harmonic。它不是 J2
的完整物理模型；用途是檢查單一 sine 假設不足時，數值平滑會不會誤把短週期導數當 decay。

候選是 raw 10 秒列上的 1、2、3 個代表性 dominant-period window：279、559、837 samples，
polynomial order 為 2 或 3。每個候選只評估兩側各排除 half-window 後的 interior。
合格條件為：median decay 誤差 <= 0.05 m/day，95th-percentile absolute error
<= 0.2 m/day。

| window samples | polynomial order | median decay m/day | 95th-percentile absolute error m/day |
| ---: | ---: | ---: | ---: |
| 279 | 2 | -23,228.9 | 580,407.8 |
| 279 | 3 | 49,633.7 | 1,598,042.7 |
| 559 | 2 | -5,775.3 | 144,226.0 |
| 559 | 3 | 13,562.7 | 164,406.0 |
| 837 | 2 | -2,586.6 | 64,436.8 |
| 837 | 3 | 6,237.6 | 120,535.1 |

所有候選都不合格。表格保留這個歷史實驗的輸入、門檻與結果；直接 raw-SG 分支已淘汰，
不保留 standalone verification script。

**結論**：direct raw SG candidate 已淘汰。這不是只要把 window 加長一點就能解決的
數值小誤差；在一天長的 interval 內，足以壓低這種 km-level short-period derivative 的
window 會幾乎沒有可用 interior。下一步應先定義 orbit-average 或理論
osculating-to-mean conversion，再決定是否在該較慢序列上做 SG smoothing。

## P1.5-A：最小 SG candidate 的條件式驗證

**決定**：SG 的最小 candidate 是對 mean-like 10 分鐘 series 使用 centered
Savitzky-Golay，`window_length = 73` samples（12 小時）、`polynomial_order = 2`，
並只發布兩端各排除 36 samples（6 小時）的 interior derivative。

它的 input contract 是：單一 final `chunk_id` 內的 regular 10 分鐘 mean-like series；short-period
treatment 後的殘餘必須先用真實資料量測。這個 candidate 不是 raw-POD filter，也不是
Brouwer-Lyddane mean-element conversion。

可重跑 synthetic case 仍使用已知 `1 m/day` linear decline，但現在輸入是每 10 分鐘一筆、
只加 fixed-seed Gaussian residual noise（std = 0.1 m）的 mean-like series。驗收 gate 為：
median error <= 0.1 m/day，95th-percentile pointwise error <= 0.2 m/day。

| 量測 | 結果 |
| --- | ---: |
| median decay | 0.9462 m/day |
| median error | 0.0538 m/day |
| 95th-percentile pointwise error | 0.1812 m/day |
| held-out seed 的 95th-percentile pointwise error | 0.1527 m/day |

結果通過 gate。這是歷史 numerical candidate 的 fit / held-out 結果，
不是已啟動的 P1.5 implementation。

**限制**：這是 SG numerical stage 的驗證，不是 P1.5 release。要把它用在真實資料，
P1.5-A 仍必須先定義 orbit-average / mean-element conversion，並證明真實 conversion 後的
residual、UTC bin coverage 和 edge exclusions 都符合此 input contract。

## P1.5-A：simple orbit-average audit 失敗

以第一個 real interval 的 mean semi-major axis 計算 Kepler period，得到 5,582.02 s；以
10-second cadence 四捨五入為 558 samples。對 raw `semi_major_axis_m` 做 centered rectangular
rolling average 後再 detrend，結果如下。

| average window | residual std m | residual peak-to-peak m | remaining interior hours |
| ---: | ---: | ---: | ---: |
| 1 orbit, 558 samples | 13.245 | 54.406 | 22.45 |
| 2 orbits, 1,116 samples | 12.828 | 49.810 | 20.90 |
| 3 orbits, 1,674 samples | 12.535 | 43.409 | 19.35 |
| 6 orbits, 3,348 samples | 12.223 | 38.901 | 14.70 |
| 12 orbits, 6,696 samples | 12.131 | 35.484 | 5.40 |

1-orbit average 的 raw peak-to-peak 確實從 19,506.2 m 降到 66.6 m，但 residual std 仍是
13.245 m，遠高於 SG synthetic candidate 的 0.1 m residual condition；同一段的 linear
slope 是 20.306 m/day，也不能視為 Swarm-A drag。

**決定**：simple rectangular orbit-average 淘汰。增加到 12 orbits 只減少約 1.1 m residual，
卻幾乎用掉一天 interval 的可用 interior。不可把它當 P1.5-B 的方法。

選定的方法是 Brouwer-Lyddane osculating-to-mean conversion。官方 Orekit API 有固定點
`computeMeanOrbit`；自行重寫該理論不符合本專案的最小實作原則。

2026-10-01 已在專案隔離環境 `.orekitvenv/` 安裝與驗證：

```text
orekit-jpype = 13.1.8.0
jdk4py       = 25.0.2.1
orekit-data  = official checkout 3e376b326373467647b1e246ebb083cd9e57cd68
```

該環境已成功載入 Orekit data，並建立 `2024-05-10T12:00:00.000 UTC`。它已加入
`.gitignore`，不會提交到 repository。執行時使用內建 `jdk4py` runtime；不需要系統 Java
在 `PATH`。

## P1.5-A：Brouwer-Lyddane mean-orbit 驗證

實作：

```text
raw swarm_a_states {UTC, ITRF, position_m, velocity_m_s}
  -> itrf_states_to_gcrf()
  -> Orekit CartesianOrbit {UTC, GCRF, m, m/s}
  -> BrouwerLyddanePropagator.computeMeanOrbit()
  -> swarm_a_mean_orbital_elements {time_us, mean_semi_major_axis_m}
```

`M2 = 0.0`；Brouwer-Lyddane 只移除 J2--J5 gravity short-period terms，不引入經驗
drag correction。這不是 decay-rate 計算。

最小 regression：固定 synthetic GCRF state 產出
`mean_semi_major_axis_m = 6,870,017.991 m`；ITRF input 會在呼叫 Orekit 前拒絕。
SQLite integration test 以兩筆 ITRF state 驗證 derived table、metadata 與 raw table 分離。

真實資料 read-only gate：各取一個完整 86,400 秒 interval，對 raw `semi_major_axis_m`
與 mean `semi_major_axis_m` 各自 linear detrend，再量測 46.452-minute FFT component。

| interval | raw amplitude m | mean amplitude m | reduction |
| ---: | ---: | ---: | ---: |
| 1 | 9,535.35 | 52.65 | 99.45% |
| 843 | 7,395.07 | 48.89 | 99.34% |
| 1,685 | 9,675.05 | 64.54 | 99.33% |

三段都是 `8,640 / 8,640` finite conversion rows。mean residual std 為 `58.23`、`63.54`、
`63.80 m`；raw residual std 為 `6,828.81`、`6,799.52`、`6,846.19 m`。因此
Brouwer-Lyddane 通過 P1.5-A 的「移除主導 short-period term」method gate。

這個 gate 不代表 B-L output 無雜訊。J2--J5 以外的重力場、日月攝動、POD 誤差與未被模型
吸收的短週期項仍可留下數十至數百 m oscillation。後續 rate 前必須在平靜期做 periodogram：
約 94/47 min peak 先檢查 phase harmonic 與常數/角度單位；12/24 h peak 先檢查 ITRF -> GCRF
PV transform；沒有主導週期才視為 POD noise。當時曾提議對 3 與 5 個完整
orbit mean 做 OLS sensitivity；現行 P1.5.6 並非對每圈均值擬合，而是每個可用
10 秒 mean-element 點回看精確 3／5 圈相位範圍，對視窗內原始 cadence 點擬合。
少於一圈的 1 h slope 只保留 diagnostic。

這段是 P1.5-A 的歷史 gate。legacy working database 有 14,558,400 legacy mean rows；frozen
cached release 有 13,495,680 usable mean rows、224,928 `swarm_a_orbit_10min` rows，以及 224,280 final analysis rows。P1.4 對 ESA 公告的
orbit-raise campaign 做 date-level exclusion；其餘 Q4 residual candidate 維持 audit-only，
不以未校準門檻排除資料。

## P1.5.6：four local-decay candidates [working]

不以 UTC day 切 slope。P1.5.4 的 complete phase orbit 只定義 window 邊界；對每個最近 3 或 5
完整 orbit window，都保留下列四種結果，並以最後一圈的 UTC 作為 rate 時刻：

| `decay_method` | `orbit_window` | rate |
| --- | ---: | --- |
| `raw_b_l_local_ols` | 3 | raw B-L `a` 的 OLS slope |
| `joint_h2_h3_local_ols` | 3 | `trend + H2(u) + H3(u)` 的 trend slope |
| `raw_b_l_local_ols` | 5 | raw B-L `a` 的 OLS slope |
| `joint_h2_h3_local_ols` | 5 | `trend + H2(u) + H3(u)` 的 trend slope |

視窗不跨 `chunk_id`，且相鄰圈邊界 gap 不得超過 20 s。3 圈約 4.5 小時，5 圈約 7.5 小時；前者較快，後者較低雜訊。`swarm_a_phase_harmonic_decay_candidates_v1` 保留 normalized long rows，key 是 `(time_us, decay_method, orbit_window)`，供 P1.6 逐 candidate 對齊。`swarm_a_phase_harmonic_decay_raw_b_l_sets_v1` 與 `swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v1` 都以 `time_us` 為 key，各自一列放 3/5-orbit 的 rate、1-sigma、residual；未累積滿 5 圈時，保留 3 圈結果且 5 圈欄位為 `NULL`。

read-only diagnostic 使用 2023-12-25 至 2024-01-01 的 60,480 筆 10-minute B-L mean element：

| check | result |
| --- | ---: |
| 最大 residual periodogram peak | 47.10 min |
| 3-orbit quiet rate mean / standard deviation | -34.77 / 69.63 m/day |
| 5-orbit quiet rate mean / standard deviation | -35.52 / 35.06 m/day |
| May-2024 minimum 3-orbit rate | -317.04 m/day |
| May-2024 minimum 5-orbit rate | -276.63 m/day |

47.10 min peak 證實 B-L 後仍有半軌道殘留。這是 estimator 的雜訊診斷，不是對磁暴因果或真實 drag 的宣稱。三年 working copy `phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite` 已寫入 67,328 `swarm_a_phase_harmonic_decay_candidates_v1` rows、16,836 raw-B-L set rows、16,836 joint-H2/H3 set rows。`prep_13_orbit_decay_diagnostic_figures.py` 以 read-only connection 產生圖。

### H1--H5 joint-fit sensitivity

不採用「先扣 Fourier wave、再 OLS」兩步法。對同一個 raw `a(t)` 視窗直接估計：

```text
a(t) = b0 + b1 * (t - t0) + sum[k in selected H] (C[k] cos(k*u) + S[k] sin(k*u)) + residual
```

`b1` 是 rate；比較 `selected H = {2, 3}` 與 `{1, 2, 3, 4, 5}`。在 quiet week 與 May-2024
storm 都得到相同模式：H1--H5 降低 residual，但 3-orbit rate 的 median absolute change 約
`37.5 m/day`，5-orbit 約 `8 m/day`。因此 H1--H5 保留為 sensitivity；不能用它取代主要
5-orbit estimator，也不能把 residual 變小直接稱為較真實的 decay。

### 20-orbit H2/H3 then 3-orbit OLS sensitivity

另一個 two-scale candidate 是：對 trailing 20 complete orbit joint-fit H2/H3 與 linear trend，
只把 H2/H3 coefficient 套到最後 3 complete orbit，再對 residual 做 3-orbit OLS。它完全使用
當前時刻以前的資料，但假設 20 圈期間的 H2/H3 仍代表最後 3 圈。

結果否定這個假設。quiet week 的 3-orbit residual median 從 joint H2/H3 的 `28.71 m` 增至
`37.96 m`；May-2024 從 `29.03 m` 增至 `37.80 m`。兩段的 rate median absolute difference 都約
`12.5 m/day`。因此 20 圈並未提供較好的當下 H2/H3 model，可能引入 amplitude/phase lag；只保留
圖作反例，不進 candidate table。

### Raw B-L a versus joint H2/H3

同一個 3-orbit raw B-L `a` 視窗若不放 harmonic term，quiet residual median 是 `61.93 m`，
May-2024 是 `62.60 m`。joint H2/H3 分別降至 `28.71 m` 與 `29.03 m`，但兩段 rate median
absolute difference 仍有 `42.55 m/day` 與 `43.31 m/day`。H2/H3 因此不是圖形美化：它實質改變
短窗 slope；同時 residual 下降不構成它較接近真實 instantaneous decay 的證據。

## 歷史限制與已採用解法

短週期處理固定為 Brouwer-Lyddane mean-element conversion，不再對 10 分鐘列做
Savitzky-Golay smooth。10 分鐘 bin contract 固定為 `[end - 600 s, end)`、同一
`chunk_id`、至少 56 筆、最大 gap 10 s；實際 `pod_count = 58..60`。每個輸出 rate
只比較同一連續 run 的 `a(t)` 與 `a(t - 12 h)`；各 run 的第一個 72 列不輸出。

## 發布結果

```text
swarm_a_mean_orbital_elements: 13,495,680 usable rows
  -> swarm_a_orbit_10min: 224,928 rows
  -> same-chunk backward 3h/6h/12h differences
  -> swarm_a_analysis_10min: 224,280 rows
```

- P1.5 orbit algorithm：`utc_10min_mean_brouwer_lyddane_v1`。
- legacy rate algorithm：`backward_difference_12h_mean_orbit_v2`。新 release 使用 `backward_difference_3h_6h_12h_mean_orbit_v3`。
- 新 release 的所有 3、6、12 小時 interval 都限制於一個 `chunk_id` 的連續 600 s run。
- final analysis table 不含 density；DNSAACC density 保留 raw table，待獨立研究問題定義。
