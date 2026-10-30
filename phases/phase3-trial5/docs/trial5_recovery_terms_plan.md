# Trial5：恢復起始項與恢復項計畫

## 決定

狀態：[working]。Trial5 專門研究 Trial4 尚未處理的第三件事：事件後段的「恢復起始項」與「恢復項」。Trial4 的自由 $R_k$、自由 $\tau_k$ 與共同 $G$ 不再修改；它是 Trial5 的唯讀基線。

```text
Phase 3 frozen source
  -> Trial4 joint-fit baseline
  -> Trial5 recovery-start term + recovery term
```

## 第一個恢復模型

Trial4 只讓一個常數 $R_k$ 平移整場背景，並用 $H_{\tau_k}$ 描述 SME 驅動的記憶。Trial5 的第一個模型固定這些 Trial4 參數，額外加入

$$
y_{k,i}=\ln R_k+GH_{\tau_k,k,i}
+A_k\exp\!\left[-\frac{t_i-t_{0,k}}{T_{\mathrm{rec}}}\right]
\mathbf{1}(t_i\ge t_{0,k}).
$$

$A_k\ge0$ 是第 $k$ 場在 $t_0$ 的恢復起始項；$T_{\mathrm{rec}}$ 是 25 場共用的恢復時間。恢復項在 $t<t_0$ 精確為零，後續 SME 再驅動仍由固定 Trial4 的 $GH_{\tau_k}$ 項處理。它會歸零，因而不和固定背景 $R_k$ 完全混成同一個 intercept。

## 第一個結果

以 25 場等權 MSE 在 $T_{\mathrm{rec}}=0.1$–96.0 h、每 0.1 h 格點搜尋。每個候選時間先以最小平方得到 $A_k$，再截為非負。最佳格點為 $T_{\mathrm{rec}}=14.3$ h；等權逐場 RMSE 從 Trial4 的 0.109953 降到 0.101272，17／25 場 $A_k>0$。完整數值在[Trial5 第一份恢復項報告](../reports/trial5_recovery_first_fit.md)。

## 尚未決定的下一步

| 問題 | 必須決定的內容 |
| --- | --- |
| $T_{\mathrm{rec}}$ 共享方式 | 共同 14.3 h 是否足夠，或要允許事件間差異？ |
| $R_k,\tau_k,G$ | 是否仍固定 Trial4，或要在有恢復項時共同重估？ |
| 函數形式 | 一個指數不足時，是否有獨立證據支持雙指數或其他形式？ |
| 評分 | 如何保留事件或時間段作不參與選參的檢查？ |

目前不能先假設指數函數是物理正確。中心相位平均仍會使用錨點後資料，所以即使 Trial5 擬合較好，也只能先稱為 retrospective descriptive improvement。

## 獨立後段檢查

每場留出時，共同 $T_{\mathrm{rec}}$ 只用其餘 24 場選擇；被留出場的 $A_k$ 只由 $t_0$ 後前 6、12、24 或 36 h 的殘差估計，再評分之後的資料。共同時間在 11.8–14.7 h，選參穩定；但正值恢復項只在 6 h 情境有小幅改善，12 h 幾乎持平，24 h 和 36 h 變差。

結論：此最小模型不採用為全事件恢復律，也不併回 Trial4。它只保留為「部分事件在 $t_0$ 附近有短期正殘差」的診斷證據。[完整驗證結果](../reports/trial5_recovery_first_fit.md)與 `data/analysis/trial5_recovery_horizon_models.csv` 為準。

## 硬資料邊界

Trial5 只讀下列既有輸出：

- Trial4 `trial4_joint_fit_minute`：L2、quiet/full MSIS、Trial4 預測與對數殘差。
- Trial4 `trial4_25storm_overview`：$R_{\mathrm{RQ}}$、$R_{\mathrm{fit}}$、$\tau_k$ 與逐場誤差。
- Phase 2／Phase 3 的唯讀 SME、SYM-H 與事件時間資訊。

Trial5 只能建立新的 `phase3-trial5/data/sqlite/` 與 `data/analysis/` 輸出，不得更新 Trial4 或凍結 Phase 3 的資料表。

## 已交付輸出

- `code/calc_trial5_recovery.py`：純格點計算。
- `code/prep_trial5_recovery.py`：唯讀 Trial4，寫 Trial5 CSV、SQLite 和圖。
- `data/sqlite/swarm_a_trial5_recovery_v1.sqlite`：214,907 個 minute rows 與 25 場總覽。
- `data/analysis/`：模型、格點和逐場 CSV。
- `figures/trial5_recovery_25storm_residuals.png`：Trial4／Trial5 殘差比較。
- `data/analysis/trial5_recovery_loo_*.csv`：留一事件選擇共同時間的驗證。
- `data/analysis/trial5_recovery_horizon_*.csv`：6、12、24、36 h 獨立後段驗證。
- `figures/trial5_recovery_horizon_validation.png`：預測距離敏感度。
- `tests/`：指數形狀、非負 amplitude、格點最低點與 SQLite contract 測試。
