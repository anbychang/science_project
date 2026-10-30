# Trial4：25 場時間錯位初篩

## 決定

狀態：[working]。現有 Phase 3 的中心相位資料不足以判定共同 $\tau=4.65$ h 偏大或偏小。這一步只做 screening，不重跑、回調或替換任何主線參數。

## 比較方式

查詢 `data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite` 的 `phase3_prediction_minute` 與 `phase3_25storm_overview`。對每個有效 `{storm_id, time_us}`，使用

$$
z(t)=\ln\!\left(\frac{\rho_{\mathrm{L2,phase}}(t)}
{\rho_{\mathrm{MSIS,q,phase}}(t)}\right)-\ln R_k
$$

並計算 pooled Pearson correlation：

$$
\operatorname{corr}[z(t),H_{4.65,\mathrm{phase}}(t+\Delta)].
$$

正的 $\Delta$ 表示拿標記較晚的 $H$ 與目前的密度異常比較。SQLite 使用 `ln()`，與主線 `np.log()` 的自然對數定義一致；不可使用 base-10 的 `log()`。

| $\Delta$ (min) | 配對列數 | correlation |
| ---: | ---: | ---: |
| -180 | 209,845 | 0.618110 |
| -120 | 211,320 | 0.639796 |
| -60 | 213,047 | 0.655759 |
| 0 | 214,907 | 0.663573 |
| +30 | 213,977 | 0.664279 |
| +60 | 213,047 | 0.662126 |
| +120 | 211,320 | 0.650114 |
| +180 | 209,845 | 0.630578 |

## 判讀

最高值在 $\Delta=+30$ min，但相對零位移只增加 0.000706。這個差異遠小於中心相位平均本身造成的時間平滑，不能解讀成密度或 SME 響應真的相差 30 分鐘，更不能據此調整 $\tau$。

主線先將 1-minute SME 作一階濾波，再把每個錨點的 $u-\pi$ 到 $u+\pi$ 視窗平均。這個中心窗會使用錨點之後的 $H$ 與密度樣本；相鄰分鐘視窗也高度重疊。程式定義見[calc_h_tau.py](../code/calc_h_tau.py)的 `phase_support()` 與 `phase_weighted_mean()`，相位 $H$ 寫入方式見[prep_prediction_tau465.py](../code/prep_prediction_tau465.py)。因此這份資料適合檢查回溯曲線，不適合從 minute-shift correlation 估因果 delay。

此處的 pooled correlation 也會混合不同磁暴的背景差異；它不是 25 個獨立的 timing estimates。

## 下一個安全診斷

若要檢查 $\tau$，新實驗要在相位中心平均之前，保留原生或單側因果的 response／密度配對，並預先固定 onset window、lag 搜尋範圍與 held-out 評估。結果仍只能寫入 Trial4，不能回改已凍結的 Phase 3。
