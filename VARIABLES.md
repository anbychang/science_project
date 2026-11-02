# Phase 0--7 共用變數定義

狀態：[working]。本頁涵蓋 Phase 0–7 已識別的公式輸入、輸出、索引與保存欄位；`[verified]` 表示列明的核對範圍成立，`[issue]` 與 `[partial]` 表示仍有契約或證據缺口。術語與產品狀態見 [GLOSSARY.md](GLOSSARY.md)，逐式證據見 [公式稽核](docs/formula_audit.md)。同一字母在不同模型不得省略版本或下標而混用。

## 各 Phase 的量與傳遞

### 主線報告的局部符號對照

Phase 3–5 的 $R$ 只用下列名稱跨報告傳遞；舊報告的裸 $R_k$ 僅在該報告已宣告的局部模型內成立。

| 名稱 | 如何取得 | 去向 |
| --- | --- | --- |
| $R_{k,\mathrm{RQ}}$ | Phase 3 暴前 quiet run 的 L2／quiet MSIS 原生比值中位數 | M1 基線、Phase 4 起始值、Phase 5 V2 Ridge 輸入 |
| $R_{\mathrm{fit},k}^{\mathrm{V1}}$ | Phase 4 V1 以同場 L2 與逐場 $\tau_k^{\mathrm{V1}}$ 擬合 | V1 D-model、舊 Phase 5 D-model 殘差試驗 |
| $R_{\mathrm{fit},k}^{\mathrm{V2}}$ | Phase 4 V2 以同場 L2 與共同 $\tau_{\mathrm{V2}}$ 擬合 | V2 D-model、Phase 5 V2 Ridge 的 $\Delta R$ 標籤 |
| $\widehat R_k^{\mathrm{LOO}}$ | Phase 5 V2 每折只用其他 20 場訓練，對留出場估計 | 25 場 Ridge 密度圖、Phase 6 |
| $\widehat R_k^{\mathrm{full25}}$ | 全 25 場 Ridge 係數對新事件估計 | Phase 7；新事件的 $R_{k,\mathrm{RQ}}$ 也須重新計算 |

| 報告 | 報告內簡寫 | 跨報告統一記法與來源 |
| --- | --- | --- |
| Phase 1／1R 軌道分析 | `u`；圖上的 `u_plot` | $u=\operatorname{unwrap}(\omega+M)$ 用於圈數與 OLS；$u_{\mathrm{plot}}=u\bmod 2\pi$ 只供顯示。$t_{\mathrm{ref}}$ 是局部 OLS 時間原點，不是事件 $t_0$。 |
| Phase 2／2R 最終報告（凍結） | 事件最低點、相對時間、相位窗口 | $t_0$ 是 SYM-H 事件最低點；$t_{\mathrm{rel}}=t-t_0$；相位窗口依連續 $u$ 定界，不依圖上的模 $2\pi$ 相位。 |
| Phase 3 最終報告（凍結） | $R_k$、$G$、共同 $\tau$、M1 | $R_{k,\mathrm{RQ}}$ 是暴前 quiet-run 倍率；全 25 場擬合的 $G_{\mathrm{P3}}^{\mathrm{pooled}}$ 產生 pooled M1；排除當場重估的 $G_{\mathrm{P3},-k}$ 產生 held-out M1。兩者共用 $\tau_{\mathrm{P3}}=4.65\ \mathrm h$ 與同場 $R_{k,\mathrm{RQ}}$。 |
| Phase 4 V1 D-model | A／C 的 $R_k$；B／D 的 $R_k$、$G$、$\tau_k$ | A／C 固定 $R_{k,\mathrm{RQ}}$；D-model 為 $R_{\mathrm{fit},k}^{\mathrm{V1}}$、$G_{\mathrm{V1}}$、$\tau_k^{\mathrm{V1}}$。B 的自由 $R_k$ 是 B 模型估計值，不能當 D-model 結果。 |
| Phase 4 V2 | $R_k$、$G$、共同 $\tau$、$\rho_{\mathrm{quiet}}$ | $R_{\mathrm{fit},k}^{\mathrm{V2}}$、$G_{\mathrm{V2}}$、$\tau_{\mathrm{V2}}=4.75\ \mathrm h$、$\rho_{\mathrm{MSIS,q}}$；與 V1 參數分開。 |
| Phase 5 舊 GPR 終版 | M1、D-model、對數殘差 | Trial10–12 的訓練基底是 Phase 3 pooled $\rho_{\mathrm{M1}}$；舊 Trial1–5 的 D-model 殘差基底是 Phase 4 V1 $\rho_{\mathrm D}^{\mathrm{V1}}$。兩者與 Phase 4 V2 的 $R_{\mathrm{fit},k}^{\mathrm{V2}}$ 無直接替換關係。 |
| Phase 5 V2 Ridge | 原本 $R_k$、目標 $R_k$、預測 $\widehat R_k$ | 依序為 $R_{k,\mathrm{RQ}}$、$R_{\mathrm{fit},k}^{\mathrm{V2}}$、留場 $\widehat R_k^{\mathrm{LOO}}$；保存的全 25 場係數產生新事件 $\widehat R_k^{\mathrm{full25}}$。 |
| Phase 6 最終報告 | `rho`、`K_n`、`B_eff`、`Delta a` | $\rho$ 須依 P6.1／P6.2／P6.3 註明 L2／M0／Ridge 留場來源；$K_n$ 與 $\Delta a_n$ 使用同一密度序列，$B_{\mathrm{eff}}$ 固定。 |
| Phase 7 五場計分 | M0／Ridge、逐圈誤差 | Ridge 密度使用 $\widehat R_k^{\mathrm{full25}}$ 與 V2 的 $G,H$；沿用 Phase 6 固定 $B_{\mathrm{eff}}$，不是 Phase 6 留場 $\widehat R_k^{\mathrm{LOO}}$。 |

Phase 5 舊 Trial10–12 的 2,235 筆連續三圈中心點，是 V2 Ridge 密度庫 214,907 筆相位分鐘中的子集合；25 場的 `{storm_id,time_us}` 全部對上，子集 L2 密度逐值相同。兩報告的 RMSE 使用不同取樣集合，不可只憑「25 場」或同名密度欄比較。

| 上游 → 下游 | 關係 | 讀取時要保留的區別 |
| --- | --- | --- |
| Phase 2 `rho_msis_kg_m3` → Phase 3 `rho_msis_full_phase_kg_m3`；Phase 3 `rho_msis_quiet_phase_kg_m3` → Phase 4 D-model → Phase 5 V2 Ridge | Phase 3 在相同原生 L2 配對樣本上，將 Phase 2 的 full MSIS 做中心相位平均；quiet MSIS 則把七個 $ap$ 固定為 4 重新計算後做相同平均 | full 與 quiet 是不同密度；Phase 6 M0 取 full，D-model 與 Ridge 取 quiet |
| Phase 3 `r_candidate` → Phase 5 V2 `event_input.r_phase3` | 原 25 場同 `storm_id` 保存值相同 | Phase 7 新事件的同名 `r_phase3` 是按 Phase 3 方法重新計算，不是查原 25 場 |
| Phase 4 V2 `phase4_v2_events.r_fit` → Phase 5 V2 `event_input.r_fit` | 原 25 場同 `storm_id` 保存值相同 | 這是 V2 同場回溯擬合目標；V1 的 `r_fit` 是另一組值 |
| Phase 5 V2 探索 `phase4_v2_r_targets_v1` → 現行 `phase4_v2_r_targets_v2` | 兩份快照各有相同 25 場，但舊 v1 與現行 V2 `r_fit` 最大絕對差 $1.69\times10^{-13}$、$G$ 差 $2.08\times10^{-16}$ nT$^{-1}$；v2 快照與現行 Phase 4 V2 事件表逐值相同 | 舊 GPR 報告與試驗使用 v1 快照；正式 Ridge 讀 v2 快照並核對現行 V2。兩版近似相同不等於逐值相同 |
| Phase 5 V2 `event_input.{r_phase3,r_fit}` → Ridge 留場 `heldout_prediction.r_pred` | 訓練標籤為 $\Delta R_k^{\mathrm{V2}}=R_{\mathrm{fit},k}^{\mathrm{V2}}-R_{k,\mathrm{RQ}}$；留場預測再加回同場 $R_{k,\mathrm{RQ}}$，得到 $\widehat R_k^{\mathrm{LOO}}=R_{k,\mathrm{RQ}}+\widehat{\Delta R}_k^{\mathrm{LOO}}$ | `r_fit` 只在訓練場作標籤與留場評分；計算留場 `r_pred` 時使用的是該場 `r_phase3` 與其他場訓練出的修正量，不可把同場 `r_fit` 當輸入 |
| Phase 5 V2 `heldout_prediction.r_pred` → `density_comparison.r_ridge` → Phase 6 Ridge density | 密度庫 214,907 筆 `r_ridge` 各等於同場 25 筆留場 `r_pred` 之一；Phase 6 讀的是由此倍率產生的密度 | 留場 $\widehat R_k^{\mathrm{LOO}}$ 不等於全 25 場模型對新事件的 $\widehat R_k^{\mathrm{full25}}$ |
| Phase 3／Phase 4 V1／V2 同事件分鐘的 L2、quiet MSIS | 25 場、214,907 個鍵和值相同 | 三庫同名 `h_phase_nt` 的時間常數不同；V1／V2 的 `r_fit`、$G$ 也不同 |

| Phase | 來源量 | 中間量與輸出 | 不能跨用的版本 |
| --- | --- | --- | --- |
| 0 | SP3 `{time, frame, position_m, velocity_m_s}`、DNSAPOD、F10.7、$ap$ | UTC state、GCRS 數值 state、MSIS density | SP3 GPS epoch 先轉 UTC；`GCRF` 是專案輸出標籤，實際座標庫為 GCRS |
| 1／1R | POD state、Orekit mean elements | $a_{\mathrm{osc}}$、$a_{\mathrm{mean}}$、$u$、3／5 圈 raw／joint $b_1$ | osculating 與 mean 半長軸、局部 $t_{\mathrm{ref}}$ 與事件 $t_0$ |
| 2／2R | raw SYM-H、SME、L2／MSIS、Phase 1 相位 | $t_0$、$t_{\mathrm{rel}}$、`log_ratio_obs`、平滑 peak 與 lag | 2R 的 49 場候選與 46 場可用相位事件；描述 peak 不是 causal lag |
| 3 | Phase 2 事件與相位、L2、quiet MSIS、SME | $R_{k,\mathrm{RQ}}$、$H_{4.65}$、$G_{\mathrm{P3}}^{\mathrm{pooled}}$／$G_{\mathrm{P3},-k}$、兩版 $\rho_{\mathrm{M1}}$ | fixed-R 歷史基線；不可把 M1 當現行 D-model |
| 4 v1／v2 | 同批 L2、quiet MSIS、SME | 各版 $R_{\mathrm{fit}}$、$G$、$H$、$\rho_{\mathrm{V1/V2}}$ | v1 每場 $\tau_k$；v2 共同 $\tau=4.75$ h，參數不得交叉代入 |
| 5／5 V2 | 歷史 M1 圈密度、Phase 3 $R$、Phase 4 v2 $R$ | Trial10–12 的 $m,e,q,s$；V2 的 $\Delta R$、$\widehat R$、$\rho_{\mathrm{Ridge}}$ | GPR 各 Trial 的資料條件不同；Ridge 留場圖與全 25 場重擬合參數不同 |
| 6 | L2／M0／Ridge density、POD mean $a$ | $K$、固定 $B_{\mathrm{eff}}$、分鐘與事件 $\Delta a$、逐圈 $e$／MAE | P6.1 全三年擬合、P6.2/3 事件 endpoint、P6.4 逐圈主分數的分母不同 |
| 7 | 五場外測事件、M0／Ridge density、固定 $B_{\mathrm{eff}}$ | 453 個圈間 $e$、每場與 pooled MAE／RMSE | 五場計分集合不含 2018 舊試算；不可與 Phase 6 25 場分數混為同一樣本 |

## 符號關係與禁止混用

```text
POD state {time, frame, position_m, velocity_m_s}
  -> two-body a_osc；另經 Orekit B-L -> a_mean, omega, M -> u -> 3/5 圈 OLS b1
  -> Phase 6 分鐘 mean a_n -> Delta a_POD
DNSAPOD 原始 phi_deg, lambda_deg -> 舊 loader 同單位欄位 -> pymsis deg 邊界
  -> 若建立新介面，loader 轉 phi_rad, lambda_rad；pymsis 呼叫點再轉 deg
SYM-H minima -> P2.2 合併窗口 metadata；最深點 -> t0
  -> P2.3 前 31／後 62 圈相位資料窗 -> t_rel 與每分鐘特徵
  -> P2.6 t0 前 12／後 24 h peak 候選窗
SME -> X=SME-65 nT -> H_tau -> Phase 3/4 的 exp(G H_tau)
L2 + quiet MSIS -> Phase 3 R_RQ 與 Phase 4 R_fit
quiet MSIS * R_fit * exp(G H_tau) -> Phase 4 D-model density
quiet MSIS * Ridge R_hat_LOO * exp(G_V2 H_V2) -> Phase 5 V2 / Phase 6 density
quiet MSIS * Ridge R_hat_full25 * exp(G_V2 H_V2) -> Phase 7 external density
L2 或 M0 或 Ridge density + POD a -> K -> -B_eff K -> Phase 6/7 誤差
```

| 關係 | 必須區分的量 | 原因 |
| --- | --- | --- |
| `time_us` → $t_0$ → $t_{\mathrm{rel}}$ | POD 觀測 epoch、事件最低點、相對時間 | 同為時間值，來源和零點不同；Phase 1 OLS 的 $t_{\mathrm{ref}}$ 是計算批次來源首筆，不是 $t_0$ |
| $u$ → `u_rel_rad` → 相位平均 | 連續 mean-orbit phase、事件相對 phase、中心窗口 | 相位差可定義圈數，但相位平均會讀錨點之後，不能當即時輸入 |
| $q_{\mathrm{obs}}$ 與 $y_{k,i}$ | 對數比的中心平均、兩條密度先中心平均後取比 | 一般不相等：$\operatorname{mean}(\ln A/B)\ne\ln(\operatorname{mean}A/\operatorname{mean}B)$ |
| Trial10／11 的 $m_{k,n+1}$ 與測試場 $\rho_{\mathrm{L2},k,n}$ | $m_{k,n+1}=\ln\rho_{\mathrm{M1},k,n+1}$ 是下一圈 M1 模型密度；L2 是當圈觀測標籤 | `centered_log_curvature`、`centered_log_slope` 均含下一圈 M1，屬事後完整曲線特徵；留場 GPR 推論未讀測試場 L2，但不因此成為當圈即時預報 |
| P2 的 `log_ratio_smooth` 與 P3／4 的相位加權 $\bar H_\tau$ | 前者逐分鐘值等權並以有效分鐘數／窗內分鐘數判 80%；後者依每分鐘原生 L2 配對數 0／1／2 加權，覆蓋率以原生預期筆數為分母 | 兩者雖都用 $u\pm\pi$，輸入量、權重與分母不同；不能把 P2 peak 平滑量當作 Phase 3／4 模型響應 |
| Phase 1 `space_weather` ap 與 DNSAPOD M0 `ap_values` | 前者用 CelesTrak 當前格／當日 `AP_AVG`，後者用 GFZ 上一已完成格／前一日八格平均 | 2023-08-03 05:01:30 UTC，Phase 1 `space_weather` 所在 03:00 格保存 `[5,6,5,6,7,12.25,7]`；同一 DNSAPOD 原生時刻依 GFZ 重建的 M0 driver 為 `[11.875,5,6,7,22,11,6.625]`。即使改成 pymsis 時序，當日 daily ap 的 CelesTrak `AP_AVG=5` 與 GFZ 八格平均 4.75 仍不同，不能把兩份來源直接互換 |
| `f107a_sfu`（MSIS）與 `quiet_f107a_last81_sfu`（Ridge） | Phase 0 `F10.7_OBS_CENTER81` 是樣本日置中 81 日平均；Phase 5 V2 的特徵讀校準段前最近的 `f107a_last81_sfu`，是末 81 日平均 | 兩者同為 sfu，卻有不同時間支持與可用時刻；前者含樣本後日值，後者數值只依已過日值，但選校準段仍需事後事件資訊。不得以同名 F10.7A 當成相同輸入 |
| `space_weather.f107a_sfu` 與 `swarm_a_phase_harmonic_features_v2.f107a_sfu` | 前者是樣本日 `F10.7_OBS_CENTER81` 的置中 81 日平均；後者由 `align_space_weather()` 取前一 UTC 日 `f107a_last81_sfu` 的末 81 日平均 | 兩個 SQLite table 使用完全相同欄名與 sfu 單位，時間支持卻不同；Phase 1 特徵另存 `f107a_source_time_us`，不得與 Phase 0／Phase 3 MSIS driver 的置中 F10.7A 直接聯接 |
| $R_{\mathrm{RQ}}$、$R_{\mathrm{fit}}^{\mathrm{V1}}$、$R_{\mathrm{fit}}^{\mathrm{V2}}$、$\widehat R^{\mathrm{LOO}}$、$\widehat R^{\mathrm{full25}}$ | 暴前 L2 校準、兩版同場擬合、留場及全 25 場重擬合估計 | 校準資料、時間常數與用途不同；不可只寫 $R_k$ 互換 |
| Trial1 retained $\rho_{\mathrm{phys},-k}$ 與 Phase 3 $\rho_{\mathrm{M1}}$ | retained 舊 LOSO：$\bar\rho_{\mathrm{MSIS,q},k}R_{k,\mathrm{RQ}}\exp(G_{-k}H_{\tau_{-k},k})$；Phase 3 M1 另用固定 $\tau=4.65$ h 及 Phase 3 pooled／held-out $G$ | retained 的 $G_{-k}$、$\tau_{-k}$ 在其他 24 場上擬合，但 $R_{k,\mathrm{RQ}}$ 仍讀該場 L2 暴前校準；同鍵不代表同模型或全鏈外測 |
| $G_{\mathrm{P3}}^{\mathrm{pooled}}$／$G_{\mathrm{P3},-k}$、$G_{\mathrm{V1}}$、$G_{\mathrm{V2}}$ 與對應 $H_\tau$ | 各模型的 gain 與其響應 | P3 兩種 $G$ 都配 $H_{4.65}$；V1 配逐場 $H_{\tau_k^{\mathrm{V1}}}$，V2 配共同 $H_{\tau_{\mathrm{V2}}}$。$G$ 的單位為 nT⁻¹，$H$ 為 nT |
| $\mu_{\mathrm{P1/P6}}$、$\mu_{\mathrm{BL}}$ 與 Ridge $\mu_j$ | 前兩者為地球重力參數（m³/s²）；後者是第 $j$ 個訓練因素的平均，單位隨因素 | 重力常數已有兩個不同數值，Ridge 的 $\mu_j$ 又不是重力參數；代入 $\sqrt{\mu a}$ 時只能使用前者指定的版本 |
| Phase 3 pooled $G$ 與 Phase 4 各版 $G$ | $G_{\mathrm{P3}}^{\mathrm{pooled}}$ 固定暴前 $R_{k,\mathrm{RQ}}$，把所有有效分鐘合併估計；$G_{\mathrm{V1}}$、$G_{\mathrm{V2}}$ 則與各版同場 $R_{\mathrm{fit},k}$ 聯合估計，對事件等權 | 三者使用的 $R$ 來源、$H$ 版本與事件權重不同；不能因同為 nT⁻¹ 就跨版代入。完整估計式見[公式稽核](docs/formula_audit.md) |
| $\alpha_\tau$、`RIDGE_ALPHA` | Phase 3／4 指數濾波權重；Phase 5 V2 Ridge 正則化強度 | 兩者恰好都常寫成 alpha，完全不是同一參數；$\alpha_\tau$ 由 $\tau$ 和 60 s 算出，`RIDGE_ALPHA=1.0` 是固定模型設定 |
| $\rho_{\mathrm{L2}}$、$\rho_{\mathrm{M0}}$、$\rho_{\mathrm{MSIS,q}}$、$\rho_{\mathrm{M1}}$、$\rho_{\mathrm{V1/V2}}$、$\rho_{\mathrm{Ridge}}$ | 觀測、完整 MSIS、quiet MSIS、歷史回溯、兩版 D-model、留場或外測模型（須註明參數版） | 密度皆為 kg/m³，但不能只憑單位或分鐘鍵判定可互換 |
| $K_n$、$N_{\mathrm{orbit},k}$、$N_{\mathrm{event}}$ | 分鐘累積積分核、事件 $k$ 的有效圈間區間數、事件數 | Phase 4 的 $N_k$ 是有效相位分鐘數；Phase 6／7 逐圈分母統一寫 $N_{\mathrm{orbit},k}$，不能互代。$K_n$ 不是事件數 |
| $e$、$e^{\mathrm D}_{k,n}$、$e_{\mathrm{model},k,j}$ | mean eccentricity、密度無單位對數殘差、半長軸下降誤差 m | 只寫 $e$ 會把軌道元素、Phase 5 訓練標籤與 Phase 6／7 評分混在一起；計算與表格須附版本或下標 |
| $b_0,b_1$、Ridge $b_0,b_j$ | Phase 1 OLS 截距 m／斜率 m/s；Phase 5 V2 $\Delta R$ 截距／標準化因素係數，皆無單位 | 兩者共用字母但量綱與訓練資料不同；Ridge 的 `alpha=1` 也不是 Phase 3／4 的濾波 $\alpha_\tau$ |

## 時間、索引與軌道

| 符號／欄位 | 定義與單位 | 適用範圍與界線 | 狀態 |
| --- | --- | --- | --- |
| `time_us` | UTC epoch microseconds；一筆資料的 key | 各表另以 lineage 指明觀測時刻、分鐘中心或窗口端點；不可只由整數推斷語意 | [verified: contract] |
| $k$ | 磁暴事件索引，無單位 | Phase 3–7；同一事件內的分鐘與圈另用索引 | [verified] |
| $i,j,n$ | 局部樣本索引，無單位 | 在每條公式附近定義；不同 Phase 不保證相同取樣尺度 | [verified: scope] |
| $a$ | POD mean semi-major axis，m | Phase 6 的積分核使用觀測 POD $a$，不是傳播軌道的預測值 | [verified] |
| $a_{\mathrm{osc}}$／`semi_major_axis_m` | 由單一 GCRF state 的 two-body 比能算出的瞬時 osculating 半長軸，m | Phase 1 P1.3；與 Brouwer-Lyddane `mean_semi_major_axis_m` 及 Phase 6 分鐘平均 $a_n$ 不同 | [verified: code and sampled row] |
| $r$、$v$、$\mathcal E$ | GCRF 位置模長 m、速度模長 m/s、比能 $v^2/2-\mu_{\mathrm{P1/P6}}/r$（m²/s²） | $a_{\mathrm{osc}}=-\mu_{\mathrm{P1/P6}}/(2\mathcal E)$；只接受 $r>0$、$\mathcal E<0$ 的 bound state。保存的 `swarm_a_states` 是 ITRF 原始向量，須先轉換位置及速度；不可將其分量直接代入此式 | [verified: code and cross-time sampled output] |
| $a_{\mathrm{mean}}$／`mean_semi_major_axis_m` | Orekit Brouwer-Lyddane 平均軌道半長軸，m | Phase 1/1R 相位與 OLS 的 $a$ 輸入；不等於 P1.3 瞬時 $a_{\mathrm{osc}}$ | [verified: code] |
| $J_2,\ldots,J_5$、$M_2$ | Orekit Brouwer-Lyddane mean-element conversion 使用的地球 zonal gravity 項與經驗沿軌項 | provider 取未正規化 gravity field 的 degree/order `(5,0)`；`M2=0.0`，迭代容差 $10^{-13}$、上限 5,000 次。這些是特定平均化模型的設定，不代表本專案仍有獨立 J2 force 或 RK4 propagator | [verified: code/config] |
| $e$、$I$、$\Omega$ | Brouwer-Lyddane mean eccentricity（無單位）、inclination（rad）、ascending-node right ascension（rad） | 與 $\omega,M$ 同屬一個 mean element state；Phase 1 的 $u=\operatorname{unwrap}(\omega+M)$ 不使用 $I$ 或 $\Omega$ | [verified: schema/code] |
| $E$、$\nu$ | 同一 mean element state 的 eccentric anomaly、true anomaly，rad | `mean_eccentric_anomaly_rad`／`mean_true_anomaly_rad`；$M=E-e\sin E$，$\nu=\operatorname{atan2}(\sqrt{1-e^2}\sin E,\cos E-e)$（角度按 $2\pi$ 等價）。$M,E,\nu$ 是不同 anomaly，均不能代替 Phase 1 相位式中的 $M$ | [verified: code and saved-row identities] |
| $L_M,L_E,L_\nu$ | Orekit 回傳的 mean、eccentric、true longitude，rad | $L_M=\Omega+\omega+M$、$L_E=\Omega+\omega+E$、$L_\nu=\Omega+\omega+\nu$；保存欄位依序為 `mean_longitude_rad`、`mean_eccentric_longitude_rad`、`mean_true_longitude_rad`。Phase 1 的 $u=\omega+M$ 不含 $\Omega$，不能直接拿 $L_M$ 取代 | [verified: code and saved-row identities] |
| $e_x,e_y,h_x,h_y$ | Orekit mean equinoctial 元素，皆無單位 | $e_x=e\cos(\Omega+\omega)$、$e_y=e\sin(\Omega+\omega)$、$h_x=\tan(I/2)\cos\Omega$、$h_y=\tan(I/2)\sin\Omega$；對應 `mean_equinoctial_ex/ey/hx/hy`，不是 Phase 6 的誤差 $e_{\mathrm{model}}$ | [verified: code and saved-row identities] |
| $n_{\mathrm K}$、$T_{\mathrm K}$ | mean orbit 的 Keplerian mean motion（rad/s）與 period（s） | `mean_keplerian_mean_motion_rad_s`、`mean_keplerian_period_s` 滿足 $n_{\mathrm K}T_{\mathrm K}=2\pi$；這是由 mean orbit 回傳的 Keplerian 量，不等於逐圈實際 UTC 週期或 Phase 1 OLS 視窗長度 | [verified: code and saved-row identity] |
| `{time, frame, position_m, velocity_m_s}` | 單一軌道狀態；UTC 時刻、座標系、三維位置 m、三維速度 m/s | Phase 0 載入與座標轉換的共同資料形狀；`frame` 決定各向量分量的意義 | [verified: code contract] |
| `frame="ITRF"`、`frame="GCRF"` | 專案的地固／地心慣性 state 標籤 | 原始 SP3 另有 `IG*` frame label；Phase 0 實際用 Astropy ITRS→GCRS，輸出標記 `GCRF` 供 Orekit 使用。GCRS 與嚴格 GCRF 不應宣稱數學恆等；2014–2026 每年一筆跨庫抽查，位置最大分量差 0.00217–0.02524 m，速度最大分量差 $4.24\times10^{-6}$–$6.07\times10^{-5}$ m/s。另取每年首筆 raw state 13 點直接算 P1.3 的 two-body $a_{\mathrm{osc}}$，兩框架路徑最大絕對差 0.001736 m；同一 13 點送入同版 Orekit B-L mean-element 轉換，mean $a$ 最大絕對差 0.001733 m。兩批皆為抽樣，非全時段誤差上界，也不驗證兩框架嚴格等價 | [verified: code and sampled impact; frame equivalence partial] |
| `position_m`、`velocity_m_s` | 同一 `frame` 下的三維位置與速度向量，m、m/s | ITRF→GCRF 須同時轉換位置與速度；不能只旋轉位置 | [verified: code contract] |
| `f107_sfu` | 前一 UTC 日的 F10.7 太陽電波通量，sfu | MSIS 的 daily driver；不等於當日值 | [verified: loader] |
| `f107a_sfu` | 樣本當日置中 81 日 F10.7 平均，sfu | MSIS 的離線 driver；含樣本後觀測 | [verified: loader] |
| `f107a_last81_sfu` | 截至來源日的末 81 日 F10.7 平均，sfu | 與置中 `f107a_sfu` 定義不同；其資料延遲仍依來源可用性判定 | [verified: loader] |
| `sp3_frame_label`、`time_system` | POD 原始 SP3 header 宣告的 IGS 地固座標實現、時間尺度字串 | 現存來源 provenance 的 4,554 筆 `time_system` 都為 `GPS`；`IG*` label 對應載入 state 的泛稱 `ITRF`，不是 GCRF | [verified: source provenance] |
| `coverage_start_time_us`、`coverage_end_time_us` | 原始 SP3 宣告的首／末 epoch 轉 UTC 後的時間，us | provenance 範圍不是某個研究 Phase 實際可用樣本範圍；源檔 10 s cadence 另由 `cadence_s` 記錄 | [verified: loader/source sample] |
| DNSAPOD M0 `ap_values`、$A_q$ | 設 $s$ 為樣本 UTC 所在 3 h slot 起點，$A_q=ap$ 在 $[s-3(q+1)\,\mathrm h,s-3q\,\mathrm h)$ 的值；七欄為 `[前一 UTC 日八格平均, A_0, A_1, A_2, A_3, mean(A_4..A_11), mean(A_12..A_19)]`，$ap$ 指數無單位 | $A_0$ 是**最近已完成**格，結束於 $s$，不是樣本所在未完成格；兩組歷史平均各含八個 3 h 格。此列只定義 GFZ 驅動的 DNSAPOD M0；quiet MSIS 七欄固定 4。Phase 1 `space_weather.ap_now` 另走 CelesTrak 當前格，不得以同名七欄互換 | [verified: code and synthetic slot check] |
| `space_weather.ap_daily`、`ap_now`、`ap_3h`、`ap_6h`、`ap_9h`、`ap_12_to_33h_avg`、`ap_36_to_57h_avg` | Phase 0 原始 `space_weather` 的七個 CelesTrak ap 欄，順序為 `[樣本當日 AP_AVG, 所在 3 h 格, 前 3/6/9 h 格, 前 12–33 h 八格平均, 前 36–57 h 八格平均]`，ap 指數皆無單位 | `load_space_weather()` 在所在格時間鍵讀 CelesTrak，供 Phase 1 weather 特徵；DNSAPOD M0 的 `calc_msis_p2_4.ap_drivers()` 另讀 GFZ 並從上一已完成格、前一日 daily ap 開始。相同七欄長度不代表同一時間支持或來源 | [verified: two loaders and saved row] |
| $A_q^{\mathrm{completed}}$、$A_q^{\mathrm{MSIS}}$ | 前者為 DNSAPOD M0 的 `ap_drivers()` 的最近已完成格序列；後者為 pymsis 文件要求的當前格序列，$ap$ 指數皆無單位 | 樣本位於 $[s,s+3\,\mathrm h)$ 時，現行 `ap_values[1]` 取 $[s-3\,\mathrm h,s)$，而 pymsis 將該欄解讀為 $[s,s+3\,\mathrm h)$。因此現行前四個歷史格相對函式庫標準約後移 3 h；兩組八格平均亦隨之移動。這是已保存 M0 的模型定義差異，不可稱標準同時段 $ap$ 驅動；若修正需另立版本，不回寫凍結資料。quiet MSIS 七欄皆固定 4，不受此位移影響 | [issue: ap timing convention] |
| $A_q$ 與 pymsis 七欄的精確對應 | 沿用上列 $A_q$：標準第 1–6 個歷史欄應為 $[A_{-1},A_0,A_1,A_2,\operatorname{mean}(A_3..A_{10}),\operatorname{mean}(A_{11}..A_{18})]$；現行則為 $[A_0,A_1,A_2,A_3,\operatorname{mean}(A_4..A_{11}),\operatorname{mean}(A_{12}..A_{19})]$ | 陣列索引 0 的 daily ap 另有樣本當日與前一日之差；不能只把首個 3 h 值前移後認為其餘欄已修正。$A_{-1}$ 是樣本所在格，需等該格觀測完成才可取得 | [verified: pymsis local source and code indexing] |
| `longitude_deg`、`latitude_deg`、`altitude_m` | 現行 DNSAPOD loader 的 geodetic 經緯度 deg、高度 m | 原始 2023-08-03 CDF `UNITS` 分別為 `deg`、`deg`、`m`，密度及圈平均密度皆為 `kg/m3`；pymsis 2.0 呼叫按 WGS84 geodetic deg 與 km 解讀；來源欄位 metadata 未明列 ellipsoid，高度在呼叫點乘 0.001。$\lambda_{\mathrm{rad}}=\lambda_{\mathrm{deg}}\pi/180$、$\phi_{\mathrm{rad}}=\phi_{\mathrm{deg}}\pi/180$。此為舊資料介面，與專案內部 rad 規則衝突；改動須同步所有使用 loader 的 Phase 2/3/5/6 程式，不得使凍結 checkpoint 的原讀值靜默變單位 | [verified: source metadata and library units; issue: internal angle unit] |
| `DensityObservation.latitude_deg`、`EnvironmentTolerance.latitude_deg` | Phase 0 軌道環境比對中的緯度與容許差，deg | 此模組另有赤道穿越、升降方向與緯度索引，全部以 deg 門檻運作；與上列 DNSAPOD loader 相同單位名稱，但不是同一資料表。全庫 Python 呼叫搜尋只找到模組自身與單測，未見 Phase 0–7 生產呼叫；若啟用或改 rad，數值門檻與測試須一起換算 | [issue: dormant module angle unit] |
| `ap_last_slot_end_time_us` | MSIS 使用的最近已完成 3 h $ap$ 時段終點 UTC，us | `ap_values` 的 `now` 是前一已完成 slot，不是樣本所在未完成 slot；與 `source_time_us` 不同 | [verified: code] |
| `f107_day_utc`、`ap_daily_day_utc` | daily F10.7 與 daily $ap$ 所屬 UTC 日 | 兩者在 MSIS driver 組裝中取樣本前一 UTC 日；`f107a_sfu` 則對應樣本當日的置中平均 | [verified: code] |
| $\mu_{\mathrm{P1/P6}}$、$\mu_{\mathrm{BL}}$ | 前者為 $3.986004418\times10^{14}$ m³/s²；Orekit B-L provider `getMu()` 回傳後者 $3.986004415\times10^{14}$ m³/s²，差 $-3.0\times10^5$ m³/s² | Phase 1 P1.3 two-body 比能及 Phase 6／7 下降核用前者；Phase 1／1R mean-element 轉換用後者。兩者相對差約 $7.53\times10^{-10}$；Phase 1／1R 共 48,815,996 筆保存 mean elements 的 $n_{\mathrm K}^2a_{\mathrm{mean}}^3=\mu_{\mathrm{BL}}$ 最大相對差 $6.27\times10^{-16}$。不能把 $a_{\mathrm{osc}}$ 與 $a_{\mathrm{mean}}$ 的模型或重力參數視為相同 | [verified: runtime provider and full saved identity] |
| $\Delta t$ | 相鄰積分樣本的時間差，s | Phase 6 現行分鐘核為 60 s；遇缺口或 `chunk_id` 變更不跨越 | [verified] |
| $\omega$ | Brouwer-Lyddane mean argument of perigee，rad | Phase 1／1R 的 GCRF mean elements；不是地球自轉角 | [verified] |
| $M$ | Brouwer-Lyddane mean anomaly，rad | Phase 1／1R；不代表衛星質量 | [verified] |
| $u$ | $\omega+M$ 展開後的連續相位，rad | 完整 phase orbit 為 $2\pi$ 增量；與取模後的顯示相位區分 | [verified] |
| $b_0$ | 原始 mean $a$ 尺度下的概念 OLS 截距，m | Phase 1／1R 的 raw／H2-H3 模型；時間原點是計算批次的來源首筆，不是每個窗口左界，也不是 Phase 2 磁暴 $t_0$；此欄未保存於候選表 | [verified: code algebra] |
| $a_{\mathrm{ref}}$、$\bar d$、$c_0$ 與報告的 $b_0$ | $a_{\mathrm{ref}}$ 是每批來源首筆 mean $a$（m）；$d=t-t_{\mathrm{ref}}$（s）、$\bar d$ 是當前 OLS 視窗的 $d$ 平均；$c_0$ 是對 $a-a_{\mathrm{ref}}$ 且時間列改成 $d-\bar d$ 後求出的內部截距（m） | 報告寫在原始 $a$ 尺度、時間原點 $t_{\mathrm{ref}}$ 的概念截距為 $b_0=a_{\mathrm{ref}}+c_0-b_1\bar d$；程式只保存 $b_1$、誤差及諧波係數，沒有保存 $c_0$ 或 $b_0$。不可把內部求解係數 `coefficients[:,0]` 直接當報告的 $b_0$ | [verified: normal-equation transformation] |
| $b_1$ | mean semi-major axis 對時間的局部 OLS 斜率，m/s | Phase 1／1R 每個 10 s 錨點回看完整 3 或 5 圈；是候選而非 drag 真值 | [verified] |
| $t_{\mathrm{ref}}$ | Phase 1／1R 每個計算批次所讀來源列的首筆時刻，s 的局部計算原點 | 第一批可等於連續段首，後續批次通常由 5 圈回看需求決定更晚的起點；OLS 使用 $(t-t_{\mathrm{ref}})$，不得寫成 Phase 2 的 $t_0$；每批最多輸出 100,000 列，回看 5 圈的 batch source start 可能早於第一個輸出錨點 | [verified: code and batch-boundary samples] |
| $N_{\mathrm{orbit}}$ | Phase 1／1R 回看視窗的完整相位圈數，3 或 5，無單位 | 左界由目前 $u-N_{\mathrm{orbit}}2\pi$ 求得；不是固定分鐘長度 | [verified: code] |
| $u_*$、$f$、`orbit_N_window_start_time_us` | 目標左界相位 $u_*=u(t)-2\pi N_{\mathrm{orbit}}$；若來源相鄰相位 $u_L<u_*<u_R$，則 $f=(u_*-u_L)/(u_R-u_L)$、左界時間為 `int(round(time_us_L + f*(time_us_R-time_us_L)))`，us | 邊界若恰在來源列，直接用其 UTC key；插值時間採 Python/Numba 浮點 `round` 後存整數 us。Phase 1R 原 26 筆及另取各 chunk 1/3、2/3 列的 52 個 3／5 圈左界，按此運算順序都與保存值相同；替代寫法 `time_us_L + round(f*delta_us)` 在兩批分別有 2／7 筆差 1 us。兩批錨點選法不同，不能合併計數；取整次序不可混用。另取 Phase 1R 13 個與 Phase 1 3 個 chunk 各首／末有效五圈錨點，獨立從 mean elements 重建 3／5 圈左界共 64 筆，保存差均 0 us；Phase 1 三年分支再以全 9,469,438 個來源鍵重建，3 圈／5 圈所有有效左界共 9,464,376／9,461,003 筆差 0 us。Phase 1R 十二年分支亦逐列重建全 38,378,878 個來源鍵，3／5 圈所有有效左界共 38,356,927／38,342,299 筆差 0 us；兩分支 OLS 斜率仍僅抽樣 | [verified: code and both branches full saved boundaries] |
| $\epsilon$ | OLS 觀測半長軸減擬合半長軸的殘差，m | raw 與 H2/H3 joint 各有自身殘差，不共用同一組係數 | [verified: formula] |
| `slope_1sigma_m_s`、`residual_std_m` | OLS 斜率標準誤 m/s、殘差標準差 m | 用樣本數減參數數作殘差自由度；不是物理校準不確定度 | [verified: code] |
| $C_2,S_2,C_3,S_3$ | 二、三階相位諧波的 cosine／sine 係數，m | Phase 1／1R joint H2/H3 模型；不是物理力係數 | [verified] |
| $w_j^{(u)}$、$\bar a_{\mathrm{orbit}}$ | Phase 1 P1.5 完整圈的梯形相位權重（rad）、加權 mean $a$（m） | 內點 $w_j^{(u)}=(u_{j+1}-u_{j-1})/2$，端點取半個相鄰相位差；$\bar a_{\mathrm{orbit}}=\sum_jw_j^{(u)}a_j/\sum_jw_j^{(u)}$。這是逐圈相位加權平均，不是 Phase 1 以時間做的 3／5 圈 OLS 斜率，也不是 Phase 6 分鐘 mean $a_n$ | [verified: code and saved orbit sample] |
| $C_m^{(\mathrm{orbit})},S_m^{(\mathrm{orbit})},A_m^{(\mathrm{orbit})}$ | Phase 1 完整圈 $m\in\{2,3\}$ 的 Fourier 係數與振幅，m | $C_m^{(\mathrm{orbit})}=2\sum_jw_j^{(u)}(a_j-\bar a_{\mathrm{orbit}})\cos(mu_j)/\sum_jw_j^{(u)}$；$S_m$ 同式改用 $\sin$；$A_m=\sqrt{C_m^2+S_m^2}$。對應 `swarm_a_phase_orbit_mean_v2.h2/h3_*`，不能與 3／5 圈 joint OLS 的 $C_2,S_2,C_3,S_3$ 當成同一次估計 | [verified: code and saved orbit sample] |
| $a_j^{(\mathrm{H})}$ | Phase 1 P1.5.6 扣除所在完整圈 H2/H3 後的 mean semi-major axis，m | $a_j^{(\mathrm H)}=a_j-\sum_{m=2}^{3}[C_m^{(\mathrm{orbit})}\cos(mu_j)+S_m^{(\mathrm{orbit})}\sin(mu_j)]$；係數來自**整個**包含 $j$ 的圈。全部 157,779 筆 trailing 輸出的終點都可配到完整圈；其中 157,478 筆（99.809%）所屬圈在輸出後才結束，未來支持差 10–5,660 s（中位 2,810 s）。首筆差 2,050 s；所以扣諧波後的 1 h 斜率是回溯候選，不能稱為只使用過去資料的即時量 | [verified: code and first saved fit; future support] |
| $\dot a_{\mathrm{day}}$、$\dot a_{\mathrm{local},h}$、$\dot a_{\mathrm{trail},1h}$ | P1.5 的 UTC 日分組、中心 $h\in\{12,24\}$ h 窗、向後 1 h 窗 OLS 斜率，保存單位 m/day | 三者用不同支持集合，內部以 UTC 秒算 m/s，再乘 86,400 輸出 m/day；不能與 3／5 圈每 10 s 錨點的 m/s 斜率直接比較。逐日／中心窗程式有公式，但目前兩份 Phase 1 SQLite 的對應表均 0 列；trailing 表有 157,779 列，使用上列 $a_j^{(\mathrm H)}$，不是原始 mean $a$ | [verified: code and table counts; daily/local output absent] |

## 地磁與密度

| 符號／欄位 | 定義與單位 | 適用範圍與界線 | 狀態 |
| --- | --- | --- | --- |
| $\mathrm{SME}_j$ | 第 $j$ 個有效分鐘的 SuperMAG SME，nT | Phase 3 響應輸入；來源時間與 Phase 2 對齊規則依 lineage | [verified] |
| $X_j$ | $\mathrm{SME}_j-65\,\mathrm{nT}$，nT | 65 nT 是參考值，不是物理常數；負值保留 | [verified] |
| $H_{\tau,j}$、$\alpha_\tau$ | $\tau>0$ 時 $\alpha_\tau=\exp[-60\,\mathrm{s}/(3600\tau\,\mathrm{s})]$、$H_{\tau,0}=X_0$、$H_{\tau,j}=\alpha_\tau H_{\tau,j-1}+(1-\alpha_\tau)X_j$；$\tau=0$ 時 $H_{0,j}=X_j$。$H$ 為 nT，$\alpha$ 無單位 | $\tau$ 的輸入數值以 h 計；原生分鐘只依現在與過去。程式的 `filtered_sme(SME,tau)-65` 與先減 65 再濾波等價，因初值跟隨首筆且濾波權重和為 1。中心相位平均 $\bar H_{\tau,k,i}=\sum_{j\in W_{k,i}}c_{k,j}H_{\tau,j}/\sum_{j\in W_{k,i}}c_{k,j}$，其中 $c_{k,j}\in\{0,1,2\}$ 是原生 L2 配對數、$W_{k,i}$ 是 $u\pm\pi$ 的完整窗口，故平均版本含錨點後資料 | [verified: code, algebra and stored grid] |
| $\tau$ | $H_\tau$ 的濾波時間常數，h 或轉換後 s | Phase 3 歷史 M1 固定 4.65 h；Phase 4 v1 各場 $\tau_k$ 在 0–15 h 的 0.1 h 格點選，v2 在共同粗／細格點選 4.75 h；不得互換。v1 的 `tau_within_1pct_*` 是固定其他參數後的 1% 損失帶，不是物理信賴區間 | [verified: code and saved grid] |
| $\rho_{\mathrm{L2}}$ | DNSAPOD L2 密度，kg/m³ | Phase 3/4 以同樣樣本作相位平均；Phase 6 P6.1 用原生分鐘配對 | [verified] |
| $\rho_{\mathrm{MSIS,q}}$ | 七個 `ap` 值固定為 4 的 quiet NRLMSIS 2.0 密度，kg/m³ | Phase 3/4 的相位平均模型基底；離線 F10.7A 包含未來觀測 | [verified] |
| $\rho_{\mathrm{M0}}$ | 使用 Phase 0 現行 `ap` driver 的 full MSIS 密度，kg/m³ | Phase 6 P6.2 直接讀 Phase 3 保存的相位平均 `rho_msis_full_phase_kg_m3`；Phase 7 讀 Phase 2R 保存的一分鐘配對均值 `rho_msis_kg_m3`，在新事件窗重算 $u\pm\pi$ 配對數加權平均，寫成 `rho_m0_full_phase_kg_m3`。兩者都未經 Phase 4 D-model，且沿用 P0-A 的 `ap` 時序慣例 | [verified: code and five-event source join] |
| $\rho_{\mathrm{M1}}^{\mathrm{pooled}}$、$\rho_{\mathrm{M1}}^{\mathrm{heldout}}$ | 兩者共用 quiet MSIS、$R_{k,\mathrm{RQ}}$、$\bar H_{4.65}$；pooled 用 $G_{\mathrm{P3}}^{\mathrm{pooled}}$，held-out 用 $G_{\mathrm{P3},-k}$，密度單位 kg/m³ | `rho_m1_pooled_phase_kg_m3` 是 Phase 5 Trial10–12 實際讀取的歷史基底，不能替成 held-out M1 或 Phase 4 V2 密度。排除當場只作用於 $G$；兩者都保留由該場 L2 暴前選出的 $R_{k,\mathrm{RQ}}$ | [verified: Phase 3 code and saved formulas] |
| $\rho_{\mathrm{D}}^{\mathrm{V1}}$、$\rho_{\mathrm{D}}^{\mathrm{V2}}$ | v1：$\bar\rho_{\mathrm{MSIS,q},k,i}R_{\mathrm{fit},k}^{\mathrm{V1}}\exp(G_{\mathrm{V1}}\bar H_{\tau_k^{\mathrm{V1}},k,i})$；v2：$\bar\rho_{\mathrm{MSIS,q},k,i}R_{\mathrm{fit},k}^{\mathrm{V2}}\exp(G_{\mathrm{V2}}\bar H_{\tau_{\mathrm{V2}},k,i})$，kg/m³ | 兩版都同場擬合 $R$，但 v1 的 $\tau_k$ 隨事件變、v2 的 $\tau_{\mathrm{V2}}=4.75$ h 共用；$R,G,H$ 必須整組同版。舊 Trial1–5 的 D-model 殘差使用 v1；Phase 5 V2 Ridge 使用 v2 的目標 $R_{\mathrm{fit}}$ 與 $G,H$ | [verified: code and saved predictions] |
| $\rho_{\mathrm{Ridge}}^{\mathrm{LOO}}$、$\rho_{\mathrm{Ridge}}^{\mathrm{full25}}$ | 對 $q\in\{\mathrm{LOO},\mathrm{full25}\}$，$\rho_{\mathrm{Ridge},k,i}^{q}=\bar\rho_{\mathrm{MSIS,q},k,i}\widehat R_k^{q}\exp(G_{\mathrm{V2}}\bar H_{\tau_{\mathrm{V2}},k,i})$，kg/m³ | Phase 5 V2／Phase 6 用每場留出折的 $\widehat R^{\mathrm{LOO}}$；Phase 7 新事件用全 25 場重擬合係數算 $\widehat R^{\mathrm{full25}}$。公式相同，訓練集合不同，數值不可互代 | [verified: code and saved model lineage] |
| $R_{k,\mathrm{RQ}}$ | Phase 3 暴前近零響應段內原生分鐘比值 $\rho_{\mathrm{L2}}/\rho_{\mathrm{MSIS,q}}$ 的中位數，無單位 | 該段需觀測 $ap\le4$、SME $\le100$ nT、41 個 $\lvert H_\tau\rvert \le25$ nT 持續至少 90 min，且有效 L2 配對覆蓋至少 80%；取**比值中位數**。歷史 M1 參數，不同於 Phase 4 擬合 $R_{\mathrm{fit},k}$ | [verified: selected runs and source-paired ratio] |
| $R_{\mathrm{fit},k}^{\mathrm{V1}}$、$R_{\mathrm{fit},k}^{\mathrm{V2}}$ | 第 $k$ 場 Phase 4 各版以同場 L2 擬合的倍率，無單位 | V1／V2 各自儲存，擬合時限制 $0<R<2$；兩版最終值皆未碰上界（V1 0.621163–1.444016，V2 0.626500–1.449175）。Phase 5 V2 只以 V2 值作回溯標籤 | [verified: code and saved events] |
| $G_{\mathrm{P3}}^{\mathrm{pooled}}$、$G_{\mathrm{P3},-k}$、$G_{\mathrm{V1}}$、$G_{\mathrm{V2}}$ | 各模型對自己版本 $H$ 的 log-density gain，nT⁻¹ | P3 pooled 由全部 25 場估計；$G_{\mathrm{P3},-k}$ 排除事件 $k$ 重估，但仍使用該場 $R_{k,\mathrm{RQ}}$。V1／V2 另行估計共同 $G$；每個 $G$ 必須配本版 $H$ | [verified: code] |
| $y_{k,i}$ | 同一相位窗口的 L2 與 quiet MSIS **各自平均後**所得密度比之自然對數，無單位 | Phase 3／4 共用的資料量；不同於 P2.6 對逐分鐘 `log_ratio_obs` 做相位平滑的結果 | [verified] |
| $N_k$、$N_{\mathrm{minute},k}$ | 同一量：第 $k$ 場有效相位分鐘數，計數 | Phase 4 報告使用 $N_k$，共用表也寫 $N_{\mathrm{minute},k}$ 以和 Phase 6／7 的 $N_{\mathrm{orbit},k}$ 區分；事件等權分數先在每場以此數作分母 | [verified: code and stored score] |
| $\bar H_k$、$\bar y_k$ | 第 $k$ 場有效相位分鐘的響應與對數密度比之算術平均，分別為 nT、無單位 | 固定時間常數後，它們用來估該版共同 $G$ 與逐場 $R_{\mathrm{fit},k}$；$\bar H_k$、$G$、$R_{\mathrm{fit},k}$ 必須全屬 V1 或全屬 V2。各場平均都以本場 $N_k$ 分母計算 | [verified: independent closed form] |
| $z_{k,i}$ | $y_{k,i}-\ln R_{k,\mathrm{RQ}}$，無單位 | Phase 3 固定歷史倍率後的對數異常；Phase 4 v2 重新擬合倍率，不沿用此固定 $z$ | [verified] |
| $\widehat\rho_{k,i}$ | D-model 預測的相位平均密度，kg/m³ | Phase 4 v1 用各場 $\tau_k$；v2 用共同 $\tau$，參數均為資料內擬合 | [verified] |
| $L_{\mathrm{event}}$ | $\sqrt{N_{\mathrm{event}}^{-1}\sum_k N_{\mathrm{minute},k}^{-1}\sum_i[\ln(\rho_{\mathrm{L2},k,i}/\widehat\rho_{k,i})]^2}$，無單位 | Phase 4 v1/v2 事件等權 log RMSE；本批 $N_{\mathrm{event}}=25$，$N_{\mathrm{minute},k}$ 為每場有效分鐘數 | [verified] |
| $L_{\mathrm{V1}}$、$L_{\mathrm{V2}}$ | 各版以自身 $R_{\mathrm{fit},k}$、$G$、$H$ 計算的事件等權對數 MSE，無單位 | V1 使用 $R_{\mathrm{fit},k}^{\mathrm{V1}},G_{\mathrm{V1}},\bar H_{\tau_k^{\mathrm{V1}}}$；V2 使用 $R_{\mathrm{fit},k}^{\mathrm{V2}},G_{\mathrm{V2}},\bar H_{\tau_{\mathrm{V2}}}$。兩版各自的 RMSE 是 $\sqrt{L}$，不能把同名局部參數交叉代入 | [verified: stored scores] |
| $N_{\mathrm{event}}$ | 事件數，計數 | Phase 4 損失先以 $N_k=N_{\mathrm{minute},k}$ 逐場平均，再以 $N_{\mathrm{event}}=25$ 對事件等權平均 | [verified] |

## Phase 2／2R 事件與 peak QC

| 符號／欄位 | 定義與單位 | 適用範圍與界線 | 狀態 |
| --- | --- | --- | --- |
| $t_0$／`t0_time_us` | 合併事件內最深的 raw SYM-H 局部最低點；同深度取較早 UTC 分鐘，us | Phase 2／2R；不是物理 onset | [verified] |
| $t_{\mathrm{rel}}$／`t_rel_h` | 分鐘標籤相對 $t_0$ 的時間，h | P2.6／P2R.6 的 peak 候選閉區間為 $[-12,24]$ h | [verified] |
| `symh_min_nt` | 事件內最深 raw SYM-H，nT | 強事件候選低於 $-100$ nT；$t_0$ 對應該分鐘 | [verified: code] |
| $T_{\mathrm{SYM}}$、$D_{\mathrm{near}}$、$D_{\mathrm{before}}$、$D_{\mathrm{after}}$ | Phase 2／2R 事件偵測門檻 $-100$ nT、相鄰最低點近距門檻 72 h、每個最低點前窗 48 h／後窗 96 h | 僅連續等值 run、兩側相鄰分鐘都存在且 run 值**嚴格小於**兩側，並且小於 $T_{\mathrm{SYM}}$，才留下局部最低點；等值 plateau 取首分鐘。相鄰最低點時間差**小於**72 h 才先成一組；不同組的 $[t-48\,\mathrm h,t+96\,\mathrm h)$ 窗口若**嚴格重疊**再合併，恰好相接不合併 | [verified: code and all saved events] |
| $F_{\mathrm{before}}$、$F_{\mathrm{after}}$、$N_{\mathrm{before}}$、$N_{\mathrm{after}}$ | P2.3 Phase 1 候選來源搜尋半寬 60／110 h；正式相位資料窗前 31／後 62 圈 | `phase_source_rows()` 用含兩端的 $[t_0-60\,\mathrm h,t_0+110\,\mathrm h]$ 讀候選列，`phase_window()` 在連續相位上求 $u(t_0)-31(2\pi)$ 與 $u(t_0)+62(2\pi)$ 的精確 UTC 邊界，再以 `first_minute_at_or_after()` 得分鐘起訖。正式分鐘列採 $[\mathrm{minute\_start},\mathrm{minute\_end})$，不等於 P2.2 的合併事件窗。由兩份 Phase 1／1R mean-element 來源全事件重算，P2 25 場、P2R 46 場的相位 UTC 邊界與分鐘起訖逐值相同 | [verified: code, source hash and all event boundaries] |
| `window_start_time_us`、`window_end_time_us` | 合併事件所有最低點中最早的 $t-48$ h、最晚的 $t+96$ h，UTC us | 此 P2.2 合併窗口供事件分組與保存；P2.3 不用這兩欄作 Phase 1 讀取邊界，而是以 $t_0-60$ 至 $t_0+110$ h 的 SQL `BETWEEN` 取候選來源，再求前 31／後 62 圈相位窗。不能把 P2.2 合併窗口誤寫為只以代表 $t_0$ 向前／後取 48／96 h。P2.6 peak 候選 $t_0-12$ 至 $t_0+24$ h 是另一窗口 | [verified: code and stored event fields] |
| `merge_reason`、`storm_id` | 每個局部最低點的合併來源標記及事件 ID | 代表點標 `representative`；與代表點同一 72 h 近距組的其他點標 `within_72h`；因事件窗重疊而加入另一組的組代表點標 `overlap_window`。`storm_id` 以全事件最深 raw SYM-H 的 UTC 分鐘產生，同深度選較早者 | [verified: code and stored minima] |
| `candidate_minute_count`、`sme_smooth_minute_count`、`density_smooth_minute_count` | peak 時窗全部分鐘數、SME 可用平滑分鐘數、密度比可用平滑分鐘數，皆為計數 | 三個分母不同；不能用總候選數當任一平滑序列的有效數 | [verified: code] |
| `sme_peak_time_us`、`density_peak_time_us` | 各自平滑序列在候選窗內最大值的 UTC 時刻，us | 程式排序鍵為 `(平滑值,-source_time_us)`，相同最大值選較早分鐘；可來自不同 pulse。P2／P2R 保存的 25／46 場均無同值最高峰，tie 規則經 `insert_event()` 三筆合成列檢查；保存資料無實際 tie 個案 | [verified: synthetic tie and stored peaks] |
| `sme_peak_nt`、`density_peak_log_ratio` | 上述兩個最大值，nT、無單位 | 峰值來自不同量；不可直接作數值差 | [verified: code] |
| `sme_precedes_density` | $1[t_{\mathrm{SME,peak}}<t_{\mathrm{density,peak}}]$，0／1 | 同時刻為 0；不是因果判定 | [verified: code] |
| `u_rel_rad` | 相對事件的連續軌道相位，rad | 密度平滑以每個錨點 $u\pm\pi$ 的完整窗口求平均；不能替代 UTC 時間 | [verified] |
| `phase_left_time_us`、`phase_right_time_us`、`phase_status` | P2.3／P2R.3 每分鐘相位內插的左／右 Phase 1 mean-element 錨點 UTC（us）及 `exact`／`interpolated` 狀態 | 相位 $u(t)$ 在 10 s 兩錨點間線性內插；`u_rad=u(t)\bmod2\pi`、`u_rel_rad=u(t)-u(t_0)`。若分鐘恰在來源 epoch，左右錨點相同且狀態為 `exact`；不可跨 10 s 來源缺口 | [verified: all 618,608 saved minute rows] |
| `storm_minute_feature_v5.mean_semi_major_axis_m` | P2.3／P2R.3 分鐘列攜帶的 Phase 1 mean $a$，m | 程式取**左錨點**的 `mean_semi_major_axis_m`，即使相位 $u(t)$ 已線性內插，也不對 $a$ 內插；與 Phase 6 分鐘 mean $a_n$ 的來源和取樣法須分開。P2／P2R 共 618,608 分鐘從來源逐列重算，全同 | [verified: code and all saved minute rows] |
| $q_{\mathrm{obs}}$／`log_ratio_obs` | $\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{MSIS}})$，無單位 | P2.6／P2R.6 對此對數比作 centered one-orbit mean；與 Phase 3「兩個相位平均密度之比」不同 | [verified] |
| $P_{k,m}$、`paired_sample_count` | 事件 $k$、分鐘 $m$ 中同時有有效 L2 與可算 MSIS 的原生約 30 s 樣本集合；$p_{k,m}=\lvert P_{k,m}\rvert $，保存資料中為 0、1、2 | P2.4／P2R.4 的 `rho_l2_kg_m3` 與 `rho_msis_kg_m3` 各只在此**同一集合**上平均；$q_{\mathrm{obs},k,m}=\ln[(\sum_{s\in P}\rho_{\mathrm{L2},s}/p)/(\sum_{s\in P}\rho_{\mathrm{MSIS},s}/p)]$，$p=0$ 則三欄空。`rho_l2_orbitmean_kg_m3` 另按原生 orbitmean 平均，不進 $q$；凍結 P2／2R 該診斷欄有 564／1,283 分鐘誤收 CDF 填充值，見[稽核 P2-N](docs/formula_audit.md) | [verified: all native L2/MSIS pairs; orbitmean issue] |
| `expected_30s_sample_count`、`l2_coverage`、`paired_coverage` | 事件分鐘數 $M_k$ 的預期原生筆數 $2M_k$；分別為有效 L2 總筆數／$2M_k$、有效配對總筆數／$2M_k$ | P2.4／P2R.4 只有兩個 coverage 都 $\ge0.80$ 才標 `used`；與 P2.6 平滑窗有效**分鐘**比例及 Phase 3 相位窗配對比例是三種不同分母 | [verified: code and saved event rows] |
| `sme_smooth_nt` | SME 在閉區間 $[t-7.5,t+7.5]$ min 內有效分鐘的算術平均，nT | 完整 1 min 格時窗口含 15 筆，至少 12 筆非空且有限才達 80%；含錨點後觀測。窗口必須整段落在該事件來源列的起訖內 | [verified: code, boundary check and independent full saved smoothing] |
| `log_ratio_smooth` | $q_{\mathrm{obs}}$ 在閉區間 $[u-\pi,u+\pi]$ 內有效分鐘的算術平均，無單位 | 完整窗口且有效分鐘數／窗口分鐘列數 $\ge0.80$；相位窗口列數可變，並非固定 15 筆，也不是 Phase 3 以 30 s L2 配對數加權的 $\bar H_\tau$ | [verified: code, endpoint check and independent full saved smoothing] |
| `sme_to_density_lag_h` | density 平滑峰時間減 SME 平滑峰時間，h | 正值只代表本次 global peak 選法下 SME 較早；可能跨 pulse | [verified] |

## Phase 5 殘差與 Phase 5 V2 Ridge

Trial1–9 的 $e^{\mathrm{D}}_{k,n}=\ln(\rho_{\mathrm{L2},k,n}/\rho_{\mathrm{D},k,n})$ 以 Phase 4 D-model 為分母；Trial10–12 的 $e_{k,n}$ 以 Phase 3 M1 為分母。兩者不能共用殘差欄位意義。$k$ 為事件、$n$ 為事件內分鐘或圈錨點；須連同 Trial 的取樣尺度閱讀。

| 符號／欄位 | 定義與單位 | 適用範圍與界線 | 狀態 |
| --- | --- | --- | --- |
| $e^{\mathrm{D}}_{k,n}$、$\hat e^{\mathrm{D}}_{k,n}$ | D-model 對數殘差及其估計，無單位；$\rho_{\mathrm{candidate}}=\rho_{\mathrm D}\exp(\hat e^{\mathrm D})$ | Trial1–9；D-model 參數已用同場 L2 擬合 | [verified: report/code] |
| `H_tau_k`、`H_24h`、`SME`、`SYM-H`、`altitude` | Trial1–2 五項 GPR 輸入；前兩者與 SME 同為 nT，高度為 m | Trial3 移除高度；$H_{\tau_k}$ 來自 Phase 4 同場擬合，$H_{24h}$ 為固定 24 h 響應 | [verified: report/code] |
| `relative_time_hours`、`tau_hours` | $(t-t_{0,k})/(1\,\mathrm h)$、Phase 4 擬合 $\tau_k/(1\,\mathrm h)$，皆為數值上的 h | Trial4；後者已使用測試事件完整 L2 擬合 | [verified: code] |
| `season_sin`、`season_cos` | $\sin(2\pi f_y)$、$\cos(2\pi f_y)$，無單位；$f_y$ 為 UTC 年初至當刻占當年總秒數比例 | Trial4；閏年以實際年長正規化 | [verified: code] |
| `dSYM-H/dt`、`ap_step`、`F10.7` | 前後相鄰來源時間的 SYM-H 向後差商，nT/s；當步 $ap$、前一 UTC 日 F10.7（sfu） | Trial5；差商首筆無定義，不能當成無單位差值 | [verified: code/report] |
| $e_L,e_R,\hat e(t)$ | 六小時缺口兩側已觀測殘差與其間線性內插，無單位 | Trial6；前後端皆須有 L2，$\hat e(t)=e_L+(e_R-e_L)(t-t_L)/(t_R-t_L)$ | [verified: code/report] |
| `support_start_us`、`support_end_us` | Trial6 一個約一圈錨點所用原生資料的 UTC 支持起訖，us | 測試缺口為 `[start_hour,start_hour+6 h)`；訓練錨點的支持區間須完全在所有測試錨點支持範圍之外。`np.interp` 只用保留下來的兩側訓練殘差，因此 $e_L,e_R$ 是缺口支持區外最近可見的兩點，不是測試錨點的 L2 | [verified: implementation] |
| $\hat e^{\mathrm{past}}_t$ | $60^{-1}\sum_{j=1}^{60}e^{\mathrm D}_{t-j}$，無單位 | Trial7 逐分鐘；須前 60 分鐘連續且有效，當分鐘 L2 只供事後評分 | [verified: code] |
| $\delta e_{k,n}$、$\hat e_{k,n}$ | $e^{\mathrm D}_{k,n}-e^{\mathrm D}_{k,n-1}$、$e^{\mathrm D}_{k,n-1}+\widehat{\delta e}_{k,n}$，無單位 | Trial8–9 預測下一圈；直接沿用基線為 $\hat e=e_{n-1}$，兩圈須相鄰 | [verified: code] |
| `log_trial4_current`、`log_trial4_previous`、`log_l2_previous`、`previous_log_residual` | $\ln\rho_{\mathrm D,n}$、$\ln\rho_{\mathrm D,n-1}$、$\ln\rho_{\mathrm{L2},n-1}$、$e^{\mathrm D}_{n-1}$；對數以固定 kg/m³ 數值計 | Trial8 四輸入、Trial9 跨場 GPR；測試場上一圈 L2 是必要輸入 | [verified: code] |
| $r_{k,n}^{(q)}$、$N$ | Trial13 模型 $q$ 的 $\ln(\rho_{\mathrm{L2},k,n}/\hat\rho_{k,n}^{(q)})$，及共同有效圈數 | 同圈 RMSE $\sqrt{\sum r^2/N}$；合計 2,235 圈是 pooled，不是五折 RMSE 平均；殘差方向以 `calc_gpr_comparison.py` 實作為準 | [verified: code; report sign corrected] |

| 符號／欄位 | 定義與單位 | 適用範圍與界線 | 狀態 |
| --- | --- | --- | --- |
| $m_{k,n}$ | 第 $k$ 場第 $n$ 圈 $\ln(\rho_{\mathrm{M1},k,n})$，以固定 kg/m³ 數值作對數輸入 | Phase 5 Trial10–12 的特徵；單獨對帶單位密度取 log 是記法簡寫，實際比較與差值為無單位 | [verified: notation] |
| $e_{k,n}$ | $\ln(\rho_{\mathrm{L2},k,n}/\rho_{\mathrm{M1},k,n})$，無單位 | Phase 5 Trial10–12 的訓練答案；留出場的 L2 只供事後評分 | [verified] |
| `centered_log_slope` | $(m_{k,n+1}-m_{k,n-1})/2$，無單位／圈 | Phase 5 Trial11；按圈索引的中心差，未除實際時間 | [verified] |
| `centered_log_curvature` | $m_{n+1}-2m_n+m_{n-1}$，無單位／圈² | Phase 5 Trial10；連續三圈，按圈索引的二階差 | [verified] |
| `cumulative_excess` | 相鄰連續圈的正對數密度超額以梯形法乘上時間差／1 day 後累積，無單位 | Phase 5 Trial12；一天是時間正規化基準，並非輸出單位 | [verified] |
| $\widetilde m_k$、$m_k^{\max}$、$t_k^{\max}$ | Trial12 該場有效中心圈 log M1 中位數、最大值、首次達最大值的 UTC 時刻 | `log_below_peak` 為 $m_{k,n}-m_k^{\max}$；`days_from_peak` 為 $(t_{k,n}-t_k^{\max})/(1\,\mathrm{day})$。中位數與峰值都先看完整事件的 M1 曲線，早期圈會用到後期 M1；這是回溯特徵 | [verified: code and stored features] |
| $q_{k,n}$ | $\max(m_{k,n}-\widetilde m_k,0)$，無單位 | Trial12 只將高於該場中位數的 log M1 累入 `cumulative_excess` | [verified: stored features] |
| $r_{k,n}^{\mathrm{T10:12}}$、`total_rmse`、`shape_rmse`、`change_rmse` | $r=e-\widehat e$（Trial10）或 $r=e-\widehat s$（Trial11／12）；total $=\sqrt{\operatorname{mean}(r^2)}$；shape $=\sqrt{\operatorname{mean}[(r-\bar r_k)^2]}$；change $=\sqrt{\operatorname{mean}[(r_{k,n}-r_{k,n-1})^2]}$，皆無單位 | Trial11／12 的 change 只取同事件且 `grid_index` 相差 1 的相鄰圈；總表以全 2,235 圈及所有合格相鄰對 pooled 計算，並非 25 場 RMSE 算術平均。Trial10 只保存 total log RMSE。這裡 $r=e-\widehat e=\ln(\rho_{\mathrm{L2}}/\widehat\rho)$，與 Trial13 實作的殘差方向相同；皆不是 Phase 6／7 半長軸誤差 m | [verified: code and saved fold/event/summary metrics] |
| $\widehat e^{\mathrm{T10}}_{k,n}$ 與 $\widehat s^{\mathrm{T11/T12}}_{k,n}$ | Trial10 GPR 直接預測 $e_{k,n}=\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{M1}})$；Trial11／12 預測各場去均值的形狀殘差，皆無單位 | Trial10 不扣訓練或測試事件平均，其 25 場保存預測均值範圍 $[-0.058506,0.167503]$；Trial11／12 測試預測各場重新去均值。三者都以 $\rho_{\mathrm{M1}}\exp(\text{預測殘差})$ 還原密度，但不能把 Trial10 的 $\widehat e$ 稱為 $\widehat s$ | [verified: code and 2,235 saved rows per Trial] |
| $s_{k,n}$、$\widehat s_{k,n}$ | 訓練標籤 $s_{k,n}=e_{k,n}-\bar e_k$；測試預測 $\widehat s_{k,n}=g(x_{k,n})-\overline{g(x)}_k$，皆無單位 | Trial11／12 訓練場的 $\bar e_k$ 需 L2；測試場只扣 GPR 預測值自己的事件平均，不讀該場 L2。$\rho_{\mathrm{GP},k,n}=\rho_{\mathrm{M1},k,n}\exp(\widehat s_{k,n})$；故無法修正整場共同偏移。保存的 25 場／2,235 筆各場預測平均近零，密度式逐列吻合 | [verified: code and saved predictions] |
| $\Delta R_k^{\mathrm{V2}}$ | $R_{\mathrm{fit},k}^{\mathrm{V2}}-R_{k,\mathrm{RQ}}$，無單位 | Phase 5 V2 Ridge 的訓練標籤；前項用同場 L2 回溯擬合，後項由暴前 quiet run 校準 | [verified: report/code] |
| `r_phase3`（Phase 7） | 外測事件最近暴前 quiet run 的原生 L2／quiet MSIS 有效配對比值中位數，無單位 | 沿用 Phase 3 $R_{k,\mathrm{RQ}}$ 的選段與計算方法，但對 2021–2023 新事件重新計算；不是從凍結 Phase 3 的 25 場 $R$ 表查出。此值進入全 25 場 Ridge 參數的三因素式，選「最近暴前」run 仍依事後事件 $t_0$ | [verified: Phase 7 code, source hash and six native prequiet ratios] |
| `r_post_diagnostic`、`r_post_pre_relative_gap` | Phase 7 暴後 quiet run 的 $R_{k,\mathrm{post}}=\operatorname{median}(\rho_{\mathrm{L2}}/\rho_{\mathrm{MSIS,q}})$；相對差 $R_{k,\mathrm{post}}/R_{k,\mathrm{pre}}-1$，皆無單位 | 暴後量只作回溯診斷，不進 Ridge 三因素預測式；$R_{k,\mathrm{pre}}$ 是同場 `r_phase3`。六場原生暴後配對 1,568 個有效分鐘，保存值逐場全同 | [verified: source-paired post ratios] |
| `quiet_pre_density_coverage`、`quiet_post_density_coverage`、`valid_phase_minutes` | 前兩者為 quiet run 中有效配對分鐘數／該 run 全部分鐘數，無單位；後者為同場有效相位分鐘列數 | quiet run 覆蓋門檻 $\ge0.8$；相位列另需模型所需量完整，不能把兩種分母當成同一 coverage。六場暴前／暴後覆蓋均由原生檔重算吻合 | [verified: source-paired coverage and saved counts] |
| `r_fit_external`、$R_{k,\mathrm{fit,external}}$ | Phase 7 同場回溯參考倍率：$\exp\{\min[\operatorname{mean}_i(y_{k,i}-G_{\mathrm{V2}}H_{\mathrm{V2},k,i}),\ln(\operatorname{nextafter}(2,0))]\}$，無單位 | 直接讀該外測事件的 L2 與 quiet MSIS；`external` 指事件在原 25 場之外，不表示此倍率能事前預測。只作同場擬合參考，不能代替 $\widehat R_k^{\mathrm{full25}}$ 或 Phase 4 的 $R_{\mathrm{fit},k}$ | [verified: code and six saved event rows] |
| $\widehat R_k^{\mathrm{LOO}}$、$\widehat R_k^{\mathrm{full25}}$ | 對 $q\in\{\mathrm{LOO},\mathrm{full25}\}$，$\widehat R_k^q=R_{k,\mathrm{RQ}}+\widehat{\Delta R}_k^q$，無單位；上標指定 Ridge 參數訓練集合 | 前者用每場留出折的 20 場參數，供 Phase 5 V2 圖與 Phase 6；後者用全部 25 場參數，供 Phase 7 新事件外測。Phase 7 的 $R_{k,\mathrm{RQ}}$ 依同一方法在新事件重算，不從 Phase 3 25 場查表 | [verified: code and saved parameters] |
| $x_j,\mu_j,s_j,b_j$ | Ridge 第 $j$ 個因素原值、訓練平均、訓練尺度、標準化線性係數；$x_j,\mu_j,s_j$ 同單位，$b_j$ 與 $\Delta R$ 無單位 | 入選因素依序為 `r_phase3`（無單位）、`prequiet_sme_mean_nt`（nT）、`quiet_f107a_last81_sfu`（sfu）。`StandardScaler` 在每折 20 場訓練集計 $\mu_j$ 與母體標準差 $s_j=\sqrt{\sum_{k\in\mathrm{train}}(x_{k,j}-\mu_j)^2/20}$；零變異時實際除數為 1。$\widehat{\Delta R}=b_0+\sum_j b_j(x_j-\mu_j)/s_j$；全 25 場重擬合的 $\mu,s,b$ 是另一組參數，不得代入留場曲線 | [verified: code, formula and saved folds] |
| `RIDGE_ALPHA`、$b_0$ | Ridge 固定正則化強度 1.0；$\Delta R$ 預測式的截距，皆無單位 | 每折最小化 $\sum_{k\in\mathrm{train}}(\Delta R_k-b_0-\sum_j b_j z_{k,j})^2+\mathrm{RIDGE\_ALPHA}\sum_jb_j^2$，其中 $z_{k,j}=(x_{k,j}-\mu_j)/s_j$；截距不受懲罰。`RIDGE_ALPHA` 不進入 $H_\tau$，$b_0$ 不等於 Phase 1 OLS 截距 | [verified: code and saved folds] |
| `fold_index`、`train_count`、`score_count` | Ridge 分組留場折號、訓練事件數 20、算分事件數 5 | 每場恰好落在一次算分折；同一五折亦用於 137 組候選因素的選擇 | [verified: stored folds] |
| `five_fold_mean_rmse_r` | 五個留出折各自 $R$ RMSE 的算術平均，無單位 | 候選因素的排序目標；不是 25 場誤差平方 pooled 後開根號，也不是獨立外測 | [verified: stored scores] |
| `prequiet_sme_mean_nt` | 校準段開始前完整 1,440 個分鐘的 SME 平均，nT | Phase 5 V2 固定三因素之一；來源值 25 場全同。校準段依第一個 SYM-H 最低點回溯選取，特徵不可當成事前預報量 | [verified: source values] |
| `quiet_f107a_last81_sfu` | 校準段開始前最近的末 81 日 F10.7A，sfu | Phase 5 V2 固定三因素之一；25 場保存值全與 Phase 1 `space_weather` 相同，來源時間落後 0–174 min，符合最多 3 h 規則；校準段本身仍依事後事件選取 | [verified: source values and timing] |

## 密度到半長軸下降

| 符號／欄位 | 定義與單位 | 適用範圍與界線 | 狀態 |
| --- | --- | --- | --- |
| $a_{\mathrm{mean}}$ 與 $\mu_{\mathrm{P1/P6}}$ 的跨模型配對 | P6.1 的 `mean_semi_major_axis_m` 由 Phase 1 Orekit B-L provider（$\mu_{\mathrm{BL}}$）推得；積分核再用 $\rho\sqrt{\mu_{\mathrm{P1/P6}}a_{\mathrm{mean}}}$ | Phase 7 同樣從 Phase 1R mean elements 作分鐘 $a$ 平均後代入固定 $\mu_{\mathrm{P1/P6}}$。這是已保存 pipeline 的兩個模型設定，不能說兩處 $\mu$ 完全相同，也不能將 mean $a$ 直接視為 P1.3 的 osculating $a$ | [verified: Phase 1/6/7 code lineage] |
| $K_n$ | 從 block 起點累積的 $\rho\sqrt{\mu_{\mathrm{P1/P6}}a}$ 梯形積分，kg/m | Phase 6；只在連續 60 s 樣本與同一 block 內累積 | [verified: dimensional] |
| $\mathcal E_{\mathrm{circ}}$、$v_{\mathrm{circ}}$、$\beta$ | 近圓軌道比能 $-\mu_{\mathrm{P1/P6}}/(2a)$（m²/s²）、速度 $\sqrt{\mu_{\mathrm{P1/P6}}/a}$（m/s）、理想化 $C_DA/m$（m²/kg） | 若阻力加速度大小為 $\beta\rho v^2/2$ 且 $v_{\mathrm{rel}}\simeq v_{\mathrm{circ}}$，由 $d\mathcal E/da=\mu_{\mathrm{P1/P6}}/(2a^2)$ 得 $da/dt=-\beta\rho\sqrt{\mu_{\mathrm{P1/P6}} a}$。這只推導 Phase 6 使用的簡化形式；保存 $B_{\mathrm{eff}}$ 是資料內有效比例，不等於已量得的 $\beta$ | [verified: algebra and model assumption] |
| $B_{\mathrm{eff}}$ | 以 L2/POD 全三年資料內擬合的有效比例，$-\sum_n K_n\Delta a_{\mathrm{POD},n}/\sum_n K_n^2$，m²/kg | 通過原點、以 1,575,671 個可積分**累積分鐘點**等權求平方誤差，37 blocks 各自重設 $K=0$；不是對每段獨立 $B$ 取平均，也不是對增量斜率做回歸。Phase 6 固定 0.0092292068 m²/kg，Phase 7 沿用；P6.1 擬合資料從 2023-07-01 開始，Phase 7 五場計分最晚到 2023-03-28，時間無重疊；仍不是獨立測得的 $C_D A/m$ | [verified: code and stored fit] |
| $\Delta a_{\mathrm{POD},n}$ | $a_n-a_{\mathrm{block,start}}$，m | Phase 6 P6.1 每個連續 block 歸零 | [verified] |
| $\Delta a_{\mathrm{model},n}$ | $-B_{\mathrm{eff}}K_n$，m | Phase 6/7 的回溯 density-to-decay closure，不是 XYZ propagator | [verified] |
| `chunk_id`、`block_id` | POD 連續段識別、密度積分連續段識別 | Phase 6/7 缺分鐘或 chunk 改變就切 block；不得跨 block 相減 | [verified: code] |
| $\Delta a_{\mathrm{POD,event}}$ | $\sum_b(a_{b,\mathrm{end}}-a_{b,\mathrm{start}})$，m | Phase 6 每場事件只計已覆蓋 blocks；不把缺口當作已知下降 | [verified: report/code] |
| `observed_covered_delta_a_m`、`predicted_*_covered_delta_a_m` | 事件內各已覆蓋 block 終點的 POD／模型下降量總和，m | `*` 是 M0 或 Ridge；不跨缺口做首尾差 | [verified: stored event formula] |
| `absolute_percentage_error` | $100\lvert e_{\mathrm{event}}/\Delta a_{\mathrm{POD,event}}\rvert $，% | Phase 6 事件 endpoint 診斷；與逐圈 MAE 的 m 單位、分母都不同 | [verified: stored event formula] |
| $\bar a_j$、$\Delta a_{\mathrm{POD},j}$ | 第 $j$ 個完整 POD 圈平均半長軸 m、相鄰圈差 $\bar a_j-\bar a_{j-1}$ m | Phase 6/7 逐圈計分；與 Phase 6 分鐘 $a_n-a_{\mathrm{block,start}}$ 不同 | [verified: formula] |
| $e_{\mathrm{model},k,j}$ | $\Delta a_{\mathrm{model},k,j}-\Delta a_{\mathrm{POD},k,j}$，m | 正值表示預測下降較少；模型須註明 M0 或 Ridge | [verified: stored score] |
| $N_{\mathrm{orbit},k}$ | 事件 $k$ 的有效相鄰圈間區間數，計數 | $\operatorname{MAE}_{\mathrm{model},k}=N_{\mathrm{orbit},k}^{-1}\sum_j\lvert e_{\mathrm{model},k,j}\rvert $；Phase 6/7 逐場與 pooled 指標分母不同 | [verified: formula] |
| $N_{\mathrm{P7}}$、$\operatorname{MAE}_{\mathrm{P7,pooled}}$、$\operatorname{RMSE}_{\mathrm{P7,pooled}}$、$\operatorname{MAE}_{\mathrm{P7,macro}}$ | $N_{\mathrm{P7}}=\sum_{k=1}^{5}N_{\mathrm{orbit},k}=453$；pooled MAE $=\sum_{k,j}\lvert e_{k,j}\rvert /453$、pooled RMSE $=\sqrt{\sum_{k,j}e_{k,j}^2/453}$；macro MAE $=\sum_{k=1}^{5}\operatorname{MAE}_k/5$，皆為 m | Phase 7 報告「全部」列是 453 圈 pooled；五場圈數為 89、91、91、91、91，所以兩種平均接近但不相同。M0 pooled／macro MAE 為 5.309314802270／5.309300214216 m，Ridge 為 5.304511217345／5.304391807891 m；Phase 6 的 25 場 macro 主分數不可直接同名比較 | [verified: saved five-event SQLite] |
| `nearest_minute` | $m(t)=\lfloor(t+30\,\mathrm s)/60\,\mathrm s\rfloor\,60\,\mathrm s$；POD 圈 endpoint 對齊到最近 UTC 分鐘的錨點，恰在半分鐘時選較晚分鐘 | Phase 6／7 只在兩端同 block 且鍵存在時計分；無時間插值。保存的 2,262／453 個有效圈間區間，兩端共 4,524／906 個錨點，最大絕對對齊差皆 28 s，無恰半分鐘樣本；模型分鐘跨度與 POD 兩終點 UTC 跨度最多差 50 s，不能寫成完全相同的時間段 | [verified: code and all saved scored endpoints] |

## Phase 5 Trial1–5 主要 SQLite 實際欄位對照

五個 Trial 的主要預測結果分布在六份 SQLite（Trial5 的特徵與預測分庫），合計 14 張非 metadata 表、151 個實際欄位、39 種不同欄名。五份預測表各有 25 場／2,295 個圈錨點。Trial1 是同場資料內 GPR 擬合；Trial2–5 的 `fold_index`／`outer_fold_index` 才表示留場測試。所有 Trial 都以 Phase 4 v1 同場 D-model 作殘差基線，整條密度流程不能稱為無同場 L2 的外測。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `storm_id`、`time_us`、`algorithm_version`、`u_rel_rad` | 事件 ID、相位圈錨點 UTC key（us）、方法版本、相對相位（rad） | `time_us` 是相位圈代表分鐘，不是原生 DNSAPOD 30 s 樣本；有些輸出表未重存 `u_rel_rad`，以來源錨點為準 | [verified: schema/code] |
| `h_tau_phase_nt`、`h_24h_phase_nt`、`sme_phase_nt`、`symh_phase_nt`、`altitude_phase_m` | 同圈的 Phase 4 v1 擬合 $H_{\tau_k}$、固定 24 h 響應、SME、SYM-H（nT）及高度（m） | Trial1／2 五項 GPR 輸入；Trial3 選模可刪高度。$H_{\tau_k}$ 使用該場完整 L2 擬合的 $\tau_k$，不是事前固定量 | [verified: feature code/schema] |
| `symh_rate_nt_s`、`ap_step`、`f107_sfu` | SYM-H 相鄰來源時刻的向後差商（nT/s）、當步 ap 指數、前一 UTC 日 F10.7（sfu） | Trial5 新 driver；`symh_rate_nt_s` 不可當 nT 差值，`f107_sfu` 需按特徵來源 key 讀 | [verified: driver code/schema] |
| `relative_time_hours`、`tau_hours`、`season_sin`、`season_cos` | 相對事件最低點的時間（h）、該場 v1 擬合 $\tau_k$（h）、UTC 年內相位的 sine／cosine（無單位） | Trial4 時間與季節特徵；同名 `tau_hours` 在 Trial1 預測亦是 Phase 4 v1 同場參數，不是 GPR 核長度尺度 | [verified: feature code/schema] |
| `rho_l2_phase_kg_m3`、`rho_trial4_phase_kg_m3`、`residual_log_density` | 圈相位支持 L2／Phase 4 v1 密度（kg/m³）及 $e^{\mathrm D}=\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{V1}})$（無單位） | Trial3–5 預測表不重存 L2 密度，但保留殘差與 v1 密度；L2 可依同圈來源 key 查回。這個殘差與 Trial10–12 的 M1 殘差分母不同 | [verified: 5×2,295 saved rows] |
| `gp_log_residual_mean`、`gp_log_residual_std`、`rho_gpr_median_kg_m3` | GPR 預測 v1 log 殘差的平均與標準差（無單位）、$\rho_{\mathrm{V1}}\exp(\hat e^{\mathrm D})$（kg/m³） | `median` 對 lognormal 還原密度而言是中位數，不是期望密度；五份預測表全列還原式吻合 | [verified: code/saved rows] |
| `rho_95_lower_kg_m3`、`rho_95_upper_kg_m3` | $\rho_{\mathrm{V1}}\exp(\hat e^{\mathrm D}\mp1.96\sigma_{\mathrm{GP}})$ 的兩個密度界，kg/m³ | 95% coverage 以 log 殘差差值是否落入 $\pm1.96\sigma$ 計；不是實際密度加減同一 kg/m³ 常數 | [verified: code/saved rows] |
| `r_fit`、`gain_per_nt`、`phase_paired_coverage` | Phase 4 v1 同場 $R_{\mathrm{fit},k}$（無單位）、$G_{\mathrm{V1}}$（nT⁻¹）與圈相位支持的原生配對覆蓋率（0–1） | 前兩者屬 D-model 上游，不是 GPR 重新估的參數；`phase_paired_coverage` 在 Trial1 錨點表保存 | [verified: schema/upstream code] |
| `fold_index`、`outer_fold_index`、`role` | 留出折號與 `train`／`test` 角色；`outer_fold_index` 用於 Trial3–5 nested selection | Trial2 直接 20／5 分組；Trial3–5 的候選只在外折訓練場內選，後於外折測試場評分 | [verified: split code/schema] |
| `candidate_name`、`selected_candidate_name`、`feature_names`、`kernel_name`、`selected` | 內折候選名、外折選中候選、特徵清單、GPR 核名及是否選中（0／1） | `selected_candidate_name` 每個外折固定；不是每個圈再選模型 | [verified: nested selection schema/code] |
| `inner_validation_anchor_count`、`inner_validation_storm_count`、`inner_rmse_log_density`、`inner_mae_log_density` | 四個內折驗證集合併後的圈數／場數及 log 密度 RMSE／MAE（無單位） | 若 $V_f$ 為外折 $f$ 的全部內驗證錨點，$S_{f,c}=\sqrt{\sum_{i\in V_f}(e_i-\hat e_{i,c})^2/\lvert V_f\rvert}$，外折選 $c_f^*=\arg\min_c S_{f,c}$。$\lvert V_f\rvert$ 等於外折訓練錨點數 1,835–1,838；不可把內驗證分數當外折留場分數 | [verified: Trial3/4/5 all inner fits and selections] |

### Trial2 高度尺度上下界控制庫

`phase5_altitude_bound_v1.sqlite` 和 `phase5_altitude_lower_bound_v1.sqlite` 各有 `{prediction,fold_fit,summary}` 三表；前者測高度 ARD 下限 0.01、0.1、0.3，後者測 0.001、0.0001。五組各對相同 2,295 個留場錨點計分。這些是 Trial2 診斷，不是新的採用模型。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `altitude_min_length_scale`、`fitted_altitude_length_scale` | 高度 RBF-ARD 長度尺度的設定下限與各折擬合值，皆為**標準化後無單位** | 標準化只由該折訓練場擬合；不能把 0.001 等數值當 0.001 m。保存 25 個折擬合值均不小於設定下限 | [verified: code/stored fold fits] |
| `storm_id`、`time_us`、`fold_index`、`algorithm_version` | 留場事件、圈錨點 UTC key（us）、留出折號、控制實驗版本 | 五組共 11,475 筆 `prediction`；同組每事件每錨點只一筆，與 Trial2 主庫折號與 key 全同 | [verified: saved prediction keys] |
| `actual_log_residual`、`predicted_log_residual` | Phase 4 v1 的 $\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{V1}})$ 與 GPR 估計值，皆無單位 | 實際值逐鍵與 Trial2 主庫 `residual_log_density` 相同；`predicted_log_residual` 是該下限／折的留場輸出 | [verified: saved keys] |
| `test_log_rmse`、`gpr_log_rmse`、`phase4_log_rmse`、`test_anchor_count`、`convergence_warning_count` | 折內 $\sqrt{\operatorname{mean}[(e-\hat e)^2]}$、五折合併同式、$\sqrt{\operatorname{mean}(e^2)}$、測試圈數與收斂警告數 | fold 與 summary 分母不同；五組逐點重算各折與總列最大差 $1.11\times10^{-16}$，不能平均五個折 RMSE 取代 pooled | [verified: saved predictions/metrics] |

### Trial1 retained 舊 LOSO 庫

`data/retained/swarm_a_phase4_gpr_loso_v1.sqlite` 另存舊版 2,295 個錨點，與目前 Trial1 主庫的 `(storm_id,time_us)` 集合全同，但 `rho_phys_phase_kg_m3` 不是 `rho_trial4_phase_kg_m3` 的別名。原產生程式已從 Git 歷史 commit `88f24e8` 的 `phases/phase4/code/{load_phase4_inputs,prep_gpr_loso,calc_phase4_gpr}.py` 找回；現行工作區沒有這些舊檔。retained 是舊 Phase 4 四特徵 LOSO，不能把它的分數併入 Trial1 五特徵資料內結果。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `storm_id`、`time_us`、`u_rel_rad`、`algorithm_version` | 事件 ID、圈錨點 UTC key（us）、相對相位（rad）、舊庫版本 | 與目前 Trial1 主庫的 2,295 個事件／時刻鍵完全對齊，僅表示取樣位置相同 | [verified: saved keys] |
| `rho_l2_phase_kg_m3`、`rho_phys_phase_kg_m3` | 同錨點觀測 L2 與 retained 舊版 $\bar\rho_{\mathrm{MSIS,q},k}R_{k,\mathrm{RQ}}\exp(G_{-k}H_{\tau_{-k},k})$，kg/m³ | $R_{k,\mathrm{RQ}}$ 來自該場 Phase 3 暴前 L2 校準；$G_{-k}$、$\tau_{-k}$ 由其他 24 場在 0–10 h、0.05 h 格點搜尋。從原始 SME 與 Phase 3 quiet 分鐘重算全部 2,295 列，最大相對差 $4.21\times10^{-16}$；故不同於固定 $\tau=4.65$ h 的 Phase 3 M1 | [verified: historical code and full source rebuild] |
| `gp_log_residual_mean`、`gp_log_residual_std`、`rho_gpr_median_kg_m3`、`rho_95_lower_kg_m3`、`rho_95_upper_kg_m3` | GPR log 修正均值／標準差（無單位）、$\rho_{\mathrm{phys}}e^{\hat e}$ 與 $\rho_{\mathrm{phys}}e^{\hat e\mp1.96\sigma}$（kg/m³） | retained 庫 2,295 列的中位數與兩界還原式全同；不能因此推知 `rho_phys` 的上游物理公式 | [verified: saved output formula; upstream open] |

### Trial1–5 歷史摘要 CSV 欄位

21 份既存摘要／診斷 CSV 共 59 種欄名。這些 CSV 是唯讀研究證據；主要逐點輸出已存在上列 SQLite。`storm_id=all_anchors` 是總列標籤，非實際事件。`fold_index=all_held_out`／`outer_fold_index=all_held_out` 也是總列標籤，不能作整數折號。下列同名數值必須連同 CSV 名稱和 event／fold／summary 層級判讀。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `anchor_count`、`train_anchor_count`、`test_anchor_count`、`train_storm_count`、`test_storm_count` | 事件／折使用的相位圈錨點數與磁暴數，皆為計數 | Trial1 的 `anchor_count`、Trial2–5 的 `test_anchor_count` 都指評分圈數；內折 `inner_validation_anchor_count`／`inner_validation_storm_count` 另在上表定義 | [verified: headers/code] |
| `trial4_rmse_log_density`、`trial4_mae_log_density`、`gpr_rmse_log_density`、`gpr_mae_log_density` | $e=\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{V1}})$、$e-\hat e$ 的 RMSE／MAE，皆無單位 | event、fold、all_anchors 各依其圈集合計分；五份主要 SQLite 逐點重算 25 場與總列最大差 $2.08\times10^{-16}$ | [verified: score code/saved rows] |
| `gpr_coverage_95` | $N^{-1}\sum_i\mathbf1\{\lvert e_i-\hat e_i\rvert\le1.96\sigma_i\}$，0–1 比例 | 是保存 GP 區間對當批 L2 的經驗覆蓋率，非可直接宣稱 95% 校準；總列由逐圈重新計數，非逐場比例算術平均 | [verified: score code/saved rows] |
| `length_scale_h_tau_phase_nt`、`length_scale_h_24h_phase_nt`、`length_scale_sme_phase_nt`、`length_scale_symh_phase_nt`、`length_scale_altitude_phase_m` | GPR RBF 核沿五種特徵軸的擬合長度尺度，**標準化後無單位** | 欄名後綴 `_nt`／`_m` 指原始特徵欄位，不是保存尺度的物理單位；每折以訓練資料 `StandardScaler` 換算，不能和 $\tau_k$ 或高度 m 直接比較 | [verified: fit_gpr code/hyperparams schema] |
| `signal_variance`、`noise_variance`、`log_marginal_likelihood`、`convergence_warning_count`、`selection_warning_count` | GPR 核訊號／白噪聲方差、訓練 log 邊際概似、收斂警告數與選模警告數 | 前三項是所屬折的統計模型參數／目標值，不是大氣密度或物理噪聲量測；兩個 warning count 作用域不同 | [verified: kernel/selection code] |
| `analysis_kind`、`feature_set_name`、`target_feature_name`、`selected_feature_names`、`feature_name` | Trial2 消融類型、候選特徵集合、被保留／移除的目標欄、實際特徵清單與單一特徵名 | `analysis_kind` 分全五項、只留一項、移除一項；Trial5 的 `feature_name` 另指 driver 稽核欄 | [verified: ablation/feature-audit code] |
| `all_feature_rmse_log_density`、`single_feature_rmse_log_density`、`drop_feature_rmse_log_density`、`single_feature_delta_vs_trial4`、`drop_feature_delta_vs_all_features` | 全五項、單一特徵、去除一項的 log RMSE；後兩者分別為單項 RMSE 減 v1 基線、去除一項 RMSE 減全五項 RMSE，皆無單位 | 差值保留正負號；正值表示該比較的 RMSE 較大，不等於因果特徵貢獻 | [verified: contribution_deltas code] |
| `train_mean`、`train_std`、`test_mean`、`test_std`、`test_mean_shift_sd`、`test_outside_train_range_fraction` | 某原始特徵在訓練／測試集合的均值與標準差、$(\bar x_{\mathrm{test}}-\bar x_{\mathrm{train}})/s_{\mathrm{train}}$、超過訓練 min–max 的測試圈比例 | 前四者沿各 `feature_name` 的 nT／m 單位；後兩者無單位。每折只用訓練場求標準化基準 | [verified: diagnostic code] |
| `median_nearest_standard_distance`、`p95_nearest_standard_distance`、`median_nearest_ard_distance`、`p95_nearest_ard_distance`、`median_nearest_non_altitude_ard_distance`、`p95_nearest_non_altitude_ard_distance`、`median_nearest_altitude_distance_m` | 測試錨點到訓練錨點最近鄰距離的中位數／95 百分位；前三組分別用標準化五維、再除 RBF ARD 尺度、或排除高度軸後再除 ARD 尺度；最後一欄為純高度差中位數（m） | 標準化／ARD 距離無單位，純高度距離才是 m；不同空間及維度不可直接作物理距離差 | [verified: geometry code] |
| `median_abs_gpr_correction` | 測試錨點 $\lvert\hat e^{\mathrm D}\rvert$ 的中位數，無單位 | 診斷 GPR 修正量，不是密度絕對誤差；事件與折各自取中位數 | [verified: geometry code] |
| `minimum`、`maximum`、`unique_value_count` | Trial5 driver 特徵在保存錨點的最小值、最大值、不同數值數量 | min／max 的單位由同列 `feature_name` 決定：SYM-H 差商 nT/s、ap 無單位、F10.7 sfu；不能混成同一物理單位 | [verified: feature-audit headers/code] |

## Phase 5 Trial6 SQLite 實際欄位對照

`swarm_a_trial6_day_fraction.sqlite` 的 `trial6_anchor_feature` 有 25 場／2,295 個錨點。這是歷史 Trial6 特徵庫；同階段既存 CSV 是凍結證據，不作新管線輸入。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `storm_id`、`time_us`、`algorithm_version` | 事件 ID、圈錨點 UTC epoch（us）、衍生方法版本 | `time_us` 沿用 Trial4 `phase4_trial4_gpr_prediction` 的錨點 key；不得當原生 30 s 樣本時刻 | [verified: source/schema] |
| `elapsed_hours` | $(t-t_{k,\mathrm{first\ anchor}})/(1\,\mathrm h)$，數值單位 h | 相對該事件第一個**錨點**，不是 Phase 2 的 SYM-H 最低點 $t_{0,k}$；全列直接重算差 0 | [verified: code/2,295 rows] |
| `day_count`、`paired_count`、`day_fraction` | 相位支持窗口內日照側原生配對樣本數、全部原生配對樣本數及其比值，計數／計數／無單位 | `day_fraction=day_count/paired_count`；日照側定義為 UTC 與地理經緯度對應的太陽高度角 $>0^\circ$，無大氣折射（pressure 0）；只有 L2 有值且 MSIS driver 可用的原生樣本進分母。全列 $0\le\mathrm{day\_count}\le\mathrm{paired\_count}$ | [verified: code/stored ratio] |
| `support_start_us`、`support_end_us` | 相位窗口實際涵蓋的首末來源分鐘 UTC key，us | 每列支持區間含錨點 `time_us`；Trial6 隱藏六小時區塊時按整個測試支持區間排除重疊訓練錨點，不能只按錨點時間篩選 | [verified: phase support/2,295 bounds] |
| `rho_l2_phase_kg_m3`、`rho_trial4_phase_kg_m3`、`residual_log_density` | 同圈相位支持的 L2 與 Phase 4 v1 D-model 密度（kg/m³），及 $\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{V1}})$（無單位） | Trial6 內插的是帶號 log 殘差，不是直接內插密度；2,295 列保存對數比全同 | [verified: source/code/stored ratio] |

## Phase 5 Trial7–9 歷史輸出欄位對照

Trial7–9 的既存 CSV／gzip CSV 只作歷史證據；新計算不得以它們作中繼輸入。以下符號以檔案及列層級為作用域，`algorithm_version` 是方法標籤。`storm_id` 通常是磁暴 ID，但 Trial9 `trial9_pooled_fold_metrics.csv` 的同名欄位實存 `fold_1` 至 `fold_5`，表示折標籤，不是可聯接的事件 ID。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `time_us`、`previous_time_us`、`u_rel_rad` | 當圈／前一完整相位圈錨點 UTC key（us）、當圈相對相位（rad） | Trial8／9 相鄰圈須相位序號差 1；Trial7 逐分鐘檔的 `time_us` 則是分鐘鍵，不能跨檔視為同一尺度 | [verified: code/headers] |
| `rho_l2_minute_kg_m3`、`rho_trial4_pointwise_kg_m3`、`rho_l2_phase_kg_m3`、`rho_trial4_phase_kg_m3` | 逐分鐘 L2／Phase 4 v1 點密度，及整圈相位支持的 L2／v1 密度，kg/m³ | `pointwise` 與 `phase` 的平均支持不同；所有 Trial7–9 殘差須和同尺度密度配對 | [verified: file headers/code] |
| `residual_log_density`、`past_mean_log_residual`、`moving_mean_log_residual` | 同尺度 $\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{V1}})$、前 60 個連續有效分鐘殘差均值、舊展示用 centered 61 分鐘均值；皆無單位 | `past_mean` 不讀當分鐘 L2；`moving_mean` 讀未來分鐘，僅屬舊單場展示，不是正式 25 場測試 | [verified: Trial7 code/audit] |
| `rho_past_mean_kg_m3`、`rho_trial7_phase_kg_m3`、`rho_trial7_minute_kg_m3` | $\rho_{\mathrm{V1}}\exp(\text{對應預測殘差})$，kg/m³ | 前者是正式逐分鐘 past mean；後兩者是舊 centered 展示的圈／分鐘輸出 | [verified: Trial7 code/headers] |
| `previous_trial4_density_kg_m3`、`previous_l2_density_kg_m3`、`previous_log_residual` | 前一圈 v1 D-model／L2 密度（kg/m³），及 $\ln(\rho_{\mathrm{L2,prev}}/\rho_{\mathrm{V1,prev}})$ | Trial8 四輸入與 Trial9 跨場推論仍需測試場已完成前圈的 L2；不是完全不看測試場觀測 | [verified: code/point rows] |
| `gp_log_residual_mean`、`gp_log_residual_std`、`one_input_gp_log_residual_mean`、`pooled_gpr_log_residual`、`pooled_gpr_log_std`、`same_storm_gpr_log_residual` | GPR 對當圈 log 殘差的平均／標準差、單輸入對照平均、跨場 GPR 平均／標準差與同場 Trial8 平均；皆無單位 | GPR 內部訓練 target 是殘差增量 $\delta e$，保存的平均已加回前圈 $e$；`std` 是模型輸出標準差，不是保存 RMSE | [verified: Trial8/9 code] |
| `rho_previous_kg_m3`、`rho_gpr_kg_m3`、`rho_pooled_gpr_kg_m3` | 當圈 v1 密度分別乘 $\exp(e_{n-1})$、$\exp(\hat e_n^{\mathrm{same}})$、$\exp(\hat e_n^{\mathrm{pooled}})$，kg/m³ | Trial8 兩份逐點檔各 2,115 列、Trial9 逐點檔 2,265 列，保存還原式全列差 0 | [verified: point files] |
| `training_pair_count`、`training_storm_count`、`fold_index`、`fitted_kernel` | 訓練連續圈對數、訓練事件數、留出折號、擬合後 GPR kernel 字串 | Trial8 隨事件時間增加可用對數；Trial9 每折用另外 20 場，`fitted_kernel` 是模型診斷字串而非物理參數 | [verified: code/headers] |
| `minute_count`、`valid_l2_count`、`scored_count`、`scored_orbits`、`matched_orbit_count`、`t0_48h_scored_count` | 事件分鐘、有效 L2 分鐘、可計分分鐘／圈，以及事件最低點前後各 24 h 內可計分數，皆為計數 | Trial7 分鐘／圈 summary 及 Trial8／9 圈 summary 分母不同；Trial9 matched 只算同鍵有 Trial8 對照的圈 | [verified: code/summary headers] |
| `trial4_log_rmse`、`trial4_log_mae`、`corrected_log_rmse`、`past_mean_log_rmse`、`past_mean_log_mae`、`previous_orbit_log_rmse`、`previous_orbit_log_mae`、`gpr_log_rmse`、`gpr_log_mae`、`one_input_gpr_log_rmse`、`one_input_gpr_log_mae`、`same_storm_gpr_log_rmse`、`pooled_gpr_log_rmse` | 各自對 L2 的 log 密度殘差 RMSE／MAE，無單位 | `previous_orbit` 是前圈殘差沿用基線；同名指標在不同檔的分母依分鐘／圈／共同配對圈及事件／折／總層級而異 | [verified: metric code/headers] |
| `t0_48h_trial4_log_rmse`、`t0_48h_corrected_log_rmse`、`t0_48h_past_mean_log_rmse` | $t_0\pm24\,\mathrm h$ 子集的 v1、舊修正與正式 past mean log RMSE，無單位 | Trial7 的部分 summary 保存此前綴欄；Trial9 的 $t_0\pm24$ h 結果另存 `trial9_t0_48h_event_metrics.csv`，其中指標沿用原欄名，不能捏造此前綴欄 | [verified: summary headers] |

## Phase 5 Trial10–13 SQLite 實際欄位對照

四份試驗庫的 16 張非 metadata 表共 158 欄；欄名依下列 table 作用域與上文公式閱讀。`prediction` 的 `time_us` 是圈錨點 UTC key（us），`grid_index` 是事件內相位圈序號，`storm_id` 是事件識別碼；`fold_index` 是五折中留出該場的折號。`algorithm_version` 是產生該列的版本字串。Trial13 只保存聚合分數及來源路徑，不保存逐圈預測。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `log_m1`、`past_log_change`、`centered_log_curvature` | $m_n=\ln(\rho_{\mathrm{M1},n}/(1\,\mathrm{kg/m^3}))$、$m_n-m_{n-1}$、$m_{n+1}-2m_n+m_{n-1}$；皆為無單位數值 | Trial10 三項 GPR 特徵；`centered_log_curvature` 使用下一圈 M1 | [verified: feature code/schema] |
| `days_from_t0`、`relative_log_m1`、`centered_log_slope` | $(t_n-t_{0,k})/(1\,\mathrm{day})$、$m_n-\operatorname{median}_k(m)$、$(m_{n+1}-m_{n-1})/2$ | Trial11 四項特徵中的三項；事件中位數與中心斜率讀完整 M1 曲線，非當圈即時量 | [verified: feature code/schema] |
| `log_below_peak`、`days_from_peak`、`cumulative_excess` | $m_n-m_k^{\max}$、$(t_n-t_k^{\max})/(1\,\mathrm{day})$、正超額的時間正規化累積；皆無單位 | Trial12 使用整場 M1 峰與中位數；同名 `log_m1` 仍是 Phase 3 pooled M1 | [verified: feature code/schema] |
| `rho_m1_kg_m3`、`rho_l2_kg_m3`、`rho_gpr_kg_m3`、`rho_gp_kg_m3` | 圈錨點歷史 M1、觀測 L2 與 GPR 還原密度，kg/m³ | Trial10 輸出叫 `rho_gpr_kg_m3`，Trial11／12 叫 `rho_gp_kg_m3`；後兩者用事件去均值形狀殘差 | [verified: prediction schema/code] |
| `actual_log_residual`、`gpr_log_residual`、`predicted_shape_residual` | 前者 $\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{M1}})$；Trial10 的 GPR 輸出預測此殘差，Trial11／12 輸出去均值形狀；皆無單位 | `rho_gpr`／`rho_gp` 各為 $\rho_{\mathrm{M1}}\exp(\text{預測殘差})$，但預測量是否去均值須按 Trial 區分 | [verified: prediction code/schema] |
| `train_count`、`test_count`、`warning_count`、`train_target_scale` | 每折訓練／測試圈數、GPR 收斂警告數、Trial10 訓練殘差的標準差 | `train_target_scale` 先縮放訓練 target，輸出時乘回；警告數不是預測不確定度 | [verified: fold code/schema] |
| `length_scale_log_m1`、`length_scale_past_change`、`length_scale_curvature`、`length_scale_relative_m1`、`length_scale_slope`、`length_scale_below_peak`、`length_scale_time`、`length_scale_cumulative` | 各折擬合 RBF 核在對應標準化特徵軸的長度尺度，無單位 | 同欄名跨 Trial 的訓練集合及其他特徵不同；不得當物理時間常數 $\tau$。`length_scale_time` 對應 Trial11 的 `days_from_t0`、Trial12 的 `days_from_peak` | [verified: GPR kernel/scaler code] |
| `m1_log_rmse`、`gpr_log_rmse`、`m1_total_rmse`、`gp_total_rmse`、`m1_shape_rmse`、`gp_shape_rmse`、`m1_change_rmse`、`gp_change_rmse` | M1／GPR 對 L2 的 total、逐場去均值 shape、連續圈差 change 對數 RMSE；無單位 | Trial10 只有 total；Trial11／12 含三種。fold、event、summary 各有自己的樣本集合與分母 | [verified: metric code/schema] |
| `improved_storm_count`、`improved_shape_storms`、`improved_shape_folds` | 優於 M1 的場數或折數，計數 | Trial10 依 total RMSE，Trial11／12／13 的 shape 欄依 shape RMSE；不可混成一個勝場統計 | [verified: summary code/schema] |
| `model_name`、`sqlite_path`、`storm_count`、`orbit_count`、`total_sse`、`shape_sse`、`change_sse`、`change_count` | Trial13 來源模型／來源 SQLite、事件與圈數、各種平方誤差和與有效連續圈對數 | total／shape 分母是 `orbit_count`，change 分母是 `change_count`；event、fold、summary 聚合層級不同 | [verified: comparison code/schema] |
| `total_rmse`、`shape_rmse`、`change_rmse`、`shape_delta_ci_low`、`shape_delta_ci_high` | Trial13 由對應 SSE／分母開方的對數 RMSE；末兩欄是事件重抽樣下 GPR 減 M1 的 shape RMSE 95% 區間端點 | CI 以事件為抽樣單位、固定亂數種子與 10,000 次重抽；不是單圈獨立 bootstrap | [verified: comparison code/schema] |

## Phase 0／1／1R SQLite 實際欄位對照

Phase 0 原始表目前存在 Phase 1／1R 工作庫；Phase 1R 的 14 張主要非 metadata 表與 Phase 1 三年分支的歷史候選表共用部分欄名。欄位定義以 table 與版本為準。

以下共用欄位以所在 table 為作用域：`time_us` 是該列的 UTC epoch key（us），不是來源資料涵蓋區間；`chunk_id` 是連續可用 POD 段的識別碼；`algorithm_version` 是衍生方法標籤。`sample_count` 計擬合樣本，`orbit_count` 計完整圈，兩者不可互換。`window_start_time_us` 和 `window_stop_time_us` 是歷史候選視窗的 UTC 邊界；v2 左界另有 `orbit_3_window_start_time_us`／`orbit_5_window_start_time_us`。匯入錯誤表另有 `{source_file_name,error_message}`，只記錯誤，不是物理資料。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `x_m`、`y_m`、`z_m`、`vx_m_s`、`vy_m_s`、`vz_m_s` | `swarm_a_states` 的同一 ITRF state 三維位置（m）與速度（m/s）分量 | 合併即 `{time,frame,position_m,velocity_m_s}`；`weather_time_us` 是所在 3 h 天氣格 key，不是 POD 觀測時刻 | [verified: raw loader/schema] |
| `source_id`、`epoch_count`、`signature` | SP3 來源檔流水 ID、provenance 的 epoch 數、`source_files` 的 `size:mtime_ns` 字串 | `signature` 是檔案大小與最後寫入時間，不是 SHA-256；不可拿它代替原生 ZIP 雜湊驗證 | [verified: identifier code/schema] |
| `file_name`、`sp3_frame_label`、`coverage_start_time_us`、`coverage_end_time_us`、`cadence_s`、`time_system` | SP3 檔名、宣告的座標框架、來源涵蓋 UTC 起訖（us）、取樣間隔（s）、來源時間系統 | 這些是 `swarm_a_pod_source_provenance` 的來源描述；`coverage_*` 不是逐列 `time_us`，且檔案標籤不等於獨立 frame 驗證 | [verified: provenance schema] |
| `f107_sfu`、`f107a_last81_sfu`、`ap_daily`、`ap_3h`、`ap_6h`、`ap_9h`、`ap_12_to_33h_avg`、`ap_36_to_57h_avg` | `space_weather` 的 F10.7（日值）、末 81 日均值（sfu）、日均與歷史 3 h ap 格或區間均值（無單位指數） | `f107a_last81_sfu` 是 trailing，`space_weather.f107a_sfu` 是 centered；同名 `f107_sfu` 在 P1.6 特徵取前一 UTC 日，其時間來源看 `f107_source_time_us` | [verified: weather schema/alignment code] |
| `density_kg_m3`、`local_solar_time_h` | 舊 `swarm_a_density` 表的模型密度（kg/m³）與地方太陽時（h） | Phase 1 三年／Phase 1R 工作庫此表均無保存列，不能當 Phase 2 M0 或 Phase 3 quiet 密度來源 | [verified: schema and row counts] |
| `altitude_m`、`latitude_deg`、`longitude_deg`、`source_file_name` | 舊密度匯入表的高度（m）、緯／經度（deg）與來源檔名 | `swarm_a_density` 為空表；deg 是舊表欄位單位，不可假裝是內部 SI rad；`source_file_name` 在匯入錯誤表另指失敗檔案 | [verified: empty legacy schema] |
| `sym_h_nt`、`sym_h_version` | Phase 1／1R `geomagnetic` 的 SYM-H 數值（nT）與 Kyoto 版本號 | P2／P2R 的 `symh_nt` 是另建的一分鐘來源表；雖表示同類指數，須依 UTC key、來源檔及版本核對，不可只按近似欄名合併 | [verified: schema/alignment code] |
| `ae_nt`、`ae_version` | Phase 1／1R `geomagnetic` 的 AE 指數（nT）與 Kyoto 版本號 | 與 SYM-H 同屬 geomagnetic 來源，AE 未進此分支 rolling 斜率公式 | [verified: geomagnetic schema] |
| `ap_source_time_us`、`f107_source_time_us`、`f107a_source_time_us`、`f107_data_type` | Phase 1 P1.6 特徵的 3 h ap 格、前一 UTC 日 F10.7／末 81 日 F10.7A 來源 key（us）與 F10.7 類型字串 | `ap_now` 取當前 CelesTrak 3 h 格；F10.7 與同名 `f107a_sfu` 特徵取前一日，後者實為 trailing last81 而非 `space_weather.f107a_sfu` 的 centered 值 | [verified: feature alignment code] |
| `sym_h_left_time_us`、`sym_h_right_time_us`、`quality_flags` | P1.6 SYM-H 對齊來源兩端 UTC key（us）、缺值旗標字串 | exact 時左右相同；旗標為 `ok`、`missing_sym_h`、`missing_space_weather` 或兩缺值組合，不是物理品質量 | [verified: feature alignment code] |
| `mean_eccentricity`、`mean_inclination_rad`、`mean_argument_of_perigee_rad`、`mean_raan_rad`、`mean_anomaly_rad` | Orekit Brouwer-Lyddane mean 偏心率（無單位）及傾角、近地點幅角、升交點赤經、平近點角（rad） | $u=\operatorname{unwrap}(\omega+M)$ 只取末兩個角；mean 元素不是 osculating state 直接換單位 | [verified: mean-orbit code/schema] |
| `semi_major_axis_m`、`mean_semi_major_axis_m` | osculating 與 B-L mean 半長軸，m | 即使共用 `time_us`，兩個軌道定義不同；Phase 6／7 的平均軌道與 POD 圈均值須註明來源 | [verified: schema/mean-orbit code] |
| `mean_longitude_rad`、`mean_eccentric_longitude_rad`、`mean_true_longitude_rad` | mean orbit 的平、偏近點、真經度，rad | 與 $\omega+M$ 所用近地點幅角和平近點角相關，但經度還包含升交點赤經；不可把這三欄直接當 $u$ | [verified: Orekit getter/schema] |
| `mean_eccentric_anomaly_rad`、`mean_true_anomaly_rad`、`mean_keplerian_period_s`、`mean_keplerian_mean_motion_rad_s` | mean orbit 偏近點角／真近點角（rad）、Kepler 週期（s）與平均角速率（rad/s） | $n=2\pi/T=\sqrt{\mu_{\mathrm{BL}}/a_{\mathrm{mean}}^3}$；與另算的瞬時 osculating $a$ 使用的 $\mu_{\mathrm{P1/P6}}$ 不同 | [verified: Orekit getter and constants] |
| `mean_equinoctial_ex`、`mean_equinoctial_ey`、`mean_equinoctial_hx`、`mean_equinoctial_hy` | Orekit mean equinoctial 的偏心率與傾角向量分量，無單位 | 同一 mean orbit 的另一組元素表示；不能直接把 `ex,ey,hx,hy` 當成位置或速度 | [verified: Orekit getter/schema] |
| `mean_x_m`、`mean_y_m`、`mean_z_m`、`mean_vx_m_s`、`mean_vy_m_s`、`mean_vz_m_s` | 由 mean orbit 輸出的 GCRF 位置（m）與速度（m/s）分量 | 和原生 ITRF `swarm_a_states` 分量既不同 frame，也不同 osculating／mean 軌道定義 | [verified: mean-orbit code/schema] |
| `is_usable`、`rejection_reason` | POD 品質旗標（0／1）與元素計算／品質判定的拒絕原因字串 | 同名 `rejection_reason` 出現在 osculating、mean 與品質表，須帶 table 名；空值不代表同一拒絕規則 | [verified: schema/code] |
| `orbit_start_time_us`、`phase_weighted_mean_semi_major_axis_m`、`pod_count`、`phase_coverage_rad`、`max_pod_gap_s` | 完整相位圈起點（UTC us）、相位加權 mean $a$（m）、POD 樣本數、相位覆蓋（rad）、最大 POD 時間缺口（s） | `phase_coverage_rad` 與 10 s POD 取樣品質決定完整圈；不能把完整圈與 3／5 圈 rolling OLS 視窗當同一集合 | [verified: phase-orbit code/schema] |
| `h2_cosine_m`、`h2_sine_m`、`h2_amplitude_m`、`h3_cosine_m`、`h3_sine_m`、`h3_amplitude_m` | 每個完整相位圈的二／三階 Fourier cos、sin 係數及 $\sqrt{C_m^2+S_m^2}$，m | 用該完整圈的相位權重求出；與 rolling joint OLS 的 `orbit_{3,5}_h{2,3}_{cos,sin}_m` 不同 | [verified: phase-orbit formula/schema] |
| `h2_amplitude_median_m`、`h2_amplitude_max_m`、`h3_amplitude_median_m`、`h3_amplitude_max_m` | 完整圈 H2／H3 振幅的中位數與最大值，m | Phase 1 診斷表的聚合，不是單一時刻的 OLS 係數 | [verified: diagnostic schema] |
| `orbit_{3,5}_window_start_time_us`、`orbit_{3,5}_sample_count`、`orbit_{3,5}_phase_span_rad` | rolling 3／5 圈左界 UTC key（us）、含內插左界的擬合樣本數、相位跨度（rad） | `{3,5}` 指兩個實際欄位家族；兩分支有效左界已全列重算，不能把圈數當分鐘數 | [verified: v2 schema/full boundary audit] |
| `orbit_{3,5}_decay_rate_m_s`、`orbit_{3,5}_decay_rate_1sigma_m_s`、`orbit_{3,5}_fit_residual_std_m`、`orbit_{3,5}_reject_reason` | 各 3／5 圈、raw／joint 表的斜率（m/s）、1-sigma（m/s）、殘差標準差（m）、拒絕原因字串 | 同欄名在 raw 與 joint 表分別求解；不能把不同模型係數或 sigma 視為同一數值 | [verified: code/schema; slopes sampled] |
| `orbit_{3,5}_h{2,3}_{cos,sin}_m`、`harmonic_orders` | joint H2／H3 表的四個諧波係數（m）及使用階數字串 `2,3` | 只存在 joint 表；完整圈 Fourier 的係數是另一種估計 | [verified: joint schema/code] |
| `audit_name`、`violation_count`、`scope_start_time_us`、`scope_stop_time_us` | P1.7 稽核規則名稱、違規數、所查 UTC 範圍起訖（us） | 稽核列記資料契約，不是物理觀測；範圍端點須連同實際 SQL 的包含規則閱讀 | [verified: audit schema/code] |
| `available_window_count`、`orbit_window`、`decay_method`、`harmonic_orders` | 舊 v1 候選可用窗口數、圈數、raw／joint 方法及諧波階數標記 | v1 候選仍在 Phase 1 三年工作庫，不能與 v2 的 m/s 全列輸出或 Phase 2 正式使用欄位靜默互換 | [verified: historical schema] |
| `orbit_{3,5}_decay_rate_m_day`、`orbit_{3,5}_decay_rate_1sigma_m_day`、`orbit_{3,5}_fit_residual_std_m` | 舊 v1 3／5 圈候選的斜率與 1-sigma（m/day）、殘差標準差（m） | 舊 v1 共有 16,836 列；v2 改存 m/s，單位換算須乘／除 86,400，不等於新一輪相位估計 | [verified: historical schema/count] |
| `utc_day_start_us`、`daily_decay_rate_m_day`、`daily_decay_rate_1sigma_m_day`、`window_hours`、`local_decay_rate_m_day`、`local_decay_rate_1sigma_m_day`、`window_stop_time_us`、`fit_residual_std_m` | 舊逐日或 12／24 h 局部 OLS 的日界／窗口末端 UTC key（us）、窗口小時數、斜率與 1-sigma（m/day）、殘差標準差（m） | Phase 1 三年庫的 daily/local 兩表均為 0 列，只能記方法欄位，不能報成已保存結果 | [verified: schema and empty tables] |
| `trailing_window_start_time_us`、`decay_rate_m_day`、`decay_rate_1sigma_m_day`、`phase_coverage_rad`、`max_pod_gap_s` | 扣完整圈 H2/H3 後、向後 1 h OLS 的起點 UTC key（us）、斜率與 1-sigma（m/day）、相位覆蓋（rad）、最大 POD 缺口（s） | trailing 表有 157,779 列，但其扣諧波係數多由尚未結束的完整圈求得，不是即時可用斜率；與 v2 rolling raw/joint 斜率不同 | [verified: schema/count and future-support audit] |

## Phase 2／2R／3 SQLite 實際欄位對照

Phase 2／2R checkpoint 與 Phase 3 歷史基線保持唯讀。兩份最終事件庫和三份 Phase 3 主要結果庫的實際欄位以下表及上文公式共同定義。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `audit_sha256`、`audit_json`、`sha256`、`file_name`、`source_kind`、`modification_date`、`downloaded_at_utc` | checkpoint／來源檔的雜湊、稽核 JSON、檔名、來源類型、檔案修改日及下載 UTC 時刻 | provenance 欄位不進密度或事件公式；`source_audit_v2` 與 `geomag_source_files_v2` 的 `sha256` 對象不同 | [verified: schema] |
| `sme_nt`、`symh_nt`、`ae_nt`、`sme_station_count`、`sme_valid` | 同 UTC 分鐘 SME／SYM-H／AE 指數（nT）、SME 有效測站數（計數）、SME 可用旗標（0／1） | `geomag_1min_v2`、P2.3 分鐘特徵同名來源；SYM-H 選事件，SME 進響應及 peak QC，AE 只保留來源資料 | [verified: geomag schema/code] |
| `symh_version`、`ae_version`、`sme_source_file_name`、`symh_source_file_name`、`ae_source_file_name` | Kyoto 指數版本號與三種指數的來源檔名 | `storm_minimum_v2` 的 `symh_version`／來源檔指向選低點所用原始分鐘；版本與來源不等於物理指數值 | [verified: geomag/event schema] |
| `minimum_time_us`、`phase_start_time_us`、`phase_end_time_us`、`minute_start_time_us`、`minute_end_time_us` | 局部 SYM-H 最低點、事件相位窗口兩端、取整分鐘窗口兩端的 UTC key，us | 相位邊界由 $u(t_0)-31(2\pi)$、$u(t_0)+62(2\pi)$ 反插；分鐘端點用 ceiling-to-minute，輸出窗口右端不含 | [verified: P2/P2R code and all saved windows] |
| `raw_3_sigma_m_s`、`raw_5_sigma_m_s`、`joint_3_sigma_m_s`、`joint_5_sigma_m_s` | P2.3 帶入的 Phase 1／1R 四種局部 OLS 斜率 1-sigma，m/s | `raw`／`joint` 與 3／5 圈各自一組；不是磁暴密度誤差 | [verified: schema/source mapping] |
| `raw_3_sample_count`、`raw_5_sample_count`、`joint_3_sample_count`、`joint_5_sample_count` | 對應四個 OLS 視窗的樣本數，計數 | 有內插相位左界時可多一筆虛擬邊界樣本；與 P2 密度配對數無關 | [verified: rolling estimator/schema] |
| `raw_3_reject_reason`、`raw_5_reject_reason`、`joint_3_reject_reason`、`joint_5_reject_reason` | 對應四種 OLS 候選的拒絕原因字串 | 需與斜率／sigma 空值一起讀；不能把缺值當零斜率 | [verified: schema] |
| `l2_valid_sample_count`、`orbitmean_valid_sample_count` | P2.4 分鐘有效原生 L2 數、有效 orbitmean L2 數，皆為計數；事件 coverage 表的同名 `l2_valid_sample_count` 是逐事件總數 | `paired_sample_count` 另要求同筆 MSIS 有效，故可小於 L2 有效數；凍結 `orbitmean_valid_sample_count` 曾把正值 CDF `FILLVAL` 誤算為有效，P2／P2R 分別影響 564／1,283 分鐘，不能直接當物理有效數。orbitmean 欄會經 P2.5 view 暴露，但不進 L2/MSIS 配對對數比或 P2.6 平滑／peak | [issue: frozen orbitmean count; downstream scope audited] |
| `sme_raw_nt`、`log_ratio_raw` | P2.6 平滑前該分鐘 SME（nT）及 $\ln(\rho_{\mathrm{L2,paired}}/\rho_{\mathrm{MSIS,paired}})$（無單位） | `sme_smooth_nt` 為中心 15 分鐘、`log_ratio_smooth` 為中心 $u\pm\pi$；原值與平滑值不得混用 | [verified: peak QC code] |
| `candidate_start_t_rel_h`、`candidate_end_t_rel_h`、`sme_peak_t_rel_h`、`density_peak_t_rel_h` | P2.6 候選窗相對 $t_0$ 的 -12／+24 h、及在此窗選出的 SME／密度峰相對時間，h | peak 同值時選較早分鐘；`sme_to_density_lag_h` 是後兩個峰時刻之差，可能跨 pulse | [verified: peak selection code/schema] |
| `h_phase_tau_00_nt`…`h_phase_tau_40_nt`、`h_raw_tau_00_nt`／`h_raw_tau_16_nt`／`h_raw_tau_40_nt` | Phase 3 41 個中心相位平均響應與三個保留的原生分鐘響應，nT；索引 $j$ 對應 $\tau=j/4$ h | `h_phase_tau_*` 的 `*` 嚴格為兩位數 00–40；`h_raw` 只存 0、4、10 h 三點。兩者不可混為同一權重或同一時間支持 | [verified: response code/schema] |
| `rho_msis_quiet_kg_m3`、`log_l2_over_quiet_phase` | Phase 3 quiet MSIS 原生分鐘密度（kg/m³），及相位 L2／quiet MSIS 的對數比（無單位） | quiet 密度的七個 ap 均固定 4；相位對數比先各自相位平均密度再取比，不是原生比值平均 | [verified: quiet density code/schema] |
| `rho_m1_held_out_phase_kg_m3` | Phase 3 使用排除當場估計的 $G_{\mathrm{P3},-k}$、但保留該場暴前 $R_{k,\mathrm{RQ}}$ 所得 M1 相位密度，kg/m³ | 與 `rho_m1_pooled_phase_kg_m3` 只差 $G$ 訓練事件集合；不能稱完全無同場 L2 的外測預測 | [verified: prediction code/schema] |
| `r_candidate`、`r_pre_distance_days`、`r_candidate_status` | Phase 3 所選暴前 quiet-run $R$（無單位）、該 run 不含終點到第一個強磁暴最低點的距離（day）、校準候選狀態字串 | `r_candidate` 即歷史 $R_{k,\mathrm{RQ}}$ 的保存欄名；不是 Phase 4 同場 $R_{\mathrm{fit}}$ | [verified: overview/calibration code] |
| `gain_excluding_this_storm_per_nt`、`m1_excluding_this_storm_g_rmse_log_density` | Phase 3 排除當場估計的 $G_{-k}$（nT⁻¹）與其 M1 對該場 L2 的 log RMSE（無單位） | 排除只作用於 $G$；同場暴前 $R$ 仍進 M1，因此不是完全獨立外測 | [verified: prediction/overview code] |

## Phase 4／Phase 5 V2 SQLite 實際欄位對照

Phase 4 v1、v2 與 Phase 5 V2 Ridge 的同名欄位須連同模型版本及訓練集合閱讀。下列四個主要保存庫的數值表欄名已與 schema 對照。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| Phase 3／Phase 4 V1／V2 的 `h_phase_nt` | 各庫同名但不同響應：Phase 3 為 $\bar H_{4.65}$，V1 為 $\bar H_{\tau_k^{\mathrm{V1}}}$，V2 為 $\bar H_{\tau_{\mathrm{V2}}}$；皆為 nT | 三庫 25 場、214,907 個 `{storm_id,time_us}` 完全對齊，L2 與 quiet MSIS 相位密度逐值相同；`h_phase_nt` 三組兩兩比較，每組 214,907 筆均不同。不能只憑欄名或時間鍵跨版代入 $G$ | [verified: full read-only join] |
| V1／V2 的 `r_fit`、`tau_hours`、`gain_per_nt` | V1 D-model：$R_{\mathrm{fit},k}^{\mathrm{V1}}$、$\tau_k^{\mathrm{V1}}$、$G_{\mathrm{V1}}$；V2：$R_{\mathrm{fit},k}^{\mathrm{V2}}$、共同 $\tau_{\mathrm{V2}}$、$G_{\mathrm{V2}}$ | V1 `trial4_joint_fit_events` 須先限定 `model='D_free_r_tau'`；25 場的 V1／V2 `r_fit`、`tau_hours` 全部不同，$G_{\mathrm{V1}}=0.0007050541071710351$、$G_{\mathrm{V2}}=0.0006898286353846385$ nT⁻¹。相同欄名不代表相同參數 | [verified: event-table join and model table] |
| `rho_trial4_joint_phase_kg_m3`、`rho_phase4_v2_phase_kg_m3` | Phase 4 v1／v2 的 $\rho_{\mathrm{MSIS,q}}R_{\mathrm{fit}}e^{GH}$，kg/m³ | v1 每場 $\tau_k$，v2 共用 4.75 h；$R,G,H$ 只能同版配對 | [verified: code and saved minutes] |
| `residual_log_density`、`gain_per_nt` | 前者為 $\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{D}})$，無單位；後者為所屬 v1／v2 模型 $G$，nT⁻¹ | `residual_log_density` 在 v1／v2 各分鐘表各自以本版 D-model 為分母；不能只按欄名跨版聯接 | [verified: prediction code/schema] |
| `r_rq`、`r_fit_over_r_rq`、`r_fit_near_upper_bound` | Phase 3 暴前倍率、Phase 4 同場擬合倍率除以暴前倍率（皆無單位）、以及 $R_{\mathrm{fit}}\ge0.99R_{\max}$ 的 0／1 診斷旗標 | v1 最佳化限制 $0<R<2$；`r_rq` 不等於 `r_fit`，比值只作差異診斷 | [verified: v1 fit code/schema] |
| `tau_within_1pct_low_hours`、`tau_within_1pct_high_hours` | 固定該場已擬合 $R$ 與共同 $G$，逐一代入候選 $\tau$ 後，事件 MSE 不超過最小 MSE 1.01 倍的首／末格點，h | 只是條件式損失帶，不是重新擬合 $R,G$ 的信賴區間；固定 $\tau$ 基線兩端同為基線值 | [verified: v1 fit code] |
| `trial4_joint_rmse_log_density`、`m0_uncalibrated_rmse_log_density` | v1 同場 D-model、未校準 M0 各自對 L2 的事件 log RMSE，無單位 | 兩者以相同事件相位分鐘計分；前者已同場擬合，不能稱獨立預報勝出 | [verified: v1 overview code] |
| `mean_residual_ln`、`geometric_l2_over_m1` | Phase 4 歷史殘差篩查中，Phase 3 M1 的事件平均 $\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{M1}})$ 及其指數，均無單位 | 前者是對數平均，後者是幾何比；不是 $\operatorname{mean}(\rho_{\mathrm{L2}}/\rho_{\mathrm{M1}})$ | [verified: residual-screen code] |
| `residual_slope_per_nt`、`residual_h_correlation`、`screening_flags` | Phase 3 M1 殘差對 $H_{4.65}$ 的同場去均值 OLS 斜率（nT⁻¹）、Pearson 相關（無單位）、及閾值旗標字串 | 旗標 `background_offset` 依 $\lvert\bar e\rvert\ge\ln(1.10)$，`response_shape` 依 $\lvert r\rvert\ge0.30$；屬舊 M1 問題診斷，不是 Phase 4 D-model 參數 | [verified: residual-screen code] |
| `converged`、`outer_iterations`、`iteration`、`changed_tau_count` | v1 交替擬合是否收斂、外層迭代總數、迭代序號、當輪換 $\tau_k$ 的事件數 | 這些是數值求解診斷；不是物理時間常數或事件數據列 | [verified: fit code/schema] |
| `event_equal_mse_log_density`、`event_equal_rmse_log_density` | v1 模型每場分鐘 MSE 先平均，再對 25 場等權平均；後者是此前者開根號，皆無單位 | 不等於 214,907 個分鐘直接 pooled 的 RMSE | [verified: fit code and saved model score] |
| `r_k_tau_fixed` | `phase4_v2_tau_fixed_r_v1` 中 $\tau=4.75$ h 的 `phase4_v2_events.r_fit` 精確快照，無單位 | 25 場逐事件複製，不是另一輪重新擬合；與 v1 每場 $\tau_k$ 的 $R$ 不可混用 | [verified: snapshot code/schema] |
| `quiet_start_time_us`、`quiet_end_exclusive_time_us` | Phase 5 V2 `event_input` 所選暴前 quiet 校準段的 UTC 起點與不含終點，us | 校準段用於 `r_phase3`、暴前 SME、末 81 日 F10.7A 特徵；選段依事後事件 $t_0$ | [verified: Ridge input code/schema] |
| `selected_features`、`train_rmse_r`、`five_event_rmse_r` | 每折選中的因素名稱清單；20 訓練事件、5 留出事件各自的 $R$ RMSE，後兩者無單位 | Ridge 訓練標籤為 $\Delta R_k^{\mathrm{V2}}=R_{\mathrm{fit},k}^{\mathrm{V2}}-R_{k,\mathrm{RQ}}$；五折分數是在同一五折上挑因素後所得 | [verified: Ridge fold code/schema] |
| `baseline_train_rmse_r`、`baseline_five_event_rmse_r` | 不加 Ridge 修正時 $\widehat{\Delta R}=0$，訓練／留出事件的 $\sqrt{\operatorname{mean}(\Delta R^2)}$，無單位 | 對應直接用 Phase 3 暴前 $R$ 的基線；與 Ridge 兩個 RMSE 使用同折事件 | [verified: Ridge evaluate code] |
| `r_pred`、`train_mean`、`train_scale` | 留出場 $\widehat R_k^{\mathrm{LOO}}=R_{k,\mathrm{RQ}}+\widehat{\Delta R}_k^{\mathrm{LOO}}$（無單位）；全 25 場最終 Ridge 因素的訓練平均與 `StandardScaler` 尺度（各同因素原單位） | `heldout_prediction.r_pred` 用 20 場折參數；`final_parameter.train_mean/train_scale` 用全 25 場重擬合，兩組參數不能混用 | [verified: Ridge code/schema] |
| `rho_phase4_v1_phase_kg_m3`、`rho_phase4_v2_phase_kg_m3`、`rho_ridge_phase_kg_m3` | Phase 5 V2 對照庫逐分鐘的 v1、v2 同場 D-model 與留場 Ridge 密度，kg/m³ | 三欄在 `(storm_id,time_us)` 精確對齊；圖只畫 L2、v1、Ridge，Ridge 用 v2 的 $G,H$ | [verified: comparison code/figure] |
| `v1_rmse_log_density`、`v2_rmse_log_density` | 對照庫逐事件的 v1、v2 $\sqrt{\operatorname{mean}_i[\ln(\rho_{\mathrm{L2},i}/\rho_{\mathrm{model},i})^2]}$，無單位 | 同表 `ridge_rmse_log_density` 另用留場 Ridge；v1／v2 是同場擬合參考，不是獨立外測 | [verified: comparison score code] |

### Phase 5 V2 探索庫補充欄位

`data/sqlite` 的 24 份既存 SQLite 合計 62 張非 metadata 表、406 個欄位位置；其中多數是舊因素搜尋、GPR 或線性控制試算。相同 `r_pred`／`rmse_r` 在不同檔代表不同特徵集合與選模規則。v16／v17 以同批五場分數選因素，保存分數是搜尋分數；現行下游只用固定的 v20／v21 Ridge 參數版本。以下欄位只補實際存在的作用域，不把試算庫升格為採用版。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `feature`、`feature_set`、`features`、`factor`、`model`、`name`、`value` | 特徵名、候選集合名／逗號分隔清單、單因素名、線性控制模型名、基線摘要名，以及 `event_feature` 的特徵值 | `value` 的單位依同列 `feature` 決定；`features`／`feature_set` 是選模標籤，不是可直接代入的數值向量 | [verified: schema/feature code] |
| `source_algorithm_version`、`rmse_log_density` | Phase 4 v2 $R$ 快照的來源演算法版與該事件同場擬合的 log 密度 RMSE（無單位） | `phase4_v2_r_targets_v1/v2` 的 `r_fit` 是目標標籤，不是新事件可事前知道的輸入 | [verified: target snapshot schema/code] |
| `peak_sme_nt`、`min_symh_nt`、`log_r_fit` | 事件內 SME 最大值、SYM-H 最低值（nT），及 $\ln R_{\mathrm{fit},k}^{\mathrm{V2}}$（無單位） | 初版 `storm_r_gpr_v1` 以前兩個事件全窗極值預測 log $R$；它們不是暴前可用特徵 | [verified: initial GPR code] |
| `r_pred_std_log`、`r_train_mean` | GPR 輸出的 log $R$ 標準差（無單位）、$\exp[\operatorname{mean}_{\mathrm{train}}(\ln R_{\mathrm{fit}})]$（無單位） | `r_train_mean` 是訓練場幾何均值基線，不是 $R$ 算術平均；`r_pred_std_log` 不等於 $R$ 空間的 `delta_r_std` | [verified: GPR code] |
| `distance_days`、`quiet_duration_h`、`quiet_end_us`、`held_out_quiet_end_us` | quiet 段末至事件最低點距離（day）、段長（h）、quiet 段排他末端的 UTC key（us） | 後兩個舊欄名實際複製 `quiet_end_exclusive_time_us`；相同末端的事件視為同一 quiet 組，分折須同組不拆 | [verified: quiet/linear code] |
| `quiet_mean_sme_nt`、`quiet_max_sme_nt`、`quiet_mean_symh_nt`、`quiet_mean_ap` | quiet 段 SME 平均／最大、SYM-H 平均（nT）及 ap 平均（指數） | 都在選定校準段的時間支持內彙總；段選取仍依事件 $t_0$，不是事前固定日曆窗 | [verified: quiet feature code] |
| `quiet_mean_h_nt`、`quiet_std_h_nt`、`quiet_max_abs_h_nt`、`r_h_adjusted` | quiet 段相應 $H$ 的平均／標準差／最大絕對值（nT）；$r_{\mathrm{h-adjusted}}=R_{k,\mathrm{RQ}}\exp(-G_{\mathrm{V2}}\overline H_{\mathrm{quiet}})$ | `r_h_adjusted` 是探索性 $H$ 校正參考，與正式 Ridge 的 $\widehat R$ 不同 | [verified: quiet-response code] |
| `delta_r_pred`、`delta_r_std`、`r_ridge` | 預測 $\widehat{\Delta R}_k=\widehat R_k-R_{k,\mathrm{RQ}}$、其 $R$ 空間標準差（皆無單位），及對照密度庫實際使用的 Ridge $R$ | `delta_r_pred` 與 `r_pred` 的關係依試算模型核對；GPR log 空間輸出不能直接當 $R$ 空間標準差 | [verified: trial/schema] |
| `amplitude_r`、`length_scale`、`noise_std_r` | 探索 GPR 的固定 $\Delta R$ kernel 振幅、標準化特徵 RBF 長度尺度、$R$ 空間白噪聲標準差，皆無單位 | 與 Phase 3/4 時間常數 $\tau$、Ridge `alpha` 不同；v19 以內層 15／5 選六組平滑設定 | [verified: prior/smooth GPR code] |
| `inner_rmse_log_r`、`inner_rmse_log_correction`、`inner_rmse_delta_r`、`inner_rmse_r`、`selection_rmse_r` | 內驗證 log $R$、log 修正、$\Delta R$ 或 $R$ RMSE；`selection_rmse_r` 是 v16 五場選模分數，皆無單位 | 分母和目標尺度不同，不可只因同名 RMSE 比大小；v16 的選模五場也是報告的五場，非獨立外測 | [verified: selection code/report] |
| `train_rmse_r`、`test_rmse_r`、`baseline_test_rmse_r`、`rmse_r`、`mae_r` | 訓練／測試／不修正基線的 $R$ RMSE，或線性模型彙總 RMSE／MAE，皆無單位 | `test_rmse_r` 在 v16 等於所選候選的 `selection_rmse_r`；不同庫的 test 是否先參與選模須按版本判斷 | [verified: fold/summary code] |
| `factor_value`、`intercept`、`slope`、`slope_all`、`coefficient` | 單因素實值、線性修正截距與斜率、全資料斜率、最終 Ridge 標準化因素係數 | $\Delta R=\mathrm{intercept}+\mathrm{slope}\,x$；斜率單位是 $x$ 的倒數，`coefficient` 則以標準化無單位因素為輸入，不能直接互換 | [verified: linear/ridge code] |
| `group_pearson_r`、`permutation_p`、`nine_factor_p`、`positive_fold_slopes`、`positive_group_slopes`、`positive_h_slopes` | 以 quiet 組彙總的 Pearson 相關、10,000 次置換的原始與九因素多重比較 p 值、斜率為正的折／quiet 留一組次數 | p 值無單位；`positive_*` 是計數，並非 $R$ 或物理斜率。v11 共有 20 個不同 quiet 組 | [verified: robustness/controls code] |

## Phase 6 SQLite 實際欄位對照

以下逐項對照 P6.1–P6.4 六個保存庫；相同欄名的分鐘、事件與逐圈尺度仍以 table 區分。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `interval_start_time_us`、`block_start_time_us`、`block_start_a_m`、`observed_a_m` | P6.1 目前梯形區間前一分鐘、連續 block 首分鐘的 UTC key（us），以及 block 首筆／當筆 POD mean $a$（m） | `observed_cumulative_delta_a_m=observed_a_m-block_start_a_m`；首分鐘不形成積分點 | [verified: P6.1 code/schema] |
| `kernel_increment_kg_m`、`cumulative_kernel_kg_m` | 目前 60 s 梯形核增量與自 block 首筆起的增量和，kg/m | $K_n=\sum \Delta K$；只在同 chunk、相鄰分鐘累積，與 `block_index` 一起解讀 | [verified: P6.1 code/formula] |
| `observed_cumulative_delta_a_m`、`predicted_cumulative_delta_a_m`、`predicted_a_m`、`residual_m` | 依序為 $a_n-a_{\mathrm{block,start}}$、$-B_{\mathrm{eff}}K_n$、$a_{\mathrm{block,start}}-B_{\mathrm{eff}}K_n$、預測累積變化減觀測累積變化，皆為 m | P6.1 的 `residual_m` 是分鐘累積殘差；不是 P6.4 的單圈 `m0_error_m` | [verified: P6.1 code/schema] |
| `fit_id`、`beta_eff_m2_kg`、`paired_minute_count`、`integral_point_count`、`block_count` | P6.1 唯一擬合列 ID、固定有效比例（m²/kg）、原始配對分鐘數、可積分累積點數、連續段數 | `integral_point_count=1,575,671` 才是擬合分母的點數；每個 block 首筆不進回歸。`beta_eff_m2_kg` 與後續 `b_eff_m2_kg`／`beff_m2_kg` 同一保存值，欄名不同 | [verified: P6.1 fit/schema] |
| `pod_sample_count`、`density_sample_count`、`first_density_source_file`、`last_density_source_file` | P6.1 每分鐘原生 10 s POD 與 L2 數量、首／末 L2 原始來源檔名 | 來源檔名是 provenance，非模型輸入；分鐘配對門檻和事件 `paired_minute_count` 分母不同 | [verified: pair schema/code] |
| `cumulative_m0_kernel_kg_m`、`cumulative_ridge_kernel_kg_m`、`rho_m0_kg_m3`、`rho_ridge_kg_m3` | P6.2／3 各自用 M0／留場 Ridge 密度（kg/m³）積分出的 block 內 $K$（kg/m） | M0 與 Ridge 共用固定 $B_{\mathrm{eff}}$ 與 mean $a$，但密度與 $K$ 不可互換 | [verified: P6.2/3 code/schema] |
| `predicted_m0_delta_a_m`、`predicted_ridge_delta_a_m`、`m0_residual_m`、`ridge_residual_m` | P6.2／3 分鐘列各自的 $-B_{\mathrm{eff}}K$ 與其減去當前 block POD 變化，m | 這些是 block 內累積分鐘量；事件列另加總各已覆蓋 block 的終點 | [verified: P6.2/3 code/schema] |
| `b_eff_m2_kg`、`event_count`、`summary_id`、`model_id` | P6.2–4 複製的固定有效比例（m²/kg）、事件數、總結列 ID、模型 ID | `model_id` 指 `M0` 或 `P5V2_RIDGE`；`summary_id`／`fit_id` 是識別字串，不參與數值公式 | [verified: P6.2–4 schema/code] |
| `m0_covered_error_m`、`ridge_covered_error_m`、`absolute_error_m` | P6.4 分鐘 covered 累積誤差為模型 covered 變化減 POD covered 變化；`absolute_error_m` 是 P6.2／3 事件誤差的絕對值，皆為 m | covered 分鐘值在目前 block 之前只加總已完成 blocks，與 P6.4 圈間誤差不同；`absolute_error_m` 須連同 M0／Ridge 事件表讀 | [verified: event code/schema] |
| `m0_absolute_percentage_error`、`ridge_absolute_percentage_error`、`mean_absolute_percentage_error` | 各模型事件 $100\lvert e_{\mathrm{event}}/\Delta a_{\mathrm{POD,event}}\rvert$，以及各事件百分比的算術平均，% | 分母是同事件 covered POD 下降；不是 2,262 圈 pooled 的百分比 | [verified: event/summary code] |
| `mean_error_m`、`mean_absolute_error_m`、`median_absolute_error_m`、`root_mean_square_error_m` | 所屬 table／model 的 signed mean、MAE、median AE、RMSE，m | P6.1 用累積分鐘殘差；P6.2／3 用事件端點；P6.4 `orbit_summary` 用 pooled 圈間誤差。欄名相同不代表分母相同 | [verified: score code/schema] |
| `underestimated_count`、`overestimated_count` | 事件模型誤差 $e>0$、$e<0$ 的場數 | 下降為負值，$e>0$ 表示預測下降量較小；零誤差不計入兩者 | [verified: P6.2/3 summary code] |
| `previous_pod_mean_a_m`、`current_pod_mean_a_m`、`observed_orbit_delta_a_m` | 前後兩個完整 POD 圈的 mean $a$（m）及後減前差（m） | P6.4 逐圈列的觀測答案，不是 P6.1 分鐘 `observed_a_m` | [verified: orbit score code/schema] |
| `predicted_m0_orbit_delta_a_m`、`predicted_ridge_orbit_delta_a_m` | 前後圈終點對齊分鐘錨點的 covered 模型累積值之差，m | 只有相鄰完整圈且兩錨點同 block 時計分；與事件總 `predicted_*_covered_delta_a_m` 尺度不同 | [verified: orbit score code/schema] |
| `m0_mean_error_m`、`ridge_mean_error_m`、`m0_mean_absolute_error_m`、`ridge_mean_absolute_error_m`、`m0_median_absolute_error_m`、`ridge_median_absolute_error_m`、`m0_root_mean_square_error_m`、`ridge_root_mean_square_error_m` | P6.4 每事件各模型的 signed mean、MAE、median AE、RMSE，m | 分母是該事件有效圈間數；25 場等權的主分數另從各場 MAE 平均 | [verified: orbit event summary code] |
| `closer_orbit_count`、`m0_closer_orbit_count`、`ridge_closer_orbit_count`、`tied_orbit_count` | pooled 某模型勝出的圈數、每場 M0／Ridge 較接近 POD 的圈數、平手圈數 | 每圈比較 $\lvert e_{\mathrm{M0}}\rvert$ 與 $\lvert e_{\mathrm{Ridge}}\rvert$；不同於以每場 MAE 判勝的場數 | [verified: P6.4 score code] |
| `storm_count`、`m0_win_count`、`ridge_win_count`、`tied_storm_count` | P6.4 事件等權比較的總場數與 M0／Ridge／平手場數 | 每場先比較兩模型該場圈間 MAE，再計一場勝負；不能從逐圈勝數推回 | [verified: P6.4 storm summary code] |

## Phase 7 SQLite 實際欄位對照

同名欄位以 table 為範圍；事件累積量與圈間差量不能互代。下列欄名逐一對照 Phase 7 三個保存庫的 schema 與計算入口。

| 欄位 | 定義與單位 | 來源與關聯 | 狀態 |
| --- | --- | --- | --- |
| `quiet_pre_start_time_us`、`quiet_pre_end_exclusive_time_us`、`quiet_post_start_time_us`、`quiet_post_end_exclusive_time_us` | Phase 7 暴前／暴後 quiet run 的 UTC 起點與不含終點，us | 這四個邊界決定各 run 的覆蓋分母；不可當成事件相位窗或 POD 圈端點 | [verified: event schema/code] |
| `r_ridge_external`、`ridge_minus_fit_r` | 外測事件的 $\widehat R_k^{\mathrm{full25}}$；及 `r_ridge_external-r_fit_external`，皆無單位 | 前者用固定 25 場 Ridge 參數，後者與同場 L2 回溯擬合倍率比較；不是「預測誤差」的獨立外測真值 | [verified: density code and saved events] |
| `fit_rmse_log_density`、`ridge_rmse_log_density` | 各事件有效相位分鐘的 $\sqrt{\operatorname{mean}_i[\ln(\rho_{\mathrm{model},i}/\rho_{\mathrm{L2},i})^2]}$，無單位 | fit 用同場 $R_{\mathrm{fit,external}}$，Ridge 用 $\widehat R^{\mathrm{full25}}$；同一批相位分鐘 | [verified: saved event scores] |
| `rho_l2_phase_kg_m3`、`rho_msis_quiet_phase_kg_m3`、`h_phase_nt` | Phase 7 相位窗口的 L2、quiet MSIS 密度（kg/m³）與 V2 SME 響應（nT） | 後兩者與 $R$ 乘成 D-model 密度；L2 只進同場 fit／評分，不能當 Ridge 外測輸入 | [verified: minute schema/code] |
| `rho_fit_external_kg_m3`、`rho_ridge_external_kg_m3` | 分別為 $\rho_{\mathrm{MSIS,q}}R_{\mathrm{fit,external}}e^{G_{\mathrm{V2}}H_{\mathrm{V2}}}$、$\rho_{\mathrm{MSIS,q}}\widehat R^{\mathrm{full25}}e^{G_{\mathrm{V2}}H_{\mathrm{V2}}}$，kg/m³ | 兩線共用 quiet 密度、$G,H$，只換倍率來源；後者進 Phase 7 decay | [verified: all saved density minutes] |
| `rho_m0_kg_m3`、`rho_ridge_kg_m3` | Phase 7 decay 分鐘聯接的 M0、Ridge 相位密度，kg/m³ | 只取 `paired_sample_count=2` 且同分鐘有六個可用 10 s POD mean $a$ 的列；Ridge 是前一列的 `rho_ridge_external_kg_m3` | [verified: decay join/code] |
| `observed_block_delta_a_m`、`predicted_m0_block_delta_a_m`、`predicted_ridge_block_delta_a_m` | 自目前連續 block 首筆起的 POD、M0、Ridge 累積半長軸變化，m | 每逢分鐘缺口或 POD chunk 改變歸零；模型列為 $-B_{\mathrm{eff}}K_{\mathrm{block}}$ | [verified: decay minute code] |
| `predicted_m0_covered_delta_a_m`、`predicted_ridge_covered_delta_a_m` | 已完成 blocks 的預測變化總和，加上目前 block 的預測變化，m | 同表 `observed_covered_delta_a_m` 用相同覆蓋 blocks；事件列取最後分鐘。不能把跨缺口首尾 POD 差當此值 | [verified: minute/event code] |
| `paired_minute_count`、`block_count`、`beff_m2_kg` | Phase 7 事件通過密度/POD 精確聯接的分鐘列數、連續 blocks 數、固定 $B_{\mathrm{eff}}$（m²/kg） | `beff_m2_kg` 來自 Phase 6 P6.1 單一擬合，不在 Phase 7 重估；`paired_minute_count` 與密度庫 `valid_phase_minutes` 分母不同 | [verified: decay event code] |
| `pod_start_time_us`、`pod_end_time_us`、`model_start_time_us`、`model_end_time_us` | 相鄰完整 POD 圈的真實終點、以及各自最近分鐘模型錨點，UTC us | 兩個時間差可不同；先確定兩模型錨點同 block 才有圈間分數 | [verified: score code and saved endpoints] |
| `observed_delta_a_m`、`m0_delta_a_m`、`ridge_delta_a_m` | 後圈減前圈 POD mean $a$、及兩分鐘錨點的 M0／Ridge covered 累積變化差，m | 三個差量屬同一圈間配對，與 Phase 7 decay 事件端點累積量不同 | [verified: score code] |
| `m0_error_m`、`ridge_error_m` | 在 `orbit_score_v1` 是模型圈間差減 POD 圈間差；在 `phase7_decay_event_v1` 是模型 covered 事件變化減 POD covered 事件變化，m | 同名但取樣尺度與分母不同；不可把事件誤差當單圈誤差 | [verified: both table formulas] |
| `m0_mae_m`、`ridge_mae_m`、`m0_rmse_m`、`ridge_rmse_m` | `orbit_event_score_v1` 每事件的平均絕對誤差、均方根誤差，m | 各除以該場 `orbit_count`；五場合計報告再用 453 圈 pooled，而不是這五列的算術平均 | [verified: score code and saved events] |
| `closer_model`、`algorithm_version` | 前者在 Phase 7 decay 事件列依 $\lvert e_{\mathrm{ridge}}\rvert<\lvert e_{\mathrm{m0}}\rvert$ 選 `ridge`，否則 `m0`；後者為產生該表的演算法版本字串 | Phase 7 事件 tie 歸 `m0`；Phase 6 逐圈分數另有 `TIE`，兩者規則與標籤大小寫皆不同。`algorithm_version` 不參與數值公式 | [verified: code/schema] |

## 保存欄位補充與依賴

這些欄位是上面公式的輸入、支持範圍或計分分母；同名欄位須連同 table 與 Phase 版本閱讀。

| 欄位／符號 | 定義與單位 | 依賴與不能混用的對象 | 狀態 |
| --- | --- | --- | --- |
| `storm_id`、`source_time_us` | 事件 ID、Phase 2／2R 來源分鐘 UTC key（us） | 二者構成逐事件分鐘鍵；`source_time_us` 沿用 P2.5，不是新取樣時間 | [verified: schema] |
| `minute_label(time_us)` | DNSAPOD 原生 epoch 四捨五入到最近 UTC 整分鐘的標籤，us；恰在半分鐘時向後取整 | Phase 2 每分鐘最多兩筆原生約 30 s L2；`1691038890000000` 與 `1691038920000000` 都歸到 `1691038920000000` | [verified: sampled source pair] |
| `raw_3_rate_m_s`、`raw_5_rate_m_s` | 完整 3／5 相位圈 raw OLS 斜率，m/s | `3`／`5` 是圈數；不同於固定 3／5 分鐘平均 | [verified: schema/code] |
| `joint_3_rate_m_s`、`joint_5_rate_m_s` | 同窗口扣 H2/H3 諧波後的 joint OLS 斜率，m/s | raw 與 joint 各自估計係數，不共用標準誤 | [verified: schema/code] |
| `*_sigma_m_s`、`*_sample_count`、`*_reject_reason` | 對應斜率的 1-sigma（m/s）、樣本計數、拒絕原因 | 四套 3／5 圈 × raw／joint 各自一組；空值須連同拒絕原因讀 | [verified: schema] |
| `compound`、`n_minima` | 事件是否合併多個最低點的旗標、合併最低點數 | 描述 Phase 2／2R 的局部最低點群組，不代表物理 pulse 數 | [verified: schema/code] |
| `phase_t0_rad`、`phase_start_rad`、`phase_end_rad` | $t_0$、窗口起點、終點的連續軌道相位，rad | 不可把 modulo $2\pi$ 的顯示相位代入窗口界 | [verified: schema] |
| `phase_orbits_before`、`phase_orbits_after` | 事件 $t_0$ 前 31 圈、後 62 圈的連續相位支持，計數 | Phase 2R 先在單一 Phase 1R 連續段檢查兩側支持，缺任一側即排除；不是 P1 OLS 的 3／5 圈視窗 | [verified: code] |
| `storm_event_phase_exclusion_p2r_v1.reason` | Phase 2R 候選事件排除原因字串 | `no_contiguous_phase_at_t0`、`insufficient_phase_before_t0`、`insufficient_phase_after_t0`；49 場候選中 3 場排除，與 46 場最終集合的分母不同 | [verified: stored rows] |
| `paired_sample_count`、`phase_expected_sample_count`、`phase_paired_sample_count` | 一分鐘 L2 配對數、相位窗口預期樣本數、窗口實際配對數，皆為計數 | `phase_paired_coverage=phase_paired_sample_count/phase_expected_sample_count`；分母不是分鐘數 | [verified: schema/code] |
| `phase_is_valid_80pct`、`event_is_valid_80pct` | 相位窗口、事件窗口各自達 80% 覆蓋的 0／1 旗標 | 兩種窗口與分母不同，不可互換有效性判定 | [verified: schema/code] |
| `sme_not_before_time_us`、`kyoto_not_before_time_us`、`ap_source_end_time_us` | SME、Kyoto、$ap$ 來源可用性時間戳，us | 與物理觀測 `source_time_us` 分開；不可從觀測時刻推定資料何時可用 | [verified: schema] |
| `assumed_support_start_time_us`、`assumed_support_end_time_us`、`core_ready_time_us` | P2.3／P2R.3 分鐘標籤的假定 60 s 支持邊界與核心資料最早齊備時間，UTC us | 支持是 `source_time_us ± 30 s`，是分鐘代表區間，**不是**左右 10 s 相位來源錨點；`core_ready_time_us=max(sme_not_before_time_us,kyoto_not_before_time_us,phase_right_time_us)`。核心可用性未包含 F10.7A 置中 81 日的未來觀測，也不能直接稱整筆模型可即時使用 | [verified: code and all saved minute support keys] |
| `h_raw_tau_*_nt`、`h_phase_tau_*_nt` | 原生分鐘響應、中心相位平均後響應，nT | Phase 3 粗格點 `*` 對應 0–10 h、每 0.25 h；4.65 h 另由連續 SME 計算 | [verified: schema/report] |
| `orbit_end_time_us`、`previous_orbit_end_time_us` | 相鄰完整 POD 圈終點 UTC，us | `orbit_duration_s` 是兩終點時間差；分數歸於後一圈終點 | [verified: schema/report] |
| `model_start_time_us`、`model_stop_time_us`／`model_end_time_us` | 前後兩個 POD 圈終點各自對齊的模型分鐘 UTC，us；Phase 6 欄名為 `model_stop_time_us`，Phase 7 為 `model_end_time_us` | Phase 6 兩端須同一 `block_index`／`chunk_id`，Phase 7 依同一連續模型 block；積分差值取兩個模型錨點累積量相減。`model_minute_count=(model_stop_time_us-model_start_time_us)/60 s+1` 是含兩端的分鐘列數，不是兩錨點之間的積分步數；全 2,262 筆 Phase 6 保存列吻合 | [verified: code and saved keys] |
| `model_minute_count`、`scored_orbit_count` | 圈間模型分鐘數、事件有效圈間區間數，皆為計數 | 與 Phase 1 OLS 樣本數、Phase 4 有效分鐘數不同 | [verified: schema] |
| `mae_margin_m` | 兩模型事件 MAE 差距，m | `winner_model` 由每場 MAE 判定，事件各得一票；pooled 圈數不是事件權重 | [verified: schema/report] |
| `m0_macro_mean_orbit_mae_m`、`ridge_macro_mean_orbit_mae_m` | 先算每場有效圈的 orbit MAE，再對事件等權平均，m | Phase 6 P6.4 主分數；與合併 2,262 圈後直接算 pooled MAE 不同 | [verified: stored storm score] |
