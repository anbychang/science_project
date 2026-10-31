# Swarm-A Phase5 Trial1：Trial4 殘差高度 GPR

## 結果與限制

狀態：[done]。Phase5 Trial1 在 Trial4 D-model 的固定資料內基線上，使用 `{H_tau_k, H_24h, SME, SYM-H, altitude}` 擬合零均值 GPR 殘差。2,295 個一圈錨點的資料內對數 RMSE 從 0.11005 降到 0.02029，MAE 從 0.07955 降到 0.01360，條件式 95% 區間涵蓋率為 98.39%。

這不是模型有效性的證據。Trial4 已用這 25 場事件期間 L2 選每場 $R_k,\tau_k$，Phase 5 又在相同錨點 fit GPR。因此結果只量測同一資料上的貼合能力，不能稱為留一場、外測、預報或高度因果效果。

## 模型

Trial4 的固定密度基線是 $\rho_{\mathrm{T4}}$，Phase 5 目標為

$$
y=\ln\left(\frac{\rho_{\mathrm{L2}}}{\rho_{\mathrm{T4}}}\right).
$$

GPR 以零均值學 $y$，輸出

$$
\widehat\rho=\rho_{\mathrm{T4}}\exp(\mu_{\mathrm{gp}}).
$$

五個特徵都取相同中心 $u\pm\pi$ 相位窗口的代表錨點。高度是 DNSAPOD `altitude_m` 的 paired-sample 相位平均，不是 `mean_semi_major_axis_m`。

| 指標 | Trial4 | Trial4+GPR |
| --- | ---: | ---: |
| 全部錨點對數 RMSE | 0.11005 | 0.02029 |
| 全部錨點對數 MAE | 0.07955 | 0.01360 |
| 95% 條件式涵蓋率 | 無 | 98.39% |

高度的標準化 ARD length scale 是 0.010，正好達到設定下界；本次最佳化也產生 1 個 `ConvergenceWarning`。這表示模型對高度座標極度敏感或在記住資料內結構，不能將此欄解讀為可靠物理訊號。其餘 length scale 只描述這個資料內模型的局部敏感度，也不表示因果排序。

## 輸出與重算

- [25 場總覽圖](../figures/phase4_trial4_altitude_gpr_25storm.png)：黑=L2、藍=Trial4、紅=Trial4+GPR、淡紅=條件式區間、綠=高度。
- [逐場指標](../data/analysis/phase4_trial4_altitude_event_metrics.csv)：25 場與全部錨點的資料內指標。
- [核參數](../data/analysis/phase4_trial4_altitude_gpr_hyperparams.csv)：ARD、signal、noise、marginal likelihood、warning count。
- [標準化參數](../data/analysis/phase4_trial4_altitude_scaler.json)：五欄的 mean、scale 與 anchor count。
- [資料血緣](../docs/lineage/phase_5_trial4_altitude_gpr.md)：來源、key、輸出與限制。
- [重算入口](../code/prep_phase5_trial4_gpr.py)：唯讀 Phase 2／Trial4，寫 Phase 5。

重算入口拒絕覆寫既有輸出。重新執行需要本機 DNSAPOD ZIP、Phase 2 P2.6 SQLite、Trial4 SQLite 與相依套件；本機 SQLite 不納入 Git。
