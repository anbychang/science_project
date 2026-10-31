# Phase5：單一特徵 GPR 消融

狀態：[done]。這是對 Trial1 五特徵 GPR 的探索性單欄分析，不是新 Trial，也不改變 Phase5 Final `[not created]`。完整五欄 GPR 的 held-out RMSE 是 0.110281，仍略差於固定 Trial4 D-model 的 0.110050；沒有任何結果支持採用 GPR。

## 方法與判讀

固定 Trial2 的五個 20-train/5-test storm split。每個 feature set 都只在該 fold 的 20 場重新 fit RBF-ARD GPR，再預測另外 5 場。為讓 11 個 feature set 可在有限計算量下平等比較，每折使用一個確定性 optimizer start；完整五欄 RMSE 與原 Trial2 的五 restart 結果相差 $1.41\times10^{-8}$，因此此設定對總分沒有可見影響。

對每個特徵 $j$，記錄兩個問題：

$$
\Delta_{\mathrm{single},j}=RMSE(\text{only }j)-RMSE(\mathrm{Trial4}),
$$

$$
\Delta_{\mathrm{drop},j}=RMSE(\text{without }j)-RMSE(\text{all five}).
$$

第一個數小於零才代表單獨能改善 Trial4；第二個數大於零才代表在其餘四欄已存在時，移除該欄會傷害五特徵 GPR。兩種數字都不是因果效應，也不是對未接觸事件集的確認性檢定。

## 結果

| 特徵 | only-feature RMSE | $\Delta_{\mathrm{single}}$ | without-feature RMSE | $\Delta_{\mathrm{drop}}$ | 判讀 |
| --- | ---: | ---: | ---: | ---: | --- |
| `H_tau_k` | 0.111437 | +0.001388 | 0.110963 | +0.000682 | 單獨無用；在五欄模型內有小而一致的條件增益，移除後 5/5 fold 變差 |
| `H_24h` | 0.110898 | +0.000849 | 0.111422 | +0.001140 | 單獨無用；條件增益小，移除後 4/5 fold 變差 |
| `SME` | 0.110779 | +0.000729 | 0.110197 | -0.000084 | 單獨無用；與其餘欄位冗餘，移除後 4/5 fold 略好 |
| `SYM-H` | 0.113322 | +0.003273 | 0.109242 | -0.001039 | 單獨最差；移除的整體分數較好，但 fold 間不一致（2/5 變好、3/5 變差） |
| `altitude` | 0.110050 | +0.000001 | 0.118133 | +0.007851 | 單獨近乎零修正；五欄模型移除後整體明顯變差，3/5 fold 變差 |

高度的結果必須特別小心。它沒有單獨預測能力，卻讓五欄 GPR 的整體錯誤避免惡化；最合理的模型層級解釋是它把 kernel 局部化，抑制其他 geomagnetic 欄位對未見 storm 的有害修正。這與 Trial2 的高度 ARD 下界診斷一致，但不表示高度造成密度殘差，也不支持高度作為 Final 的物理修正項。

`H_tau_k` 與 `H_24h` 的 conditional delta 為正，但完整五欄模型仍差於 Trial4。它們至多表示此 GPR 的內部組合依賴，不能視為已驗證的獨立預測訊號。`SME` 和 `SYM-H` 則沒有留下可採用的額外訊號。

## 決策

- Trial1--Trial5 的「沒有 GPR 泛化改善」結論不變。
- 本消融補足了單欄數字，但它在同一批 25 場、已被多次探索的資料上完成；只作診斷，不作 Final 選模。
- 若要確認 `H_tau_k`、`H_24h` 或高度是否真有預測價值，必須鎖定特徵集合後，在新的未接觸 storm 做預先定義驗證。

## 輸出與重算

- [總結指標](../data/analysis/phase4_feature_ablation_summary.csv)
- [逐 fold 指標](../data/analysis/phase4_feature_ablation_fold_metrics.csv)
- [每特徵貢獻](../data/analysis/phase4_feature_ablation_contributions.csv)
- [重算入口](../code/prep_phase5_feature_ablation.py)
- [計算定義](../../phase5/code/calc_phase5_feature_ablation.py)
