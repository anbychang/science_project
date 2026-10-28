# 軌道衰減擬合方法研究

狀態：早期方法研究。下文的 daily OLS 與 centered 12/24 h 結果不是現行
P1.5.6 v2；現行方法是逐 10 秒右端點回看完整 3／5 個 phase orbit 的 raw B-L／joint H2/H3
局部 OLS，見 [現行執行計畫](phase_1_execution_plan.md)。

## 決定

正式論文對照保留「完整 phase 定義的逐圈平均 `a`，再對每一 UTC day 的逐圈平均值做 ordinary
linear least-squares slope」。這是當時找到、最貼近 Swarm-A 精密星曆的已發表做法。當時的探索表另輸出
centered 12/24 h local OLS，僅用於觀察日內時間結構，不能取代 daily OLS 的文獻對照地位。

逐圈 bin 必須由 unwrapped `u = mean_argument_of_perigee_rad + mean_anomaly_rad` 或
mean longitude 的完整 `2*pi` phase coverage 定義，不可沿用固定 UTC 10-minute bins。若
一個 bin 真正覆蓋完整一圈，H2/H3 對該圈平均理論上會互相抵消；這正是先測它的原因。

H2/H3 的聯合趨勢/諧波回歸是**第二條 candidate sensitivity analysis**，不是已被 Swarm
論文直接驗證的主方法：

```text
a(t) = trend(t)
     + c2(t)*cos(2*u) + s2(t)*sin(2*u)
     + c3(t)*cos(3*u) + s3(t)*sin(3*u)
     + residual(t)
```

它可用來量化未被逐圈平均消除的 phase residual；不得先扣固定正弦波再做差分。若啟用，
`trend(t)` 與諧波係數均採分段線性表示並以二階差分 Tikhonov regularization 控制平滑。

這是 estimation 方法，尚不是「已乾淨量到地磁暴造成的衰減」。maneuver、source 邊界、
POD method anomaly 仍需保留為 flags。

當時 P1.5.4--P1.5.6 在三年 working copy 寫出 16,843 complete-orbit mean、3 個 H2/H3
chunk diagnostic、1,096 daily OLS，以及 16,825 個 12 h 和 16,807 個 24 h local OLS。這些都是
descriptive candidate，不進 P1.6/P1.7。

## 本專案的已知輸入

- P1.5.5 的完整 orbit Fourier projection 顯示：三個 chunk 的 H2 amplitude median 為
  57.829--70.577 m；H3 amplitude median 為 39.208--40.030 m。這些是 phase-orbit table 的
  diagnostic，不是直接的 drag amplitude。
- 每日以固定 phase H1--H5 擬合後，殘差標準差仍約 41 m。故 H2/H3 是 B 路線中最有根據的
  candidate nuisance terms，但不是完整物理模型；A 路線仍須先驗證逐圈平均是否已充分消除它們。
- B-L 轉換目前使用 J2--J5 且 `M2 = 0`。Orekit 明確說明 osculating-to-mean 的結果取決於
  所輸入的 gravity field 和 `M2` drag 參數；其轉換以 fixed-point iteration 求解。
  [Orekit `BrouwerLyddanePropagator` 原始 API/source](https://test.orekit.org/site-orekit-12.0.1/jacoco/org.orekit.propagation.analytical/BrouwerLyddanePropagator.java.html)

因此，殘留諧波不能直接命名為 drag 或地磁暴訊號。

## 原始研究與可轉用部分

| 原始來源 | 論文/方法實際做法 | 適用條件 | 對 B-L H2/H3 的轉用判定 |
|---|---|---|---|
| [Walter, Mercea, Arnold, Jaeggi, 2025，Bern EGU poster](https://www.bernese.unibe.ch/publist/2025/post/Walter_Poster_EGU25.pdf) | 用 `a(t) = a_bar(t) + sum_r(mu_r(t)*sin(omega_r*t) + eta_r(t)*cos(omega_r*t))` 同時估計 time-varying trend 與 periodic variations；`a_bar`、`mu`、`eta` 全部用 piecewise linear representation，10 subintervals/day；對各係數加二階差分 Tikhonov constraint。orbital decay 定義為 `d a_bar / dt`。該研究明示資料含 Swarm-A、reduced-dynamic POD，並將 Earth gravity、radiation pressure、third bodies 視為擾動來源。 | 頻率集合必須先由 spectrum 或物理 phase 檢驗決定；regularization 強度需要 simulation 與 held-out windows 校準。該作者也明示：過強約束會低估 storm peak，低約束則產生大變異；未建模長週期與 maneuvers 是限制。 | **可直接轉用核心估計架構。** 本專案不應照抄固定 `omega_r*t`：Swarm period 隨高度變，已驗 H2/H3 是 phase-locked，故以 `cos(k*u)`、`sin(k*u)` 取代固定 time-frequency；先只放已驗 H2/H3。分段 trend + time-varying coefficients + 聯合解是直接可用。 |
| [Ram et al., 2026，GRL，Swarm-A](https://doi.org/10.1029/2026GL125768) | 由 `SW_SP3xCOM_2_` 精密星曆取得 orbit-mean semi-major axis；每天對 orbit-mean `a` 做 linear least-squares fit，slope 為 daily decay rate，並以 fitted slope 的 1-sigma standard error 報告不確定度。 | 每一圈必須有完整 phase coverage，且要排除 maneuver、資料品質異常與不完整圈。原文未交代其 phase variable、circle boundary 或 weighting。 | **可直接轉用方法順序：先逐圈平均、再 daily OLS。** 不可聲稱原文指定了我們的 `u` 定義；`u` 是本專案為保證完整 phase coverage 的實作選擇。先比較逐圈平均後的 H2/H3 是否消失，再判斷是否需要 H2/H3 regression。 |
| [Li & Lei, 2021，Space Weather](https://doi.org/10.1029/2020SW002664) | 不靠平滑或 harmonic fit，而是以 POD 在 ECI 下計算含 central/non-spherical gravity、Sun/Moon 與 time-varying potential 的 mechanical-energy change；time-varying potential 用沿軌 force work 的數值積分，星曆先做 8-point Lagrange piecewise interpolation。文中使用 EGM2008 120-order、DE405、IERS2010 solid/pole tide、EOT ocean tide。 | 需要完整力模型與一致的 ECI state；結果需用 accelerometer 或獨立解驗證。作者特別指出：在低密度/高高度，近似 analytic potential 會造成很大的 rate 誤差；其 Swarm-B 範例可出現符號錯誤。 | **不可直接轉用到本輪資料處理。** 現有 B-L J2--J5、`M2 = 0` 不是該完整 force/energy model。這應是未來的獨立驗證路線，而不是把 H2/H3 直接解釋成完整 conservative-force correction 的證據。 |
| [Orekit B-L conversion 原始 API/source](https://test.orekit.org/site-orekit-12.0.1/jacoco/org.orekit.propagation.analytical/BrouwerLyddanePropagator.java.html) | `computeMeanOrbit` 將 osculating orbit 轉成 B-L mean orbit；文件明示轉換所移除的 short-periodic variation 與輸入 gravity field、empirical drag `M2` 有關，且以 fixed-point iteration 求 mean parameters。 | mean elements 只對其指定的 averaging theory/force content 有意義；不同 gravity field 或 `M2` 會得到不同 mean orbit。 | **直接轉用為方法邊界。** H2/H3 是目前 B-L definition 下的殘留，不能把擬合相減誤稱為換成了真實 mean orbit，也不能跳過 independent validation。 |

## 建議的驗證順序

### A. 主實驗：phase-defined orbit mean + daily OLS

1. 在單一 `chunk_id` 內 unwrap `u` 或 mean longitude。
2. 每跨越一個完整 `2*pi` phase interval 建立一個 orbit bin；只接受資料覆蓋完整、無 source/
   maneuver boundary、且 sample gap 合格的圈。
3. 對該圈的 `mean_semi_major_axis_m` 算平均，保存 `{orbit_start, orbit_end, orbit_mean_a_m,
   phase_coverage, sample_count, flags}`。
4. 每 UTC day 對可用逐圈 `orbit_mean_a_m` 做 ordinary least squares，輸出 slope 與 fitted
   slope 的 1-sigma standard error。
5. 比較逐圈平均前後的 H2/H3 phase fold、periodogram 和 slope distribution；若 H2/H3 沒有被
   足夠抑制，才進入 B。

這一實驗直接檢驗「已發表 Swarm 做法是否足以處理本資料的殘留」，而非假設答案是 H2/H3
regression。

### B. 僅在 A 失敗時：joint phase-harmonic sensitivity fit

#### 分段與資料邊界

- 一個 `chunk_id` 一個 block，嚴禁跨 chunk。
- source 邊界、已知 maneuver/campaign、POD rejection 或長 gap 分成不同 block；不靠 fit 把
  discontinuity 平滑掉。
- 建議 knots 先沿用文獻量級：每 2.4 小時一個（10/day）。這只是起點，必須用 synthetic
  injection、quiet windows、storm windows 做 sensitivity test。

#### 設計矩陣

每一筆 10-second mean element 的 row 具有：

```text
time_s, mean_semi_major_axis_m, u_rad, chunk_id, source_id, flags
```

`trend(t)` 使用線性 spline basis `B[j](t)`；H2/H3 的係數也使用同一組 basis：

```text
a_hat(t) = sum_j B[j](t) * trend_level[j]
         + sum_j B[j](t) * (
             h2_cos[j]*cos(2*u) + h2_sin[j]*sin(2*u)
           + h3_cos[j]*cos(3*u) + h3_sin[j]*sin(3*u)
           )
```

本形式等價於 Walter et al. 的 time-varying amplitudes，但 phase 使用已驗證的 mean
argument-of-latitude，而非固定 minutes-period sinusoid。

#### 約束與估計

對每一條係數序列 `x[j]` 加：

```text
x[j+1] - 2*x[j] + x[j-1] ~= 0
```

解 regularized least squares：

```text
min ||W * (a - X*b)||^2 + lambda_trend*||D2*trend||^2
                         + lambda_h2*||D2*h2||^2
                         + lambda_h3*||D2*h3||^2
```

- `lambda` 不可憑圖手選。以注入已知 storm-like trend 的 synthetic series 校準，再以 withheld
  windows 驗證。
- 不要在第一版放 H1/H4/H5；它們尚未有 H2/H3 等級的相位驗證，會提高 trend 被吸收的風險。
- 不要預先扣 daily fitted phase model 再 fit slope；同一個 least-squares problem 聯合估，才能在
  covariance 中看到 trend 與諧波是否不可分辨。

#### rate 與不確定度

- 每個 knot interval 輸出 `trend_slope_m_s` 與 `trend_slope_m_day`。
- 從 regularized normal matrix 或 block/bootstrap 取得 slope uncertainty；同時輸出 residual RMS、
  effective sample count、H2/H3 amplitude，以及 condition diagnostic。
- 報表可另外按 UTC day 做 weighted mean rate，格式與 Ram et al. 一致：daily slope 與 1-sigma，
  但它是 candidate rate，不取代原始 candidate intervals。

## 方法選單

下表是可選方法，不是全部都應實作。`吃掉 storm transient` 指估計器可能把真實、數小時到數天的
快速衰減變化當成 noise、periodic term 或過度平滑的 trend 而壓低。

| 方法 | 原始論文或官方來源 | 輸入 -> 輸出 | 主要假設 | 吃掉 storm transient 的風險 | 對目前 2023--2026 B-L table 的適用性 |
|---|---|---|---|---|---|
| **完整逐圈平均 + daily OLS** | [Ram et al. 2026, GRL](https://doi.org/10.1029/2026GL125768)：Swarm-A `SW_SP3xCOM_2_` 的 orbit-mean `a`，每一天 linear least-squares slope，並報 slope `1-sigma`。 | 完整逐圈 phase coverage 的 `mean_a` -> 每日 slope、`1-sigma`。 | 圈平均能壓低 orbit-period terms；每日 trend 可近似線性；排除 maneuver、不完整圈與不良 POD。 | **低到中。** 單日 OLS 不會主動平滑日內 storm slope，但把一天強迫成直線，會看不見日內結構。 | **最適合，先做。** 以 `u` 或 mean longitude 劃完整 `2*pi` 圈；先驗證 H2/H3 是否相消。原文沒有指定我們的 phase variable 或圈界。 |
| **固定週期濾波／平滑後微分** | [Savitzky & Golay 1964](https://doi.org/10.1021/ac60214a047) 定義局部 least-squares smoothing/differentiation；這是通用原始方法，非 Swarm orbital-decay 論文。 | 規則取樣 `a(t)`、固定 window/order -> smooth `a` 或 numerical derivative。 | 訊號在視窗內可由低階多項式表示；視窗寬度可分開 noise/週期項與真實 trend。 | **高。** 視窗若接近 storm 時間尺度，peak slope 會被壓低；固定 46/32-minute notch 也可能在 period 漂移時留下或扭曲殘留。邊界處尤其不可靠。 | **不適合作正式方法。** 可只用在 figure/diagnostic，或做敏感度下界；不可寫入正式 candidate decay table。 |
| **固定 harmonic regression** | [Walter et al. 2025, Bern EGU poster](https://www.bernese.unibe.ch/publist/2025/post/Walter_Poster_EGU25.pdf) 的 sinusoid-plus-trend 模型是此法的直接母式；將其 `mu_r(t)`、`eta_r(t)` 固定為常數即為固定 harmonic regression。 | `a(t)`、固定 frequencies 或 `u` phase -> 線性 trend + cosine/sine amplitudes。 | 頻率、振幅、相位在擬合區間內固定；諧波與 trend 可辨識。 | **中到高。** 若振幅隨季節改變，固定項會把不匹配殘差漏進 trend；若 fitting window 太短，storm transient 可被 sinusoid basis 吸收。 | **不適合作主方法。** 可在 quiet windows 確認 H2/H3；不可用單組係數套用三年。 |
| **phase harmonic regression** | [Walter et al. 2025](https://www.bernese.unibe.ch/publist/2025/post/Walter_Poster_EGU25.pdf) 支持 trend 與 periodic terms 聯合估計；以 `cos(k*u)`、`sin(k*u)` 取代其 `sin(omega_r*t)` 是本專案針對 phase-locked H2/H3 的推論，非論文原式。 | 完整 mean-element `a(t), u(t)` -> trend、H2/H3 amplitudes、residual。 | `u` 是殘留的正確 phase；只放已驗證 H2/H3；係數在窗內近似穩定。 | **中。** 同時估計比先扣再回歸好，但若 phase basis 與 storm sampling 有共線性，trend 仍可能被吃掉。 | **適合作 A 失敗後的 sensitivity analysis。** 需 held-out phase-fold、synthetic injection 與 covariance/condition diagnostic；不能稱文獻標準 Swarm 作法。 |
| **time-varying harmonic spline + Tikhonov** | [Walter et al. 2025](https://www.bernese.unibe.ch/publist/2025/post/Walter_Poster_EGU25.pdf)：piecewise-linear trend 和 time-varying periodic amplitudes，10 subintervals/day，以二階差分 Tikhonov constraint；作者明示約束過強會低估 storm peak，過弱會造成大變異。 | `a(t)`、periods/phase、knots、weights -> smooth trend slope 與 time-varying harmonic coefficients。 | 真實 trend 與諧波係數皆隨時間平滑變化；regularization strength 能經 simulation/held-out data 校準。 | **可高。** `lambda` 過大直接壓低 transient；過小則把 noise 當成 decay。 | **只適合第二階段研究。** 目前可用 H2/H3 建模，但 A 的完整逐圈平均與 daily OLS 必須先作對照。 |
| **state-space / Kalman filter** | [Battin 1963, JPL Technical Report 32-498](https://ntrs.nasa.gov/api/citations/19630013925/downloads/19630013925.pdf) 說明 weighted least squares、Schmidt-Kalman 與 orbit-determination state estimation 的關係；[NASA TM-2005-213758](https://ntrs.nasa.gov/api/citations/20050186564/downloads/20050186564.pdf) 說明 sequential/extended Kalman orbit estimation。 | 時序觀測、明確 state transition、measurement covariance `R`、process covariance `Q` -> filtered/smoothed state、covariance、可選 rate state。 | 動力學與觀測誤差模型正確；`Q`/`R` 有物理或外部校準；maneuver 可被明確建模。 | **高且難審計。** 小 `Q` 會把 storm 當 noise 壓平；大 `Q` 則把 POD anomaly 當成 state change。 | **目前不適合。** B-L table 沒有 measurement covariance、完整 force model 或 maneuver schedule；直接套 filter 只是在把主觀平滑藏進 `Q`。 |
| **POD mechanical-energy / force-work numerical integration** | [Li & Lei 2021, Space Weather](https://doi.org/10.1029/2020SW002664)：用 ECI trajectory 上 gravity-force work 的數值積分取得 time-varying potential；使用 8-point interpolation、EGM2008 degree 120、DE405、IERS2010、EOT tides。 | 高頻 ECI position/velocity + 完整 gravity/tide/Sun/Moon models -> non-conservative energy change、orbital decay/rate。 | conservative potentials 已充分建模；時間系統/座標一致；數值積分與 force model 可驗證。 | **低。** 目標正是分開 conservative work；但錯誤 force model 仍會殘留假 signal。 | **目前不適合直接跑。** 現有 B-L J2--J5、`M2 = 0` table 不含所需完整 force accounting；這是未來獨立 reference/validation 路線。 |
| **POD non-conservative acceleration / density 推導** | [van den IJssel et al. 2016](https://doi.org/10.1186/s40623-016-0474-5) 以 Swarm GPS kinematic orbits 作 pseudo-observations，co-estimate body-frame 3D piecewise-linear non-gravitational accelerations（10-min resolution）；[van den IJssel et al. 2020](https://doi.org/10.1016/j.asr.2020.01.004) 將 POD-derived aerodynamic acceleration 轉為 ESA Swarm Level-2 density/acceleration products。 | GPS POD/kinematic orbit、attitude、mass/area、gravity/radiation models -> non-gravitational/aerodynamic acceleration、density，再以 Gauss/energy relation 得 rate。 | 非重力 acceleration 可從完整 POD dynamics 分離；attitude、surface/mass 與 radiation-pressure correction 足夠準。 | **低到中。** 不以時間濾波為主要分離手段；但 10-min piecewise model仍會限制更快變化，且 maneuver/radiation error 可混入。 | **目前不能由 B-L table 重建。** 若改用官方 DNSxPOD/ACC product，可作外部驗證或後續 physical route；不能把密度反推結果當成本表的內生校正。 |
| **TLE mean-motion / ballistic-coefficient 方法** | [Picone et al. 2005, JGR](https://doi.org/10.1029/2004JA010585) 用 TLE/SGP 資料推 thermospheric density，並明示 `B*`/mean-motion terms 是 orbit determination fitting parameters；[CelesTrak SGP4 tutorial](https://celestrak.org/software/tutorials/sgp4.php) 說明 GP elements 是以 SGP4 differential corrector 配適觀測得到的 doubly-averaged elements。 | TLE epoch、mean motion、`B*`/mean-motion derivatives -> 粗略 `a` proxy、drag/density proxy 或 ballistic-coefficient fit。 | TLE 與同版本 SGP4 搭配；fitted `B*` 代表可用 drag proxy；資料解析度足以觀察目標訊號。 | **中到高。** TLE 時間稀疏、模型簡化，且 fitted `B*` 可吸收未建模 force error；不適合分辨短 storm structure。 | **不適合主分析。** 可在有歷史 TLE 時做低精度外部 sanity check；不得與公分級 Swarm POD/B-L `a` 混用或把 `B*` 當物理 ballistic coefficient。 |

### 選擇結論

現在只值得排程兩件事：

1. A：`phase-defined orbit mean -> daily OLS slope + 1-sigma`，以現有完整三年 mean-element table
   完成並驗證。
2. 若 A 未充分移除 H2/H3，才做 B：time-varying H2/H3 joint fit；把它保留為與 A 並列的
   candidate sensitivity result。

其他選項不是現在資料可支持的快捷校正：濾波、Kalman、TLE 都會增加不可驗證的模型選擇；
energy/acceleration 方法則需要另一條完整 POD dynamics 或官方產品資料管線。

## 必須驗證，否則停止

1. **完整圈驗證**：每個 orbit bin 的 phase coverage、gap 與邊界條件都合格；先確認逐圈平均
   對 H2/H3 的抑制是否符合預期。
2. **相位驗證**：若進入 B，H2/H3 的 amplitude/phase 在 held-out quiet windows 仍可重現；不得只看
   in-sample RMS。
3. **頻譜驗證**：逐圈平均或 B 校正後，在 `2*u` 和 `3*u` 的 folded residual/periodogram 明顯下降。
4. **trend 保留**：注入已知慢速 decline 與 storm-like transient 後，recover 的 slope 不偏；
   尤其要測 trial `lambda` 是否壓低 storm peak。這是 Walter et al. 明示的風險。
5. **邊界驗證**：source/maneuver boundaries 不產生被 spline 連接的假 slope。
6. **對照輸出**：保留既有 backward 3/6/12h rate，與新 candidate rate 並列；只能描述差異，
   不可刪除舊資料或覆寫。

## 不應做的事

- 不以固定 46 或 32 分鐘正弦波套用全三年；H2 振幅已有季節性，且 orbital period 會改變。
- 不因 fit 後曲線較平就稱已排除地球重力、POD 誤差或 maneuver。
- 不把 Li & Lei 的 force/energy 積分方法簡化成現有 B-L output 後就宣稱等價。
- 在 maneuver/source/method anomaly 校準前，不將 candidate rate 用作地磁暴因果結論。

## 來源範圍

只採用原始研究論文、研究團隊公開的原始方法文件與 Orekit 官方 source/API；沒有以
二手教學文章決定方法。
