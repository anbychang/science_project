# Trial4：25 場主線殘差基線

## 決定

狀態：[working]。Trial4 先保留 Phase 3 的 $R_k$、$\tau=4.65$ h 與 $G$，只量測 25 場的殘差型態。這一步不重跑或回調任何主線參數。

本目錄是 `phase3` 的完整複本。這份文件只查詢其 SQLite 與主線定義；沒有讀取 `phase3-trial`、`phase3-trial2` 或 `phase3-trial3`。

## 要回答的問題

目前的偏差主要像是：

- 每場背景高度錯置：優先懷疑 $R_k$；
- 響應強度隨 $H$ 系統性錯置：優先懷疑 $G$ 或 M1 的線性形式；
- 峰值時間錯置：優先懷疑 $\tau$ 或時間／相位 estimator。

三者不能由 RMSE 單獨區分。

## 殘差定義與資料來源

對 `phase3_prediction_minute` 的每個有效 `{storm_id, time_us}`，定義帶符號的對數殘差：

$$
e_{k,i}=\ln\!\left(\frac{\rho_{\mathrm{L2,phase},k,i}}
{\rho_{\mathrm{M1,pooled,phase},k,i}}\right).
$$

$e>0$ 表示 M1 偏低，$e<0$ 表示 M1 偏高。M1 的 `rho_m1_pooled_phase_kg_m3` 是以全部 25 場估出的固定 $G$ 建立的基線曲線；它不是 held-out 評估曲線。M1 的定義與欄位寫入見[prep_prediction_tau465.py](../code/prep_prediction_tau465.py)，相位 $H_\tau$ 的計算見[calc_h_tau.py](../code/calc_h_tau.py)。

SQLite 查詢使用 `ln()`；不可使用 base-10 的 `log()`，因為主線程式以 `np.log()` 定義對數密度殘差。

查詢資料庫：`data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite`，table `phase3_prediction_minute`。資料庫共有 214,907 個有效相位分鐘。這些分鐘的 $u\pm\pi$ 視窗高度重疊，不可當成 214,907 個獨立樣本；此限制沿用[Phase 3 結案報告](../../phase3/reports/phase_3_final_report.md)。

## 25 場的背景偏移

下表的 $\bar e_k$ 是每場所有有效分鐘的平均。`L2/M1` 是 $\exp(\bar e_k)$；大於 1 表示該場 M1 平均偏低。

| storm_id | $\bar e_k$ | L2/M1 |
| --- | ---: | ---: |
| S20230805T0546 | 0.115607 | 1.1226 |
| S20231021T0728 | 0.052478 | 1.0539 |
| S20231105T1654 | 0.097162 | 1.1020 |
| S20231201T1330 | 0.264780 | 1.3031 |
| S20240303T1800 | 0.067946 | 1.0703 |
| S20240324T1621 | 0.089138 | 1.0932 |
| S20240419T1921 | -0.018490 | 0.9817 |
| S20240511T0214 | -0.038412 | 0.9623 |
| S20240628T1206 | 0.287899 | 1.3336 |
| S20240804T1704 | 0.064258 | 1.0664 |
| S20240812T1652 | 0.390113 | 1.4771 |
| S20240917T0424 | -0.224447 | 0.7990 |
| S20241010T2314 | -0.069637 | 0.9327 |
| S20241109T1237 | -0.151480 | 0.8594 |
| S20250101T1640 | 0.048916 | 1.0501 |
| S20250416T1743 | -0.033762 | 0.9668 |
| S20250517T0516 | -0.102443 | 0.9026 |
| S20250601T1030 | -0.272702 | 0.7613 |
| S20250613T2015 | -0.213356 | 0.8079 |
| S20250930T0759 | -0.050752 | 0.9505 |
| S20251112T0359 | 0.015847 | 1.0160 |
| S20260120T1152 | -0.107236 | 0.8983 |
| S20260321T0139 | 0.236987 | 1.2674 |
| S20260402T0841 | 0.305572 | 1.3574 |
| S20260418T0754 | 0.154466 | 1.1670 |

全體平均 $\bar e=0.036977$，即 L2/M1 = 1.0377。這個整體偏低不能代表每一場：25 場同時有明顯正、負背景偏移，範圍是 0.7613--1.4771。

結論：$R_k$ 或 quiet-MSIS 背景值得列為假說，但不能僅憑 pooled 平均偏差把全部 $R_k$ 一起重調。Phase 3 的暴前／暴後 quiet ratio 本來已有中位 11.5% 的相對差，且 8 場超過 20%；該既有穩定性限制見[Phase 3 結案報告](../../phase3/reports/phase_3_final_report.md)。

## 響應強度的訊號

將全部有效分鐘按 `h_phase_nt` 分為五等份後，最低兩組的 L2/M1 約為 1.070--1.073，最高組為 0.974；全體殘差與 $H$ 的 Pearson correlation 為 -0.186899。

這是「$H$ 愈強時，M1 相對愈偏高」的弱到中等診斷訊號。它不能單獨證明 $G$ 應改多少，因為目前 fit 強制通過原點，global intercept 與所有 $R_k$ 同乘一個常數在數學上不可區分。它足以說明：不能把所有偏差都當成每場 $R_k$ 的問題。

## 尚未對 $\tau$ 下結論

目前只量了高度與強度殘差，沒有逐場量測 L2 與 M1 的 peak lag 或完整 cross-correlation。因此現在沒有證據判定 $\tau=4.65$ h 偏大或偏小。中心相位平均本身會用到錨點之後的資料，且會平滑時間結構；直接把曲線最高點相減不能當可靠的 $\tau$ 診斷。[Phase 3 結案報告](../../phase3/reports/phase_3_final_report.md)已將此輸出界定為 retrospective analysis。

## 逐場篩選圖 [done]

[Residual panels](../figures/trial4_25storm_residual_panels.png) 顯示每場 $e(t)$、該場 $\bar e_k$ 與 $H(t)$；[screening CSV](../data/analysis/trial4_25storm_residual_screen.csv) 是同一張圖的可重算數值。

這裡的 flag 只是安排下一輪人工檢查的門檻，不是物理分類：

- `background_offset`：$\lvert\bar e_k\rvert\ge\ln(1.10)$，即整場幾何平均比值離 1 至少 10%。
- `response_shape`：$\lvert\operatorname{corr}(e,H)\rvert\ge0.30$。

篩選結果為 9 場只有 `background_offset`、3 場只有 `response_shape`、5 場兩者皆有、8 場沒有 flag。這確認 25 場並非單一問題：有些主要是高度偏移，有些殘差隨 $H$ 改變，還有一批尚不能用這兩個指標歸類。

不能用同一場 storm-time L2 殘差直接回調 $R_k$ 後，再拿同一場宣稱改善。下一輪只檢查 flagged 場次是否與獨立 quiet ratio 或 response 結構一致，再決定要不要提出新的 $R_k$ 或 $G$ 假說。

## Trial4 joint-fit 的隔離狀態

`prep_trial4_joint_fit.py`、`prep_trial4_joint_prediction.py` 與 `prep_trial4_residual_panels.py` 只讀 Trial4 保存的 Phase 3 快照和 Phase 2 P2.6，且只寫 Trial4 output。這三個入口不依賴 `phases/phase3` 的 exploratory output。目錄內其餘較早 exploratory helper 是歷史複本，不是 joint-fit 重算流程的一部分。
