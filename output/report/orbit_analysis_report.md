# Swarm-A 軌道分析流程報告草稿

## 研究定位

本研究要建立可追溯的 Swarm-A 軌道衰減候選資料集，供後續分析地磁活動與軌道衰減的關係。

本階段的交付物是資料處理流程與候選衰減率，不是「已證明地磁暴造成軌道衰減」的因果結論。已知軌道控制、資料來源差異與估計方法造成的異常仍須校準。

## 現行狀態

目前可展示的是 2023-07-01 至 2026-07-01 UTC 的三年 working bench。

```text
9,469,438 筆平均軌道元素
  -> 16,844 筆完整相位軌道
  -> 67,328 筆三圈或五圈衰減率候選
  -> 67,328 筆完成地磁與太空天氣對齊的分析列
```

三年資料是目前的方法展示與驗證範圍。未來若建立 2014--2026 的十二年 working bench，應沿用相同方法，僅替換分析時間範圍與輸出統計；不可把兩者混成同一個 release。

## 主流程

```text
ESA 精密軌道資料（POD）
  -> 國際地球參考框架（ITRF）原始 state
  -> 地心天球參考框架（GCRF）與平均軌道元素
  -> 資料品質判定與連續資料段（chunk）
  -> 完整軌道相位與二、三階諧波（H2/H3）診斷
  -> 三圈與五圈最小平方法（OLS）衰減率候選
  -> 地磁與太空天氣特徵對齊
  -> 資料產品稽核
```

## 1. 精密軌道資料轉換為平均軌道元素

歐洲太空總署（ESA）的精密軌道資料提供每 10 秒的衛星位置與速度。原始資料的 state 位於國際地球參考框架（ITRF）；時間從 GPS 轉為 UTC，位置與速度統一轉為 SI 單位。

每個 state 先轉到地心天球參考框架（GCRF），再計算瞬時軌道元素。接著使用 Orekit 的布勞威爾－里登平均化（Brouwer-Lyddane mean elements）取得平均軌道元素，其中最重要的是平均半長軸 `mean_semi_major_axis_m`。

這一步的目的不是直接量到大氣阻力，而是降低短週期軌道變化對後續趨勢估計的干擾。每筆平均元素保留原始的 `time_us`，因此仍可一路追溯回 POD source file 與原始 state。

同時由平均近地點幅角與平均近點角定義軌道相位：

```text
u = omega + M
```

`u` 表示觀測點在該圈軌道中的位置。它不是固定 UTC 時鐘，而是用來辨識隨軌道位置重複出現的週期訊號。

## 2. 資料品質判定與連續資料段

這一步要清楚區分「排除資料」與「切斷計算」。兩者都保留在資料庫中，並不修改原始觀測資料。

### 排除資料

下列 state 不可進入後續估計：

- 時間未嚴格遞增。
- 位置或速度為空值、NaN 或 infinity。
- 瞬時軌道元素不存在、軌道能量無效，或半長軸不是有限正值。
- 落在 ESA 已公告的 orbit-control maneuver、collision-avoidance maneuver 或 orbit-raise campaign 時段。

每筆結果寫入 `swarm_a_pod_quality` 的 `is_usable` 與 `rejection_reason`。原始 POD state 不會被刪除或覆寫。

### 切斷計算

可用資料仍必須依 `chunk_id` 分段。出現下列條件時，下一筆可用資料會開始新的 chunk：

- 前一筆資料不可用。
- SP3 product stream 改變。
- SP3 frame 改變。
- 資料 cadence 改變，或 source provenance 不完整。
- 相鄰 state 的時間差不等於該 source 的 cadence。

`chunk_id` 不是品質分數。它是估計器的邊界：後續完整軌道、平均與最小平方法視窗都不能跨越資料缺口、產品切換、座標框架切換或已知 maneuver 時段。

## 3. 完整軌道相位與 H2/H3 診斷

一圈軌道只有在下列條件都滿足時，才視為完整軌道：

- 至少 500 個 POD samples。
- 相位涵蓋至少 `2pi - 0.05 rad`。
- 最大相鄰資料 gap 不超過 10 秒。
- 不跨越 `chunk_id` 或 source gap。

對每一個完整軌道，程式以相位加權平均得到一圈的平均半長軸，並估計二階與三階諧波（H2/H3）的振幅。H2/H3 描述半長軸中隨軌道相位重複出現的週期成分。

這一步不把 H2/H3 直接解釋為大氣阻力。它的作用是量化：若直接對半長軸估計斜率，軌道相位相關的週期訊號會造成多少干擾。

## 4. 三圈與五圈軌道的衰減率候選估計

每個完整 orbit 的右端點都建立 trailing 3-orbit 與 5-orbit 視窗。所有視窗都必須位於同一個 chunk，且不能跨越 orbit boundary gap。

每個視窗保留兩種估計方法：

```text
原始平均元素模型：
a(t) = b0 + b1(t - t0)

H2/H3 聯合模型：
a(t) = b0 + b1(t - t0) + H2(u) + H3(u) + residual
```

兩個模型的 `b1` 都轉為 `m/day`，作為衰減率候選。每筆候選還保留：

- `decay_rate_1sigma_m_day`：斜率不確定度。
- `fit_residual_std_m`：模型殘差標準差。
- `sample_count`：實際用於估計的資料點數。
- `window_start_time_us`、`time_us` 與 `chunk_id`：視窗邊界與來源追溯資訊。

同一段資料同時保留原始模型與 H2/H3 聯合模型，而不是只選看起來較平滑的一種。這可直接比較相位修正對斜率、不確定度與殘差的影響。

目前三年 working bench 有四種候選組合：

```text
原始平均元素：3 圈、5 圈
H2/H3 聯合模型：3 圈、5 圈
```

## 5. 地磁與太空天氣資料對齊

每個候選衰減率會對齊 SYM-H、Ap、F10.7 與 F10.7A。對齊規則禁止使用候選時間之後的太空天氣資料：

- Ap 使用候選所在的 3 小時區塊。
- F10.7 與 F10.7A 使用前一個 UTC day 的資料。
- SYM-H 優先使用同時刻觀測；若插值，右端點最多只能晚於候選 120 秒。

這一步只把地磁與太空天氣值加入 candidate record，建立後續檢查相關性的資料條件；它本身不構成地磁暴造成衰減的因果證明。

## 6. 資料產品稽核

稽核不是主要研究結果，而是這份 working dataset 可以被使用的最低門檻。現行三年 branch 的稽核結果如下：

- 67,328 筆衰減率候選與 67,328 筆分析列一對一對應。
- future feature reference 為 0。
- non-finite candidate 或 analysis value 為 0。
- candidate key mismatch 與 P1.6 foreign-key violation 為 0。
- SQLite integrity check 為 `ok`。

這表示資料符合已定義的資料契約；不表示衰減率已完全排除 maneuver、資料來源或方法造成的異常。

## 報告應呈現的圖表

1. 主流程圖：從 POD 到 audit-passed candidate dataset 的資料流。
2. 資料涵蓋與 chunk 時間線：標出資料缺口、frame transition 與公告 maneuver 時段。
3. 單一完整軌道圖：原始平均半長軸、H2/H3 重建與相位加權 orbit mean。
4. 候選比較圖：原始模型與 H2/H3 聯合模型在 3 圈、5 圈視窗的斜率、uncertainty、residual。
5. 個案時間序列圖：候選衰減率與 SYM-H、Ap 的共同時間軸；只能標示為 descriptive case study。

## 目前不可宣稱的結論

- 衰減率候選不等於已校準的真實大氣阻力衰減率。
- H2/H3 修正降低週期訊號，不代表已證明剩餘訊號全是物理衰減。
- 與 SYM-H、Ap、F10.7 或 F10.7A 同時出現的變化，不等於已證明地磁暴是原因。
- 十二年資料集建立前，不應把三年 working bench 的統計量宣稱為全任務期結果。
