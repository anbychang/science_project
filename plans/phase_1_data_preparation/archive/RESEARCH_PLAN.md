# 極端地磁暴期間低軌衛星軌道衰減的動態延遲建模與多維驗證

> Source: https://hackmd.io/@lupin1012/rkUzrF6tMx  
> Saved: 2026-09-21

> WARNING: 這是外部提案的封存快照，不是目前執行規格，也不代表已完成或已驗證的研究結果。目前第一階段只以 `../PLAN.md` 為準。

# 大綱

問題：衛星軌道預報誤差大（300-500 米）

原因：大氣模型對磁暴響應有延遲（1-12 小時）

解決方案：

1. 用獨立密度數據（Swarm L2）量化模型偏差
2. 用 XGBoost 機器學習「地磁 -> 延遲」
3. 多維驗證確保結果可信

結果：預報精度提升（20-32%）

# 6 個階段

## 一、資料準備 + 事件檢測

**做什麼：**

```text
├─ 下載 Swarm 軌道數據、地磁指標
├─ 計算軌道衰減速率
└─ 自動識別 50 個磁暴 + 標籤延遲
```

**核心公式：**

```text
半長軸：a(t) = -μ / 2E(t)
衰減速率：ȧ(t) = da/dt
延遲定義：τ = arg max Corr(過去地磁, 未來衰減)
```

**產出：**

- 40 個訓練磁暴 × 約 5000 點 = 200,000 個時間點
- 每個點有延遲標籤 `τ ∈ [0, 12]` 小時

## 二、獨立密度驗證（關鍵）

**核心想法（打破循環論證）：**

```text
舊做法（循環）：
  我的衰減 -> 反推我的密度 -> 訓練修正 -> 預報 -> 驗證自己
                                              ↑ 自我驗證 [x]

新做法（獨立）：
  Swarm L2 獨立密度 -> 計算模型偏差 -> 訓練修正 -> 預報
                                            ↑ 客觀驗證 [done]
```

**做什麼：**

```text
步驟 1：下載 Swarm L2 官方密度（ESA 網站）
步驟 2：計算修正因子
        Cρ(t) = ρSwarm L2(t) / ρNRLMSIS(t)

步驟 3：對數變換（改進機器學習穩定性）
        y = ln(Cρ) -> 範圍 [-0.7, 1.6]

步驟 4：品質篩選
        移除異常值（Cρ < 0.5 或 Cρ > 20）
        保留約 500 個有效點

步驟 5：如果能找到 CHAMP 數據，用它驗證時間穩定性
```

**產出：**

- 約 500 個修正因子（訓練 XGBoost 用）
- CHAMP 時期相關性（驗證指標）
- 視覺化圖表

## 三、XGBoost 訓練

為什麼 XGBoost 而不是 GPR？

```text
簡單（10 行代碼訓練）
無需複雜理論
預測精度相近
適合小樣本
```

**代碼示例：**

```python
from xgboost import XGBRegressor
from sklearn.model_selection import cross_validate

model = XGBRegressor(n_estimators=100, max_depth=5)
cv_results = cross_validate(model, X_train, y_train, cv=5)
cv_mae = -cv_results["test_score"].mean()

# Goal: cv_mae < 1.5 h
```

**7 維特徵（全部用過去信息）：**

| # | 特徵 | 物理意義 |
|---|---|---|
| 1 | 過去 6 h 地磁積分 | 累積能量 |
| 2 | 當前地磁變化率 | 強迫強度 |
| 3 | 暴演變階段 `[0, 3]` | 進展階段 |
| 4 | 相對太陽活動 | 背景狀態 |
| 5、6 | 季節編碼 | 季節效應 |
| 7 | 軌道高度 | 密度環境 |

**產出：**

- 訓練好的 XGBoost 模型
- 5 折交叉驗證性能

## 四、軌道預報 + 驗證

**Hindcast 版本（理想）：**

```text
使用：τobs,HC（已知延遲，事後）-> RMSE
目的：測試方法論上限
```

**Forecast 版本（現實）：**

```text
使用：τ̂(t) = XGBoost 預測的延遲 -> RMSE
目的：實際預報能力
```

**簡化軌道積分：**

```python
# Use a library, so we do not need to write RK45 here.
from poliastro.twobody import Orbit

for each_timestep:
    density = nrlmsis(..., ap_at_time_minus_delay) * correction
    new_orbit = integrate_one_step(current_orbit, density)
    save_error(new_orbit)
```

**產出：**

- Hindcast RMSE @24 h、@48 h、@72 h
- Forecast RMSE（同上）
- 軌跡對比圖表

## 五、統計分析 + 論文

**主要結果：**

計算改進率：

```text
Improvement = (RMSE_M0 - RMSE_M3) / RMSE_M0 × 100%
```

**預期結果：**

```text
Hindcast：改進 28-32%（有利條件）
Forecast：改進 18-24%（現實條件）
三個模型都改進 -> [done] 通用性確認
```

**簡單統計：**

```python
# Mean and standard deviation
mean_improvement = np.mean([...])
std_improvement = np.std([...])

# Bootstrap 95% interval
# scipy can do this, or use simple resampling.
```

**論文結構（8-10 頁）：**

```text
摘要（250 字）
1. 前言（1 頁）
2. 方法論（3-4 頁）
3. 結果（2-3 頁）
4. 討論（1.5 頁）
5. 結論（0.5 頁）
```

# 創新點

## 創新 1：獨立密度驗證

問題：傳統方法用自己反推的密度驗證，這是循環論證。

你的方案：

```text
├─ 用 Swarm L2（ESA 不同團隊反演的密度）
├─ 用 CHAMP（不同衛星，不同時期）
└─ 三個獨立大氣模型驗證
```

結果：無法反駁的多維驗證體系。

## 創新 2：因果延遲的動態預測

傳統：用經驗固定延遲或靜態延遲。

你的方案：用機器學習預測「在當前地磁條件下，延遲應該是多少」。

物理意義：延遲不是常數，它隨磁暴演變而變化。

## 完整的因果邏輯

特徵只用過去信息（因果性嚴格）-> XGBoost 預測延遲 -> 軌道預報驗證 -> 統計確認。

# 優勢（比傳統研究）

| 方面 | 傳統軌道預報 | 你的研究 |
|---|---|---|
| 創新 | 應用已知方法 | 識別 + 解決循環論證問題 |
| 驗證 | 單一方法驗證 | 多維驗證（時間／模型／來源） |
| 深度 | 黑盒應用 | 因果機制分析 |
| 科學性 | 實驗設計簡單 | 設計周密，預期充分 |

# 數據來源（直接鏈接）

- [done] [ESA Swarm POD](https://earth.esa.int/eogateway/data/swarm-precise-orbit)
- [done] [ESA Swarm L2 密度](https://earth.esa.int/eogateway/data/swarm-l2-products)
- [done] [地磁指標（WDC）](https://www.ncei.noaa.gov/products/data-indices-geomagnetic)
- [done] [太陽 F10.7（NOAA）](https://www.space.com/solar-activity/)
- [done] CHAMP 密度（如果有論文發表）：Google Scholar 搜尋 `CHAMP thermospheric density`

# 工具清單

Python 核心：

```text
├─ numpy, scipy（數值計算）
├─ pandas（數據處理）
├─ xgboost（機器學習，只需 5 分鐘學會）
└─ matplotlib/seaborn（繪圖）
```

軌道計算（可選簡化）：

```text
├─ poliastro（軌道積分）
└─ astropy（坐標轉換）
```

版本控制：

```text
└─ GitHub
```

## 科學完整性

- [ ] 核心創新明確（獨立密度驗證）
- [ ] 方法論自洽（因果邏輯嚴密）
- [ ] 結果有數據支持（不是定性）
- [ ] 多維驗證完成（時間、模型、來源）

> 「利用大氣模型對磁暴的響應有延遲，設計了一套獨立驗證體系來量化它，用機器學習進行動態修正，最後用多維驗證證明了這個改進的真實性和通用性。」
