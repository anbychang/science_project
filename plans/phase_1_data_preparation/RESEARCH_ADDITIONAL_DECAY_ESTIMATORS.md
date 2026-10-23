# 磁暴事件的額外 orbit-decay 估計選項

## 結論

沒有一個「更高級」的方法能同時給出乾淨的長期 decay、數小時 storm onset、物理 drag，且不引入新假設。
對目前的 B-L mean-element 表，較好的做法不是再加一個日平均，而是把完整逐圈平均後的
`orbit_mean_a_m` 視為共同輸入，針對兩個問題使用不同輸出：

```text
B-L mean elements
  -> 完整 phase 的逐圈 mean a
  -> [事件段落 OLS]：事件前 / main phase / recovery 的 slope
  -> [置中 rolling OLS]：連續時間的 slope 圖
  -> [H2/H3 joint fit]：只在逐圈平均殘留仍明顯時的 sensitivity
```

- **事件主結果**：外部定義斷點的 segmented OLS。斷點來自事先規則的 SYM-H/Ap event catalog，
  不是從 `a` 曲線挑出來。這避開 UTC 日界，也不把 storm onset 平滑成一整天。
- **連續圖與 timing**：以每一完整 orbit 為中心的 12 h 與 24 h rolling local-linear OLS。每個
  slope 的 timestamp 是窗口中心，不是 UTC date；12 h/24 h 併列是 sensitivity，而非獨立樣本。
- **不是主結果**：LOESS、L1 trend filtering、內生 change-point detection 都可檢查結果形狀，
  但它們的 span、penalty 或斷點數會改變 storm peak。

上述前三點是本專案資料與下列原始方法文獻交叉後的**專案推論**，不是任何一篇 Swarm 論文已
直接驗證的完整 recipe。已發表 Swarm-A direct case 的 daily OLS 仍要保留為論文對照，不應刪除。

## 先釐清三種不同問題

| 要回答的問題 | 合適輸出 | 不合適輸出 |
|---|---|---|
| 某個磁暴 main phase 比前期多大的 decay？ | 事件邊界固定後，各段的 OLS slope 與 interval | 一個跨過事件邊界的 24 h slope |
| decay 何時開始改變、峰值約在何時？ | 置中 rolling local-linear slope，並標記窗口寬度 | UTC-day slope；其日界沒有物理意義 |
| 長期 daily decay 能否和 Swarm 文獻相比？ | 完整逐圈 mean `a` 的 fixed UTC-day OLS | rolling slope 或 filtered curve |
| 非保守力或 density 是否造成變化？ | 獨立 POD acceleration/density 或完整 energy-work 模型 | 僅由 B-L `a` 的時間平滑推論 |

## 可新增但值得控制的選項

### 1. 外部斷點的 segmented linear regression

若事件期間沒有 maneuver 或資料方法切換，較乾淨的形式是 continuous broken-line：

```text
A(t) = b0 + b1*t
     + d0*max(0, t - T0)
     + d1*max(0, t - T1) + residual
```

`T0`、`T1` 是預先定義的 onset/recovery knot；各段 slope 分別是 `b1`、`b1 + d0`、
`b1 + d0 + d1`。這會強制 `A(t)` 在 knot 連續。若 knot 同時是已知 maneuver、source 或
method boundary，不能用這個式子硬接：應先切成不同 valid segment，各自估計。

例如 event catalog 可先定義 `{pre, onset, main, recovery}` 的時間邊界；每段只使用完整、品質
合格的 orbit mean。輸出是每個物理事件段一個 `rate_m_day`，不是每一天一個值。

**原始來源事實：**Muggeo 給出 segmented regression 中 break-point estimation 的迭代方法；Bai
與 Perron 提出多重 structural-change linear model 的斷點與各段參數估計，並處理斷點日期的
confidence interval。兩者證明 segmented linear model 是有正式推論框架的估計問題；都不是
Swarm 論文，也沒有規定本專案的 geomagnetic event boundary。
[Muggeo 2003, Statistics in Medicine](https://doi.org/10.1002/sim.1545)
[Bai & Perron 2003, Journal of Applied Econometrics](https://doi.org/10.1002/jae.659)

**本專案推論：**這是目前最適合 event-level 主表的補充。斷點必須由 `a` 以外的資料與規則
在看 response 前凍結；否則會把資料內的 noise、maneuver 或 POD method change 選成「storm」
break，且選點後的 slope uncertainty 會過度樂觀。

**限制：**它不產生每一個 orbit 的連續 decay rate，也不能把同一段內的非線性變化變成可識別
訊號。段長若只含少數完整 orbit，就只應標為 insufficient，不應強行輸出斜率。

### 2. 置中 rolling local-linear OLS

在每一個完整 orbit 的中心時刻 `t0`，只用同一個 valid segment 中的資料做：

```text
a(t) = intercept[t0] + rate[t0] * (t - t0) + residual
window = [t0 - W/2, t0 + W/2]
```

`rate[t0]` 直接是該中心時刻的局部 slope；`W = 12 h` 和 `24 h` 可平行輸出。離線事件研究可用
置中窗口；若真的要模擬當時可得資訊，才改成 backward window `[t0 - W, t0]`。兩者不可混稱。

**原始來源事實：**Cleveland 與 Devlin 將 local regression 定義為在移動的局部鄰域做加權
least-squares fit，藉此估計不必是全域多項式的 regression surface，也討論 smoothness 與
bias-variance 的取捨。
[Cleveland & Devlin 1988, JASA](https://doi.org/10.1080/01621459.1988.10478639)

**本專案推論：**對本表，先逐圈平均後以時間線性、等權 OLS 做 local fit 即足夠；不需要再加
LOESS kernel 才能移除 UTC 日界。以 12 h/24 h 同時輸出可以直接量出 window 選擇造成的 peak
timing/height 差異。這不是獨立觀測序列：相鄰窗口大幅重疊，後續 correlation 或 event test
不可把每一個 rolling rate 當獨立 `N`。

**限制：**所有固定窗口都會平均掉比 `W` 更短的變化。這是 estimator 的解析度，不是資料真的
沒有瞬態；窗口不得跨 maneuver、source boundary、長 gap 或預先標記的 method anomaly。

### 3. L1 trend filtering

對等間隔序列，估計一條接近原觀測但傾向 piecewise-linear 的 trend：

```text
min sum((a[i] - trend[i])^2) + lambda * sum(abs(D2 trend[i]))
```

斜率在 knot 之間固定，knot 是資料選出的 slope change。

**原始來源事實：**Kim、Koh、Boyd、Gorinevsky 提出的 L1 trend filtering 以 L1 penalty 取代
Hodrick-Prescott 的平方 penalty，產生 piecewise-linear trend；文中將 kink/knot 解釋為 underlying
dynamics 的 abrupt change，並給出線性成長的專用計算方法。
[Kim et al. 2009, SIAM Review](https://doi.org/10.1137/070690274)

**本專案推論：**若想找「何時可能改變」而不先指定事件邊界，它比二階 L2 spline 較可能保留尖銳
slope change，可作 segmented OLS 的 sensitivity diagnostic。

**限制：**`lambda` 決定 knot 數與 peak 高度；把它直接當正式 storm onset 會形成 data-driven
selection bias。等間隔需求也表示要先在不跨 gap 的每個 segment 建規則序列。現有 10 s raw
mean `a` 的 H2/H3 未先處理時不宜直接餵入；優先用完整 orbit mean。

### 4. Change-point detection 只用於 QC 與候選邊界

PELT 可在帶 penalty 的 cost 下找出多個 change points，目的就是選 breakpoint location 與數量。

**原始來源事實：**Killick、Fearnhead、Eckley 的 PELT 演算法對這類 penalized change-point cost
找全域最小解；在其條件下計算成本可達線性。
[Killick, Fearnhead & Eckley 2012, JASA](https://doi.org/10.1080/01621459.2012.737745)

**本專案推論：**可對 orbit-mean residual 做 PELT，產生要人工對照 maneuver/source/quality flag
的候選時間。它不能證明地磁暴造成斷點，也不應用同一條被 PELT 選段的資料直接報正式 storm
slope；較安全的流程是先用它補 QC flag，再以外部 event boundary 估計。

### 5. 改善 uncertainty，不改變 slope：HAC 或 block bootstrap

這兩種不是新的 decay estimator，而是避免把相鄰 orbit mean 誤當 i.i.d. 後，OLS `1-sigma`
過小的 uncertainty sensitivity。

**原始來源事實：**Newey 與 West 提出 heteroskedasticity- and autocorrelation-consistent
covariance estimator，目標是讓回歸係數 covariance matrix 在一般條件下保持一致；它本身不改變
已配適的 OLS slope。
[Newey & West 1987, Econometrica；NBER 原始 working paper](https://www.nber.org/papers/t0055)

**原始來源事實：**Kunsch 將 bootstrap/jackknife 延伸到一般 stationary sequence，以連續 block
抽樣而非把 observations 當 i.i.d.。
[Kunsch 1989, Annals of Statistics](https://doi.org/10.1214/aos/1176347265)

**本專案推論：**當一個估計窗口含足夠 orbit mean 時，可把 HAC 或 moving-block bootstrap 的
interval 和傳統 OLS `1-sigma` 並列。短事件段通常只有約數個到十餘個 orbit，這些大樣本近似
方法未必穩定；不可因多跑一個 standard error 公式就聲稱 uncertainty 已解決。

### 6. LOESS/robust local regression 只作視覺與診斷

**原始來源事實：**Cleveland 的 LOWESS 是每個目標位置對鄰近資料加權做局部 polynomial fit，
並以 robust fitting 降低 deviating points 對 smooth curve 的影響。
[Cleveland 1979, JASA](https://doi.org/10.1080/01621459.1979.10481038)

**本專案推論：**它適合畫出 `orbit_mean_a` 的 shape、檢查 OLS residual，但不適合當正式
storm-decay result。robust iteration 可能把真正的 storm peak 當 outlier；span 與 polynomial
degree 仍會改寫 peak。若使用，圖上必須顯示 span，且不得拿曲線微分後的尖峰作主結論。

## 不應誤認為「更好」的選項

| 選項 | 為何不是目前的較佳主方法 |
|---|---|
| 每天一個 OLS slope | 可和 Ram et al. 對照，但 UTC 日界不適合 event timing。保留為論文對照。 |
| 3/6/12 h backward difference | 有高時間解析度，但直接取兩時點差，殘留 H2/H3 與單點誤差會放大。保留作對照。 |
| 全三年固定 harmonic coefficients | 已知 H2 amplitude 會隨時間變；固定係數的失配會漏入 trend。 |
| Kalman smoother / Gaussian process | 可畫得連續，卻把 process covariance 或 kernel length scale 變成未校準的物理假設。B-L table 沒有完整 dynamics/covariance 來約束它。 |
| 自動從 `a` 找 storm boundary | 把 noise、maneuver、POD anomaly 選成效果的風險最高；不能取代外部事件定義。 |

## 最小可比較實驗

先不要全面實作每一種方法。以同一組完整 orbit mean、同一批排除旗標，對已知 storm cases 比較：

1. 文獻對照：fixed UTC-day OLS。
2. 事件主表：外部 boundary 的 segmented OLS。
3. timing sensitivity：置中 rolling 12 h OLS 與 24 h OLS。
4. 若 2/3 差異很大：檢查逐圈平均後 H2/H3 residual、coverage、maneuver/source boundary；
   不要先改用更強的 smoothness penalty。
5. 只有在事件段有足夠 orbit 數時，才把 conventional OLS `1-sigma` 與 HAC/block-bootstrap
   interval 作為 uncertainty sensitivity。

驗收不以「圖更平」判斷，而是 synthetic injection 能否回收已知 event slope、不同 window 的
peak 是否穩定、以及所有估計器是否在同一個 quality segment 內工作。

## 來源界線

- 本文件新增的統計方法來源均為方法原始論文或作者/機構公開版本。
- 這些來源沒有宣稱它們已被驗證為 Swarm B-L mean-element 的最佳 decay estimator；套用到
  本專案的好壞判斷均明標為「本專案推論」。
- Swarm-specific 的 phase-defined orbit mean、daily OLS、H2/H3 與 force-model 界線，沿用
  `RESEARCH_ORBITAL_DECAY_FITTING_METHODS.md` 的原始來源與限制，不在此重複擴張。
