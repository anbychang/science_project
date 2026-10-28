# Phase 3：SME 平靜基準的原始文獻核對

狀態：[retained]。這是 Phase 3 結案前的文獻核對記錄。查到熱層密度研究採用不同的「平靜」定義；**沒有查到 SuperMAG 規定 SME 必須用某個事前天數、平均或中位數歸零，也沒有查到將一階延遲 SME 濾波後再歸零的通用規範**。本研究最終採用的操作規則與結果以[Phase 3 最終報告](../../reports/phase_3_final_report.md)為準。

## 先分清三層基準

1. **磁力計測站的基線**：SuperMAG 從各站磁場扣掉日變化、年趨勢與殘餘偏移，保留磁暴、substorm 訊號。Gjerloev（2012）§5 說明三部分及一年觀測資料；這一步已在產製指數時完成，**不是**本研究要從 SME 減去的「事件前活動量」。[原論文 §5](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2012JA017683)
2. **活動指數**：官方 AE 來自固定 AE 測站的 `AU−AL`；SuperMAG 的 `SME=SMU−SML` 是以較多測站產製的對應指數，`SML` 對應 AL 的下包絡。兩套來源不能只因意義相近就視為同一數列。[Newell 與 Gjerloev（2011）摘要及 §2](https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2011JA016779)、[同作者另一篇 §2.1](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2011JA016936)
3. **事件額外驅動與密度基準**：這是研究者為特定問題定義的量，例如從活動指數扣掉參考值，或由密度扣掉平靜背景。SuperMAG 測站基線已扣除，並不表示 SME 在每場磁暴前等於零。[Gjerloev（2012）§5–6](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2012JA017683)

## 直接相關的研究做法

| 研究與資料 | 原文可確認的做法 | 對本研究的限制 |
| --- | --- | --- |
| Yamazaki 等（2015），CHAMP 高緯密度 | §2 先用 `Kp<2` 的資料擬合平靜密度；作者稱驅動為「SuperMAG AE」，取當前及前一小時的平均。其平靜密度約對應 `AE=150 nT`，因此只對正的 `AE_d=AE−150 nT` 分析密度擾動；回歸前在活動分箱內取密度與驅動中位數。 | `150 nT` 來自這篇的**多年平靜密度樣本**，不是每場暴前窗口的 SME 中位數；分箱中位數也不是「每場暴前 quiet median」。文中名稱為「SuperMAG AE」，不能因此把官方 Kyoto AE、SME 與 SML 視為可互換。[原論文 §2](https://onlinelibrary.wiley.com/doi/10.1002/2014GL062748/full) |
| Iipponen 與 Laitinen（2015），GOCE | §2 取 Kyoto 的 **AE**，比較 0–72 小時積分窗；事件資料含擾動前 2 天及 AE 回到平靜後 2 天。從 GOCE 密度減去使用真實 F10.7、關閉 3 小時 `ap` 效應且日 `Ap=3` 的 MSIS 參考。11 場留出事件的模型密度按事件**第一個平靜日的平均密度**縮放，使模型與 GOCE 的平均相等。 | 是**矩形時間窗 AE 積分**，不是 SME 的指數核一階濾波；首日縮放校準的是**密度**，未聲稱將 AE 積分扣到零。其研究限於 GOCE 約 270 km 的軌道，且作者指出未測極端磁暴。[原論文 §2、§3、結論](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2015JA021093) |
| Kalafatoglu Eyiguler 等（2019），CHAMP 密度模型比較 | §2.2 同時要求 `Kp<3−` 與相鄰軌道平均密度差不超過 `1.25×10⁻¹³ kg/m³` 才列為平靜區間；用該區間密度**平均**比較加法偏差修正、兩邊減平靜密度、乘法比例修正。 | 這是**選密度校準區間**及比較密度修正，沒有規定 SME 的事件前窗口、基準值或一階濾波後歸零。作者的門檻按其 CHAMP 事件設定，不宜直接移植 Swarm-A。[原論文 §2.2](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2018SW002033) |
| Liu 等（2010），CHAMP | 摘要以磁暴前一個安靜日的**平均密度**作背景；對 merging electric field 積分過去 3 小時並考慮密度時滯。 | 驅動不是 AE／SME；密度安靜日平均不等於驅動的事前零點。[原論文摘要](https://angeo.copernicus.org/articles/28/1633/2010/angeo-28-1633-2010.html) |

## 補查：實際怎麼辨識 SME 安靜段

| 原文位置 | 用於辨識安靜的條件 | 安靜段後取的代表值及適用範圍 |
| --- | --- | --- |
| Newell 與 Gjerloev（2011）§4.2、圖 7–8 | 對跨年的 SME 分布擬合「quiet／active」兩個對數常態成分：原始分布眾數約 **61 nT**；quiet 成分的 `ln(SME)` 平均約 `4.0`，即 `exp(4.0)≈55 nT`。 | `55 nT` 是**整體分布 quiet 成分在對數尺度的中心**，不是逐事件篩選門檻，更不是某場磁暴前 SME 的平均／中位數。該文未訂連續安靜時長，也未提供逐事件 `SME_ref` 算法。[原論文 §4.2](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2011JA016936) |
| Oyama 等（2023）「Geomagnetically quiet-time wind」節、圖 1–3 | 在 Tromsø 約 9 年冬季 FPI 觀測中測試 `SME≤30,40,...,200 nT`；`≤30` 的風場時段有缺口，故以 **`SME≤40 nT`** 的樣本定義其平靜風場。作者指出即使 `Kp<3` 仍可能出現 `SME>400 nT`。 | 對**風速**依小時取平均，形成安靜風場；沒有對合格的 SME 取一個 mean／median 作 `SME_ref`，也沒有要求連續 24 小時低於門檻。這是單站、冬季風場研究，非 Swarm 密度的通用門檻。[原論文相關小節](https://link.springer.com/article/10.1186/s40623-023-01829-0) |
| Kellerman 等（2022）§2 | 為中緯度變壓器 GIC 研究，將 **`SME<100 nT` 且 `|SMR|<15 nT`** 的時刻判為安靜。 | 隨後以 30 分鐘時段與前後各 10 天資料計算**GIC** 的第 10／50／90 百分位安靜日曲線；`50%` 是 GIC 曲線，不是安靜段 SME 中位數。原文未以固定連續時長選事件，也未定 `SME_ref`。[原論文 §2](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2021SW002729) |
| Zhang 等（2025）摘要及結論 | 尋找特別嚴格的 geospace ground state：`SME<50 nT`、`SYM-H>0 nT`，同時要求極光橢圓高於 `70°` 磁緯、紫外極光強度低於 `500 R`，**連續至少 48 小時**。 | 這是在 2002–2022 年尋找極少見的超安靜狀態，且需極光影像；不是一般暴前 quiet-day 或 SME 代表值算法。原文沒有要求從安靜段計算 SME mean／median。[原論文摘要、結論](https://www.sciencedirect.com/science/article/abs/pii/S1364682625002433) |

Yamazaki 等（2015）§2 的 `Kp<2` 用於**挑選多年平靜密度資料**，`AE−150 nT` 的 150 是該平靜密度約對應的活動水準；沒有要求某場事件事前持續多久 `Kp<2`，也沒有逐事件 SME 代表值。文中回歸分箱取中位數的對象是**分箱後的密度擾動與驅動值**。[原論文 §2](https://onlinelibrary.wiley.com/doi/10.1002/2014GL062748/full)

這些門檻分別服務於磁尾分布、單站風場、電網 GIC 與極端安靜 geospace；**門檻只回答哪些時刻可列入候選安靜資料，沒有回答如何把候選資料壓成一個事件的 `SME_ref`**。Phase 3 已依最終操作規則完成校準；本檔不重新定義它。

## 對 Phase 3 的界線

- 文獻支持「先定義密度的安靜參考，再研究磁暴額外響應」及「高頻活動指數的歷史可影響密度」。它**沒有替我們決定** SME 的 `[-3,-2]` 天是否安靜、該取平均或中位數、或應在濾波前／後扣基準。這些是待檢驗的模型選擇。[Yamazaki 等 §2](https://onlinelibrary.wiley.com/doi/10.1002/2014GL062748/full)、[Iipponen 與 Laitinen §2](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2015JA021093)
- 若把一階濾波的輸入定義為「超過平靜值的 SME」，要區分減掉原始 SME 基準與減掉**同一窗口內的濾波後 SME 基準**。因濾波有記憶，事件前活動可使兩者不同；這是由模型方程導出的**本研究方法問題**，不是上述論文提供的規範。
- `G>0` 與平靜時額外響應為零的解讀仍受驅動、平靜窗口、濾波初始條件、歸零順序與缺值處理限制；這些已在 Phase 3 最終報告中界定，不能援引 AE 研究作為 SME 數值門檻。[Newell 與 Gjerloev（2011）](https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2011JA016779)
