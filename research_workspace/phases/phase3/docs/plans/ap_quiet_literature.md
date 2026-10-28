# Phase 3：平靜 ap 輸入的文獻核對

狀態：[retained]。這是 Phase 3 結案前的文獻核對記錄。文獻提供「平靜條件的參考值」與「安靜日的判準」，**沒有提供一個對所有 Swarm-A 磁暴都正確的 `ap_quiet` 平均公式**；本研究最終採用的操作規則與結果以[Phase 3 最終報告](../../reports/phase_3_final_report.md)為準。

## 先分清楚兩種數值

- 小寫 `ap` 是每 3 小時一筆的行星磁活動指數。大寫 `Ap` 是同一 UTC 日八筆 `ap` 的算術平均；兩者沒有密度單位。[GFZ：Related Indices](https://www.gfz.de/en/section/geomagnetism/data-products-services/kp-index/related-indices)
- `pymsis` 的 storm-time 模式使用七欄 `aps`：當日 `Ap`、目前與前 3／6／9 小時的 `ap`，以及前 12–33、36–57 小時各八筆 `ap` 的平均。僅傳一個日 `Ap` 不是同一種時間輸入。`geomagnetic_activity=-1` 才使用後六欄；目前文件的預設模型版本是 2.1，若本研究指定 2.0，呼叫時應明寫。[pymsis `calculate` 文件](https://swxtrec.github.io/pymsis/reference/generated/pymsis.msis.calculate.html)

## 文獻中的「平靜」不是同一個定義

| 來源 | 文獻實際做法 | 對本研究的限制 |
| --- | --- | --- |
| Emmert 等，NRLMSIS 2.0 | 在圖示的「全球平均」參考條件採 `Ap=4`，並稱為平靜磁活動。 | `4` 可作固定平靜情境，但文獻沒有要求每場磁暴都取 `4`，也沒有證明它是本資料的最佳值。[原論文](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020ea001321) |
| Billett 等，2024 | 用 NRLMSIS 2.0 的 `Ap=3` 代表 2022 年 2 月磁暴的平靜背景，沿 Swarm-C、GRACE-FO 軌道和實測密度比較；作者指出它接近磁暴前兩天實測值。 | 這是**單一事件、兩顆衛星的操作選擇**，不能直接推成 3 年或 12 年通用標準。作者也指出即使磁活動低，平靜日高緯密度的基準仍可能低估，估計造成最多約 20% 的不確定度。[原論文](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023SW003748) |
| Picone 等，NRLMSISE-00 | 模型評估把 `Ap≤10` 列為 quiet、`Ap≥50` 列為 active；quiet 組使用日 `Ap`，其餘組使用 3 小時歷史。 | 這是**評估資料分組**，不是要求將 MSIS 的輸入固定為 `10`。[原論文 §3](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2002ja009430) |
| GFZ Q/D days | 每月按八筆 `Kp` 的和、平方和、最大值排序，選相對安靜日。入選日若 `Ap>6`，仍標成「不真正平靜」；`Ap≤6` 且出現過高的 `Kp` 也會被標記。 | `Ap≤6` **單獨不是**合格安靜日的充分條件；Q-day 是逐月相對排名，須連同附註標記閱讀。[GFZ：Q/D days](https://www.gfz.de/sektion/geomagnetismus/daten-produkte-dienste/kp-index/q/d-days-1) |

Wang 等（2022）以 2002–2008 年 CHAMP 的 265 場磁暴，研究密度相對 AE／Dst 的延遲，並校正 NRLMSISE-00。摘要報告密度對 AE 的延遲：弱、中等磁暴約 0–1 小時，強磁暴約 2–4 小時。**這篇不能當成選擇 `ap_quiet=4`、`6` 或某個平均窗口的依據**；它回答的是響應時間與模型校正問題。[論文正式版與摘要，MIT](https://dspace.mit.edu/entities/publication/53333908-166b-4184-bd92-0121d26668f4)

## 對 3 年試算的建議（方法推論，非文獻規定）

1. 先把「平靜 MSIS」明確定義成反事實背景：同一軌道位置、時間及實際 F10.7，磁活動歷史固定為預先指定的平靜值。主方案可試 `ap_ref=4`，因它有 NRLMSIS 2.0 的平靜參考先例。storm-time 模式七欄全設為 `4` 是**本研究的操作定義**，不是論文直接規定。[Emmert 等](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020ea001321)、[pymsis 文件](https://swxtrec.github.io/pymsis/reference/generated/pymsis.msis.calculate.html)
2. 把 `ap_ref=6` 與資料導出的候選值作敏感度檢查。若要用事件前 `[-3,-2]` 天的代表值，先檢查該段是否真的安靜；不可因它在事件前，就自動稱為平靜。可另以 GFZ Q-day 分類輔助檢查，但需注意 Q-day 的月內排序與附註標記。[GFZ：Q/D days](https://www.gfz.de/sektion/geomagnetismus/daten-produkte-dienste/kp-index/q/d-days-1)
3. 報告每個候選值下的 `ρ_MSIS,q`、平靜窗口的 `ln(ρ_L2/ρ_MSIS,q)`、擬合 `G` 與 `τ` 及留一事件誤差。只在 3 年試算後預先鎖定規則，再做 12 年驗證；避免用 12 年測試表現反向挑平靜值。

## 保留的適用範圍

- 原計畫中的 `ap_quiet` 若指每場 `[-3,-2]` 天中位數，必須說清它是對 3 小時 `ap`、日 `Ap`，還是七欄各自取代表值。三者並不等價；這不是本 phase 的採用規則。
- 固定 `ap_ref` 能隔離 MSIS 中隨磁暴變化的 ap 驅動，**不能保證** `ρ_MSIS,q` 已包含所有真實背景變化。事件前的衛星密度偏差仍須另行估計。
- 若標榜即時預報，任何安靜日選取與偏差校正只能使用當時已知的資料；完整月份的 Q-day 排名及事件後資料僅適合回顧分析。
