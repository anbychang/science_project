# Phase4 Trial6 計畫：同場整圈密度的事後補正

狀態：[done]。固定 Phase 3 Trial4 D-model；只在 `phases/phase4-trial6/` 寫新資料與結果。Trial6 檢查同一場磁暴中，已觀測到的 Swarm-A 整圈密度偏差能否補回一段暫時遮住的整圈密度。結果見[報告](../../reports/trial6_within_storm_ridge_report.md)：定期選段與 $t_0$ 區段內插較好，強變化區沒有穩定勝者。這不是預報，也不是跨衛星驗證。

## 固定來源與資料單位

| 來源 | 使用欄位 | 限制 |
| --- | --- | --- |
| `phases/phase4-trial1/data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite` | 25 場、2,295 個每圈錨點的 `storm_id,time_us,rho_l2_phase_kg_m3,rho_trial4_phase_kg_m3,residual_log_density` | 只取固定 Trial4 基線與 L2；不使用 Trial1 GPR 預測 |
| `phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite` | 事件分鐘、相位 `u_rel_rad`、原生配對數 | 唯讀；保持原相位窗口 |
| `phases/phase3-trial4/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite` | 逐分鐘有效配對數 | 唯讀；核對原生樣本選擇 |
| `phases/phase0/data/raw/swarm_density_pod/manifest_dnsapod_20230701_20260630.json` 與 ZIP | 每 30 秒時間、位置、L2 有效樣本 | 唯讀；計算日側比例 |

一筆錨點代表中心相位 $u\pm\pi$ 約一圈的平均。既有 Trial4 參數 $R_k,\tau_k,G$ 不重估。目標仍是整圈對數殘差：

$$e_i=\ln(\rho_{\mathrm{L2,phase},i}/\rho_{\mathrm{Trial4,phase},i}).$$

## 兩組待測特徵

| 欄位 | 定義 | 用途 |
| --- | --- | --- |
| `elapsed_hours` | 錨點 `time_us` 距同場第一個有效錨點的時數 | 每場的時間座標；不把最深 SYM-H 低點當成唯一物理起點 |
| `bend_12h`, `bend_24h`, ... | 每 12 小時固定一個轉折，`max(0, (elapsed_hours - knot_hours)/12)` | Ridge 可以沿時間改變斜率；所有轉折在看殘差前固定 |
| `day_fraction` | 同一 $u\pm\pi$ 窗口內，日側有效原生樣本數／全部有效原生樣本數 | 只在第二組模型加入；夜側比例是 `1-day_fraction`，不重複加入 |

日側由原生 UTC 與地理緯經度的太陽高度角大於 $0^\circ$ 定義。這是當地大氣的日照幾何，不是衛星是否在地影。先沿用 L2 有效且具 MSIS weather 的原生樣本；每分鐘數量須與既有 quiet-MSIS 配對數相等。日側數與配對數按相同相位窗口加總。若配對、窗口或錨點對不上，停止模型步驟並報差異。

A 組只用時間欄位；B 組用相同時間欄位加 `day_fraction`。每場分別 fit `Ridge(alpha=1.0)`，只在訓練區標準化欄位。`storm_id` 是分組鍵，不是數值特徵。SME、ap、SYM-H、$R_k$、$\tau_k$、原始密度與錨點瞬間的日夜標籤都不作輸入。若 `day_fraction` 缺乏變化，B 組的該欄不提供可辨識的訊號，按實測結果報告。

## 評估與停止條件

1. 每場遮住連續約六小時的完整錨點群；訓練錨點的原生相位支撐不得與遮住區重疊。遮住區前後都要留有同場觀測。
2. 同一批遮住點比較固定 Trial4（零殘差修正）、前後觀測的線性內插、A 組 Ridge、B 組 Ridge。比較逐場與合併的對數 RMSE、MAE，並記錄每場勝負及日側比例範圍。
3. 只把遮住區的分數當成「固定 Trial4 基線上，同場殘差補值」測試。Trial4 參數已由整場 L2 擬合，不能宣稱整條模型是獨立外測。
4. 若 A、B 均不能穩定超過簡單內插，報負結果，不增加 driver 或任意調整轉折與 `alpha`。主要再增強時段的失敗要如實列出。

追加的壓力測試保持同一模型與遮住規則：每場遮住 $t_0-3$ 到 $t_0+3$ 小時；另在不重疊的六小時候選窗中，選半小時 SYM-H 中位數總變化量最大的區段。後者只表示 SYM-H 起伏大，不聲稱找到物理上最複雜的脈衝。選段不看 L2 殘差；每組各 25 個窗口，不把它們和定期窗口視為同一測試集。

事前選擇規則只讀真正缺口外的 L2：一條要求最近兩端殘差同方向；另一條在缺口兩側各做一次六小時「假缺口」內插，兩次皆勝過不修正才補真正缺口。未通過或資料不足就保留 Trial4。兩條均在既有 275 個定期區段、25 個 $t_0$ 區段與 25 個強變化區評分，屬同資料探索，不據此升為 Final。

## 輸出

```text
code/                 calc_trial6_daylight.py、prep_trial6_day_fraction.py、calc_trial6_ridge.py、calc_trial6_stress.py、calc_trial6_interpolation_rule.py、prep_trial6_case_figures.py、prep_trial6_one_interpolation_figure.py
data/sqlite/          swarm_a_trial6_day_fraction.sqlite
data/analysis/        trial6_feature_audit.csv、trial6_block_predictions.csv、trial6_block_metrics.csv、trial6_event_metrics.csv、trial6_stress_predictions.csv、trial6_stress_metrics.csv、trial6_interpolation_rule_blocks.csv、trial6_interpolation_rule_predictions.csv、trial6_interpolation_rule_summary.csv
figures/              trial6_event_rmse.png、三場磁暴各一張完整事件與兩個六小時放大圖、trial6_one_storm_interpolation.png
reports/              trial6_within_storm_ridge_report.md
docs/lineage/          trial6_within_storm_ridge.md
tests/                 日側幾何、配對與遮住區的最小可執行檢查
```

以上輸出已建立。Phase4 Final 保持 `[not created]`。Trial6 與 Trial1--Trial5 的跨場分數回答不同問題，不直接排名。
