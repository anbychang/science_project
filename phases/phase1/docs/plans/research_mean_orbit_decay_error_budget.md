# mean semi-major axis 長期 decay 的誤差討論

## 結論

目前的 `-69.46 m/day` 是 `SP3xCOM_2_ -> ITRF/GCRF -> Brouwer-Lyddane
J2..J5, M2=0 -> phase-weighted orbit mean -> OLS` 這個 estimator 的三年線性斜率；它不是已校準的
純 drag rate。回歸線在三年跨度對應約 `76 km`；資料首尾實際差約 `71 km`。若外部數值是 `2 m/day`，兩者尚不可直接比較，必須先確認對方是否同樣是
Swarm-A、同一期間、POD 的 orbit-mean semi-major axis，而非高度、TLE 或某段 quiet-time rate。

最重要的未知不是 H2/H3。H2/H3 與不完整 phase average 會污染短窗導數，但目前可見的十至數十 m
phase 項不會自行累積成數十 km 的三年下降。read-only control 以同一批 phase endpoint 的原始 POD
position 直接算 `sqrt(x^2 + y^2 + z^2)`，得到 `-69.32 m/day`；同時刻的 raw osculating `a` 是
`-69.36 m/day`，B-L phase-weighted mean 是 `-69.46 m/day`。因此 B-L `J2..J5, M2=0` 仍需做
sensitivity，但不是目前 3-year slope 偏大的主要嫌疑。

本次再以同期 `SP3AKIN` kinematic position 做 13 個跨期日檔的 raw-radius cross-check。每個代表日的
KIN 與 RD 近地點半徑差為 `-0.19..0.00 m`，遠地點半徑差為 `+0.01..+0.11 m`；相同 13 日樣本的
KIN/RD 近地點斜率都為 `-66.64 m/day`，遠地點分別為 `-66.06 m/day`。這支持原始幾何的長期下降不屬於
RD reduced-dynamic 特有的改正；但 KIN 與 RD 同屬 ESA POD 資料鏈，不能當成完全獨立觀測。下一個品質
缺口仍是 `SP3AVAL` 的逐日 residual/empirical-acceleration 篩選，以及完整 KIN 序列的正式不確定度。

## 目前實際忽略或尚未校準的項目

| 項目 | 現在的處理與缺口 | 對三年 slope 的方向 | 能否解釋數十 `m/day` | 必要驗證或緩解 |
|---|---|---|---|---|
| B-L `M2=0` | Orekit 明定 `M2=0` 時，dynamical model 不考慮 secular along-track effects。`M2` 本來是 OD 中調整的未建模 secular along-track effects 合併項，不只 atmospheric drag。 | 未知。不是「少扣 drag」可直接判定正負；改變的是 osculating-to-mean mapping。 | **不像主要原因。** 同 phase 的 raw position radius 與 raw osculating `a` 也約是 `-69.3 m/day`；仍沒有本資料的正式 bound。 | 對同一 POD epoch 比較 `M2=0`、合理的 sensitivity range、以及獨立數值/energy method 的三年 slope；把差值列為 model sensitivity，不能預設為修正值。 |
| gravity model 只到 J5 zonal | B-L 官方模型只含 J2 至 J5 zonal harmonics。它沒有 tesseral/sectorial gravity、Sun/Moon、solid/ocean/pole tides、SRP 的完整 conservative work。 | 未知；多數會是週期或長週期 leakage，不可假設平均為零。 | **未知。** Li & Lei 的完整 energy route 顯示 time-varying potential 不能任意省略，但沒有給本 B-L estimator 的三年誤差界。 | 用含完整 potential 的 independent energy/work integration 做外部對照；不要把 B-L residual 或 Fourier subtraction 說成已移除全部 conservative effect。 |
| phase-defined orbit mean | 圈的起訖落在 sample，而非精確 `2*pi` boundary；接受門檻是 coverage `>= 2*pi - 0.05`。剩餘 phase harmonic 或不完全 coverage 可泄漏至 orbit mean。 | 未知；固定形狀通常主要是短期波動，不應自然形成單調長期下降。 | **僅就已見十至數十 m H2/H3 而言，不足以解釋三年約 76 km。** 其他未量化長週期項仍未知。 | 在 phase boundary 插值後重新積分；掃描不同 boundary offset、coverage threshold 與 harmonic order，報告三年 slope spread。保留 1 h rate 為失敗 diagnostic，不作物理 rate。 |
| ITRF -> GCRF 與 GPS -> UTC | 官方產品是 ITRF Earth-fixed `r,v`、GPS time；程式已轉 GPS -> UTC，並對 position 與 velocity 一起做 ITRS -> GCRS transform。正確的全 PV transform 不應憑空產生 secular decay。 | 正確實作時不預期有固定方向；若漏掉 velocity 的 rotation/時間系統，結果可嚴重錯。 | **只有實作錯誤時可能。** 不是可當作小的未建模物理項。 | 用獨立 Orekit/IERS transform 做逐 epoch `r,v` 差分和 ITRF -> GCRF -> ITRF round-trip；確認所有 source 的 frame label、GPS time 與 leap-second conversion。 |
| POD product / arc / quality | ESA 將 `SP3xCOM_2_` 定義為 precise reduced-dynamic position/velocity；位置宣稱 few-cm 3D，但 quality 是獨立 `SP3xVAL_2_`，目前尚未對齊寫入。此產品不是 maneuver log。 | 未知。arc/baseline step 或未標記 maneuver 可改變端點 OLS。 | **不能排除，也不能宣稱已證實。** few-cm position 不是本 estimator 的長期 `a` uncertainty；沒有 SP3xVAL 就沒有正式 bound。 | 取得並按 epoch/arc 對齊 `SP3xVAL_2_`；分 source baseline、arc、campaign 前後各自 fit；檢查每日產品接縫與已知 maneuver window。 |
| orbit raise / maneuver | 自然 decay 統計尚未有完整官方 maneuver timeline 與逐 epoch exclusion。已知 orbit raise 的 `a` 增量為正。 | 已知 raise 若保留，會把自然下降變得**較不負**；不能解釋「算得太負」。未標記或姿態/POD event 的方向未知。 | raise 本身：**否，方向相反**；其他未分類 event：未知。 | 排除已公告 campaign 的完整窗口，切開 chunk；未取得 maneuver UTC 前不可用圖形跳點反推並假稱 firing time。 |
| OLS 與殘差 autocorrelation | 三年 OLS 的 `1-sigma` 目前把 orbit mean 當獨立點；orbit-to-orbit residual 實際相關，且 rate 非恆定。 | 對 unbiased zero-mean error 不必然偏移 slope，但會低估不確定度；缺資料若與 epoch/solar condition 相關，則方向未知。 | **不會單獨製造 76 km 變化；會讓 `0.047 m/day` 這類內部 sigma 過度樂觀。** | 用 moving-block bootstrap 或按 day/week block jackknife；分年、分 season、分 source 和 leave-one-chunk-out 報 slope spread。 |
| quantity 比較錯位 | `a` 是 mean semi-major axis，不是單點 altitude；不同 mean-element theory、TLE mean motion、quiet-time rate 與全期 OLS 不是同一 observable。 | 不適用。是比較契約問題。 | **可解釋「和 2 m/day 不同」的表面矛盾，但不能替本資料定量辯護。** | 對外部值建立 `{satellite, time range, input orbit product, a/altitude definition, averaging window, maneuver policy}` 對照表後才比較。 |

## 來源能支持的邊界

- Orekit 的 [BrouwerLyddanePropagator API](https://test.orekit.org/site-orekit-development/apidocs/org/orekit/propagation/analytical/BrouwerLyddanePropagator.html) 明定模型是 J2 至 J5 zonal harmonics；`M2=0` 不考慮 along-track secular effects，且 osculating-to-mean 結果同時依 gravity field 與 `m2Value` 決定。這證明目前 `mean_semi_major_axis_m` 是特定模型的 mean element，不證明它的三年 bias 有多少。
- ESA/TU Delft 的 [SP3xCOM product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html) 明定資料為 ITRF dynamic position/velocity、GPS 10 s、position few-cm 3D，而 quality report 為獨立 `SP3xVAL_2_`。因此「raw SP3 連續」不能替代 POD quality validation。
- IERS 的 [Conventions 2010](https://www.iers.org/SharedDocs/Publikationen/EN/IERS/Publications/tn/TechnNote36/tn36.pdf?__blob=publicationFile&v=2) 將 terrestrial/celestial transformation 視為含 Earth rotation、polar motion 與 celestial-pole terms 的時間相依轉換。frame/time check 是硬 correctness test，不是可用 OLS 吸收的小噪音。
- Li & Lei 的 [POD energy integration 原始研究](https://doi.org/10.1029/2020SW002664) 以 EGM2008 degree 120、Sun/Moon、IERS2010 tides 與 ocean tide 做 time-varying potential work。該工作支持「需獨立完整力模型對照」，不支持把其 event-level performance 數字直接套成此三年 B-L slope 的誤差。

## ESA 可取得的比對資料

目前 `SP3ACOM` 不是唯一可讀取的 ESA 軌道產品，但每個候選能回答的問題不同。

| 產品 | 官方路徑 | 可以檢查 | 不能宣稱 |
|---|---|---|---|
| `SP3ACOM_2_` reduced-dynamic | [RD 最新 baseline](https://swarm-diss.eo.esa.int/#swarm/Level2daily/Latest_baselines/POD/RD) | 目前研究的原始位置、速度與長期趨勢。ESA 定義為 COM 的 ITRF `r,v`；每個 daily batch 使用 30 h input，輸出 central 24 h。 | 它本身不是獨立驗證。 |
| `SP3AVAL_2_` validation | [VAL 最新 baseline](https://swarm-diss.eo.esa.int/#swarm/Level2daily/Latest_baselines/POD/VAL)；[整個 mission archive](https://swarm-diss.eo.esa.int/#swarm/Level2daily/Entire_mission_data/POD/VAL) | 對應日期的 POD fit 品質、GPS visibility、post-fit residual 與 empirical acceleration 圖。2025-02-01 sample 是 9-page PDF，第二頁為 post-fit residual、clock offset 與 empirical acceleration。 | 它不是另一條外部軌跡，不能單靠它重算獨立的三年 decay slope。 |
| `SP3AKIN_2_` kinematic | [KIN 最新 baseline](https://swarm-diss.eo.esa.int/#swarm/Level2daily/Latest_baselines/POD/KIN) | ESA 定義為 COM 的 ITRF kinematic position time series。可用同一期間的 raw radius、perigee/apogee 或 phase-defined mean 做第一個不同 orbit-solution 路線的趨勢交叉檢查。 | 與 RD 同屬 ESA POD 資料鏈，不是外部 mission 或完全獨立觀測。KIN 僅是 position，不能直接套用現有含 velocity 的 B-L 計算。 |
| `MODA_SC_1B` preliminary medium-accuracy OD | [MOD 最新 baseline](https://swarm-diss.eo.esa.int/#swarm/Level1b/Latest_baselines/MODx_SC) | 檢查資料讀取、時間與 ITRF geometry 是否出現明顯量級錯誤。 | ESA 將它列為 `SP3ACOM` 的 input，不可稱為獨立 POD validation。 |

ESA official product catalogue 明定 `SP3xVAL_2_` 是 `SP3xCOM_2_` 的正式 quality indicator，而非 HDR 中的 `Product_Err` 或 `Quality_Indicator` 欄位。可直接下載任一日的 validation archive，例如：

`https://swarm-diss.eo.esa.int/?do=download&file=swarm%2FLevel2daily%2FLatest_baselines%2FPOD%2FVAL%2FSat_A%2FSW_OPER_SP3AVAL_2__20250131T235942_20250201T235942_0203.ZIP`

同日 RD 與 KIN 只需把 path 的 `VAL` 和 filename product tag 分別改為 `RD`/`SP3ACOM`、`KIN`/`SP3AKIN`。ESA public listing 確認 POD 下有 `RD`、`KIN`、`VAL` 三條資料線，各含 `Sat_A`。

本地研究期的 SP3 headers 全為 `File_Version=0203`；抽樣顯示 2023--2025 檔案是在 2026-08 產生，代表使用了後來重處理的輸出。這只能證明「同版號、含重處理」，**不能**說明 0203 改了什麼，也不能據此假定趨勢被調高或調低；截至 2026-10-20 未找到 ESA 公開的 0203 change log 或 reprocessing release note。

## 本次 KIN position-only cross-check

以 13 個完整 `0203` KIN 日檔（2023-07 至 2026-06，跨起點、2024、2025 與終點）直接讀 SP3 `x,y,z`，並和同日 RD 比較。此檢查不使用速度、ITRF/GCRF 轉換或 mean-element model。

| 幾何量 | KIN slope | 同日 RD slope | KIN-RD 每日差 |
|---|---:|---:|---:|
| 近地點半徑 | `-66.64 m/day` | `-66.64 m/day` | `-0.19..0.00 m` |
| 遠地點半徑 | `-66.06 m/day` | `-66.06 m/day` | `+0.01..+0.11 m` |

13 日不是完整三年正式統計，故它的 `-66 m/day` 不取代 RD 全期 `-69.46 m/day`。它回答的是較窄但關鍵的問題：同日期的 KIN 與 RD 位置幾何在公分至分米內一致，並同時保留約 `-66 m/day` 的跨期下降；RD 專有的 reduced-dynamic 微調不是這個量級的來源。

## 同 source 的外部可重現性

Ram et al. 的 [Swarm-A 事件研究](https://doi.org/10.1029/2026GL125768) 也以 `SP3xCOM` 的 daily least-squares orbit-mean semi-major axis 做 rate。對相同事件日，本地 B-L raw daily OLS 能重現其量級與時間變化：

| 事件日 | Ram et al. `m/day` | 本地 `m/day` |
|---|---:|---:|
| 2024-05-04 | -19.91 | -23.69 |
| 2024-05-07 | -42.43 | -45.03 |
| 2024-05-11 | about -170 | -173.15 |
| 2026-01-31 | -79.43 | -69.74 |
| 2026-02-02 | -83.44 | -77.78 |
| 2026-02-03 | -96.28 | -83.81 |
| 2026-02-05 | -106.45 | -91.52 |

這是 estimator 與產品量級的 cross-check，不是獨立 source validation；差異可來自日界、產品版本與 mean-element implementation。它不能證明三年 `-69.46 m/day` 是純 drag，也不能取代 `SP3AKIN` 與 `SP3AVAL` 的逐期檢查。

## 最小驗證順序

```text
1. 同期 `SP3AKIN`：先用不需 velocity 的 raw radius/perigee/apogee 比較三年 slope；若一致，再決定是否為 KIN 建立有明確 velocity policy 的 mean-element estimator。
2. `SP3AVAL`：下載並彙整研究期 daily report 的 residual、visibility 與 empirical-acceleration anomaly；這是 POD 品質篩選，不是重算軌道。
3. maneuver/campaign exclusion and external rate comparison contract
4. B-L model sensitivity: M2=0 vs a documented sensitivity range vs independent estimator
5. frame/time/PV round-trip + independent transform
6. phase-boundary/coverage sensitivity
7. block-bootstrap and split-period slope spread
```

在 1--5 前，`-69.46 m/day` 只能報為目前 estimator 的 descriptive trend。不能用 OLS 的內部
`1-sigma` 宣稱它已與 `2 m/day` 有顯著衝突，也不能先把差異全部歸因於 atmospheric drag。
