# Phase 3B 使用者原始草稿（歷史）

狀態：[retained]。2026-10-26 由使用者貼入的來源草稿，保留原始主張與符號供追溯；它不是 Phase 3 的現行方法或待辦。Phase 3 已結案，採用結果以[Phase 3 最終報告](../../reports/phase_3_final_report.md)為準。

## 3B-1 指數核從哪裡來、代表什麼

熱層一邊被加熱、一邊冷卻，用一階方程描述：

$$
\frac{dT}{dt}=\frac{Q}{C}-\frac{T-T_0}{\tau}.
$$

它的解等於「過去所有時刻的 \(Q\)，依距今多久按指數遞減加權」，也就是對 \(Q\) 做指數核卷積：

$$
\widetilde Q(t)=\int_{-\infty}^{t}Q(t')
\frac{1}{\tau}e^{-(t-t')/\tau}\,dt'.
$$

| 距今時間 | 權重（相對於當下） |
| --- | --- |
| 0 | 1 |
| \(\tau\) | \(e^{-1}\approx0.37\) |
| \(2\tau\) | \(e^{-2}\approx0.14\) |
| \(3\tau\) | 約 0.05 |

原稿列出三個性質：

- 有記憶：連續數小時的強驅動會累積，短暫尖刺的影響很小。
- 延遲自然出現：\(Q\) 達到峰值後 \(\widetilde Q\) 仍會上升，等 \(Q\) 降到低於 \(\widetilde Q\) 才開始回落；原稿稱其峰值必然晚於 \(Q\)。
- 核的積分為 1，\(Q\) 長時間不變時 \(\widetilde Q=Q\)；原稿把 \(Q\) 視為 SME 時，單位為 nT，\(G\) 單位為 nT\(^{-1}\)。

## 3B-2 用遞迴計算 \(\widetilde Q(\tau)\)

$$
\widetilde Q_k=\alpha\widetilde Q_{k-1}+(1-\alpha)Q_k,
\qquad \alpha=e^{-\Delta t/\tau}.
$$

1. 輸入：從 sme_1min.parquet 讀 1 分鐘 SME，\(\Delta t=1\) 分鐘。當 \(\tau=0\) 時直接令 \(\widetilde Q=Q\)。
2. 暖機：從窗口起點前 3 天開始遞迴，初值取第一天 SME 的平均。最大 \(\tau=10\) 小時，3 天遠大於 \(5\tau\)。
3. 缺值：單一分鐘缺值以前一個有效 SME 代入；長缺口也以前一個有效值延續，相關的圈由步驟二標為 is_valid=False，不進入擬合。
4. 每圈平均：先在 1 分鐘尺度算 \(\widetilde Q\)，再按圈平均，和每圈 \(\rho_{\mathrm{L2}}\) 對齊。

原稿的因果性主張：\(\widetilde Q\) 只使用過去 SME，因此 \(\tau\geq0\)；並稱 \(\tau\) 能給 Forecast 約 \(\tau\) 小時提前量。

## 3B-3 建立擬合資料

每圈定義

$$
y=\ln\!\left(\frac{\rho_{\mathrm{L2}}}{\rho_{\mathrm{MSIS,q}}}\right),
\qquad z=y-c_k.
$$

原稿將 \(z\) 解讀為扣除平靜基準後的磁暴密度增幅；只用訓練事件窗口內 is_valid=True 的圈。

## 3B-4 對每個 \(\tau\) 估計 \(G\)

格點為 0 至 10 小時、間隔 0.25 小時，共 41 點。對每點以 \(z_i=G\widetilde Q_i\) 作過原點最小平方：

$$
G(\tau)=
\frac{\sum_i z_i\widetilde Q_i(\tau)}
{\sum_i\widetilde Q_i(\tau)^2}.
$$

使用者貼文的 RMSE 印式為

$$
\mathrm{RMSE}_{\mathrm{稿}}(\tau)=
\frac{1}{N}\sum_i
\bigl[z_i-G(\tau)\widetilde Q_i(\tau)\bigr]^2.
$$

此印式缺平方根，數學上是 MSE；在核對前保留原稿寫法。41 組的 \(G\) 與誤差曲線預定存下並繪成 F3-1。

## 3B-5 選出 \(\tau^*\)

- 取訓練誤差最小者為 \(\tau^*,G^*\)。
- 若曲線平坦，報告誤差在最小值 5% 以內的 \(\tau\) 範圍。
- 選做：以磁暴為單位重抽樣 200 次，求 \(\tau^*\) 的信賴區間。

## 3B-6 修正 \(c_k\)：迭代一次

原稿認為平靜窗口內 \(\widetilde Q\) 不一定為 0，故提議

$$
c_k^{(1)}=
\operatorname{median}_{t\in W_{\mathrm{quiet},k}}
\left[y(t)-G^*\widetilde Q_{\tau^*}(t)\right].
$$

再重做 3B-3 至 3B-5，記錄 \(c_k\) 與 \(\tau^*\) 變化；若 \(\tau^*\) 變化超過 0.25 小時再迭代一次。原稿稱通常一次就收斂。

## 3B-7 留一法

每折排除一場測試磁暴，重做 3B-3 至 3B-6，結果寫入 baseline_fit.csv。\(c_k\) 只用該場暴前平靜窗口，不跨場擬合；測試事件也只能用自己的暴前資料估 \(c_k\)。

## 3B-8 每場磁暴的 \(\tau_k\)：F3-4

每場單獨重做 3B-4 與 3B-5，得到 \(\tau_k\) 與誤差在最小值 5% 以內的範圍。

- 最佳點在 0 或 10 小時邊界：標「無明確延遲」。
- 範圍寬逾 4 小時：標「\(\tau\) 不確定」。
- 上述兩類不放進趨勢分析。

## 3B-9 自我檢查與論文敘述

- 預期 \(G>0\)；若 \(G\leq0\)，先查時間對齊。
- 原稿預期 \(\tau^*\) 大致在 0–4 小時；若頂在 10 小時，先查時間對齊。
- 畫殘差 \(z-G^*\widetilde Q\) 對 ap_step；若仍相關，原稿提議由後續 GPR 的 ap_step 特徵補足。
- 將逐場 \(\tau_k\) 與加入因果搜尋範圍的峰對峰 lag 對照。

原稿論文表述：平靜 MSIS 加 SME 延遲項若勝過完整 MSIS，代表這個組合對本資料的密度預測更準；原稿並稱 \(\tau^*\) 可直接和密度對 AE 的延遲比較。

原稿引 [Wang 等（2022）](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2021SW003017) CHAMP 2002–2008 年 265 場磁暴，密度相對 AE 峰值在弱、中等磁暴約晚 0–1 小時，強磁暴約晚 2–4 小時。F3-4 預定將各場 \(\tau_k\) 對 SYM-H 最小值作圖，檢查強度與延遲關係。原稿的 2023-11 約 1–2 小時、2026-01 約 3 小時，以及乾淨 9 場的 0–3 小時，均為待重驗的目視估計。
