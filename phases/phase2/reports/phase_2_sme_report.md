# 第二階段：SME 能量輸入代理量

## 狀態

Phase 2 已結案 [done]。P2.6 final 是唯一交付版本；F10.7A 使用 CelesTrak `F10.7_OBS_CENTER81`，不自行平均前 81 日。此處的完成僅指資料與描述性 QC，不能推論因果延遲。交付證據見[最終報告](phase_2_final_report.md)，方法與資料契約見[計畫](../docs/plans/PLAN.md)及[資料血緣](../docs/lineage/phase_2_storm_dataset.md)。

P2.6 final 在 `t0 - 12 h` 至 `t0 + 24 h` 選平滑 peak，對 25 場各保存一列描述性 QC。9 場 density peak 早於 SME peak，表示多脈衝 pairing 未解決；這是本階段的已記錄限制，不是待完成的 Phase 2 工作。

研究範圍是建立可重現的三年分鐘資料集。這不是即時預報系統，也不在本階段連接 atmospheric drag、GPR 或軌道衰減的因果主張。

## 主驅動量

延遲模型的候選主驅動量是 SuperMAG SME：

```text
Q(t) = SME(t)
```

SME 反映極區電噴流相關的能量注入，預期在時間上可領先熱層密度反應。這是待檢驗假設，不是現有資料已經證明的順序。SYM-H 反映環電流能量儲存，用於找事件強度與 `t0`，不當作延遲核的主輸入。

## P2.0–P2.2：來源、分鐘指數與事件

- SME：SuperMAG 每分鐘 `SME` 與 `SMEnum`。
- SYM-H：京都每分鐘值；`SYM-H < -100 nT` 的局部最低點是候選。
- ap：只使用已結束的 3 小時區間，不線性內插。
- F10.7：單日值使用前一日 `OBS` 或 `INT`；P2.3–P2.6 的 F10.7A 使用樣本當日來源置中 81 日值；不使用 `PRD`／`PRM` 預報值。
- 缺 SME／SYM-H 維持 NULL；不補值、不改 SYM-H 正負號。
- 相距不足 72 h 或固定鐘錶事件窗重疊的 SYM-H 最低點合併；最深者是 `t0`。

三年 P2.2 有 25 場候選，其中 24 場是複合事件。`storm_id` 是訓練與測試未來切分的最小單位；不能隨機切分鐘列。

## P2.3–P2.5：現行分鐘資料

P2.3 v5 以 SYM-H 最低點 t0 的軌道相位，保留前 31、後 62 圈的每分鐘事件資料。P2.4 v5 以 DNSAPOD 原生 30 秒位置與時間計算同位置 NRLMSIS 2.0 密度，並接到分鐘 key；25 場的 L2 與 L2／MSIS paired coverage 均 >= 80%。P2.5 v2 的 `storm_minute_analysis_v2` 有 217,912 列，其中 `log_ratio_obs` 有 217,613 列非 NULL。

F10.7A 直接使用樣本當日 CelesTrak `F10.7_OBS_CENTER81`，不自行平均前 81 日；每日 F10.7 仍取前一 UTC 日。只接受 `OBS`／`INT`，不接受 `PRD`／`PRM`。置中值含未來觀測，僅供離線回溯；Phase 1 P1.6 的 trailing feature 不變。

## P2.6 final：平滑與限定 peak 候選窗 [done]

唯一現行輸出為 `phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite`，直接從 P2.5 v2 建立。P2.5 raw 分鐘資料不變；`storm_minute_smooth_v4` 保存 raw／smoothed 候選分鐘，`storm_minute_peak_qc_v4` 保存每場一列 peak QC。

- SME：15-minute centered mean。
- 密度殘差 `log_ratio_obs`：`u_rel_rad +/- pi` 的 centered one-orbit mean。
- 平滑窗口須完整且有效值比例 >= 80%；SYM-H `t0` 仍由 raw 最低點定義。
- Peak 僅在 `t0 - 12 h` 至 `t0 + 24 h` 的閉區間選取，不在 P2.3 約前 48／後 97 小時的完整資料保存窗取峰；同值取較早分鐘。

結果為 25 場、54,025 筆候選分鐘；16 場 SME peak 早於密度 peak，9 場相反。`phases/phase2/figures/P2.6/` 直接保存 25 張逐場圖，每張含 SME、密度殘差與 SYM-H 三個 panel，顯示 raw 與 smoothed 曲線；不設圖版本子目錄。這仍是描述性全域峰 QC；複合事件可能把不同 pulse 配成一對，不能當作因果延遲或軌道衰減標籤。
## 物理角色

SME 反映極區電噴流相關的能量注入，用來描述密度反應的時間。SYM-H 反映環電流造成的全球對稱水平磁場擾動，用來定義事件 `t0` 與描述磁暴強度。SYM-H 恢復時間可長於密度，因此不要求密度峰值晚於 SME 的同時也必須早於 SYM-H 最低點。

## 後續敏感度測試 [deferred]

延遲模型建立後，固定相同事件切分、密度標籤與評估方法，只替換驅動量：SYM-H、階梯式 ap、Kyoto AE，以及 `log(1 + SME/Q0)`。`Q0` 使用平靜期 SME 中位數。預期結果只能作為待驗證假設；若 SYM-H 的最佳延遲或誤差不符合預期，必須保留實際結果，不能為符合敘述而調整資料。

複合事件不能只取候選窗各自的全域最大值，就宣稱 SME 峰與密度峰屬於同一個能量脈衝。25 場 QC 都是描述性輸出，不建立因果延遲標籤。
