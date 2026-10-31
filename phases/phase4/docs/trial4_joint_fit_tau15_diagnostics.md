# Phase 4 joint-fit 方法與診斷備忘

## 決定

狀態：[working]。這份文件保存完整 Report 以外的做法與前置診斷；正式數值結論只以[Phase 4 joint-fit 報告](../reports/trial4_joint_fit_tau15_report.md)和其 SQLite 為準。

## 資料邊界

Phase 4 只讀取凍結的 Phase 3 相位密度、Phase 2 SME 與事件 metadata。它不重新校準 Phase 3 的 $R_k$，也不回寫 Phase 2／3 SQLite。中心相位平均會用到錨點後的資料，因此本階段是 retrospective descriptive fit。

## 擬合規格

每場定義 $y=\ln(\rho_{\mathrm{L2,phase}}/\rho_{\mathrm{MSIS,q,phase}})$，模型為 $y\approx\ln R_k+GH_{\tau_k}$。損失先在每場取 MSE，再對 25 場取平均。起始值為 Phase 3 的 $R_{k,\mathrm{RQ}}$、全部 $\tau_k=2.5$ h 與 Phase 3 的共同 $G$。

- $0<R_k<2$，沒有 RQ 軟限制或代價。
- $\tau_k=0.0$–15.0 h，間隔 0.1 h；平手保留前一輪格點。
- 一個共同 $G>0$；若估到非正值即失敗。
- 固定 $\tau_k$ 後更新 $R_k,G$，固定 $R_k,G$ 後同輪掃完 25 個 $\tau_k$；最多 20 輪。

完整模型 D 在第 5 輪停止，所有事件均未到 15 h 上界。這只表示搜尋範圍足夠，不讓 $\tau_k$ 自動取得物理時間常數的解讀。

## 擬合前殘差與時間初篩

自由擬合前，固定 Phase 3 模型的 25 場 L2/M1 幾何平均比值為 0.7613–1.4771，顯示事件間背景偏移不能用一個 pooled 常數解釋。全體殘差與 $H$ 的相關為 -0.186899，亦表示不能把所有偏差都歸給 $R_k$。

在 Phase 3 的中心相位資料上做 minute-shift correlation 時，+30 min 只比零位移高 0.000706。這小於中心相位平均與窗口重疊造成的時間平滑可解讀程度，因此沒有用它來指定 $\tau$ 的方向。自由 $\tau_k$ 是直接以模型 loss 選出，不是 peak lag 或 causality measurement。

## 輸出定位

`data/sqlite/` 保存 A–D 參數、逐場結果、迭代、總覽與完整 214,907 個 Phase 4 minute rows。`figures/` 是該 SQLite 的檢查圖。`reports/` 只保留完整的 Phase 4 結果報告；資料契約與方法細節放在本文件和 lineage。
