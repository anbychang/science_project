# Phase4 Trial6 計畫：複合磁暴的日夜與緯度 Ridge 殘差

狀態：[not created]。2026-10-30 已建立獨立工作空間與本計畫；資料準備、圖、Ridge、報告與血緣均尚未執行。這是事後密度修正實驗，不是預報，也不會修改 Phase 2、Phase 3、Phase 3 Trial4 或 Phase4 Trial1--Trial5 的輸出。

## 決定與問題

固定 Phase 3 Trial4 D-model。先問同一場複合磁暴中，剩餘密度偏差是否隨時間、當地太陽時與磁緯度改變；再測試固定基底的 Ridge 是否能從同場已有觀測，補回一段暫時遮住的觀測。Trial6 不重估 $R_k$、$\tau_k$ 或 $G$，也不把 Ridge 結果直接升為 Phase4 Final。

現有 Phase4 Trial1--Trial5 檢查的是整圈錨點殘差的資料內貼合或跨事件泛化，沒有建立日夜分區的同場事後補值。本 Trial 的資料單位與問題均不同，分數不可直接放進 Trial1--Trial5 排名。

## 固定來源與工作邊界

| 來源 | 本 Trial 讀取內容 | 邊界 |
| --- | --- | --- |
| Phase 3 Trial4 D-model SQLite | 每場固定參數、整圈相位密度與殘差 | 唯讀；保留原模型 |
| Phase4 Trial1 SQLite | 25 場、2,295 個每軌代表錨點的 `{storm_id, time_us, u_rel_rad}` | 只借錨點，不讀其 GPR 修正作為輸入 |
| Phase 2.6 SQLite | 事件窗、$t_0$、`u_rel_rad`、`compound`、`storm_minimum_v2` | 唯讀；`compound` 與局部低點只供診斷 |
| DNSAPOD 0301 原生 ZIP 與既有 quiet-MSIS 計算 | 同一批有效 30 秒 L2、UTC、地理位置、高度與平靜 MSIS | 保持 Phase 3 的有效旗標、配對與安靜 ap 定義 |

固定讀取路徑：

```text
phases/phase3-trial4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite
phases/phase4-trial1/data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite
phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite
phases/phase3-trial4/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite
phases/phase0/data/raw/swarm_density_pod/manifest_dnsapod_20230701_20260630.json
```

新結果只寫 `phases/phase4-trial6/`。原生來源和既有 SQLite 不更新、不刪除；新的衍生表保留 `algorithm_version` 與來源時間鍵。資料缺口不跨越填補。

## 資料單位：整圈錨點下的日夜／緯度分區

Trial4 的目標是中心相位 $u\pm\pi$ 約一整圈平均值。一個錨點同時包含白天與黑夜，不能用錨點瞬間的位置替整圈標日夜。Trial6 保留同一個相位支撐與 paired native samples，再把其中樣本分成「日／夜」乘「南高緯／中緯／北高緯」最多六區；磁緯度 $\pm60^\circ$ 只是預先固定的探索性分區，不代表極光邊界。

對每個錨點 $i$，固定 Trial4 的整圈修正倍率

$$
C_i=\frac{\rho_{\mathrm{Trial4,phase},i}}{\rho_{\mathrm{MSIS,q,phase},i}}
   =R_k\exp(GH_{\tau_k,i}).
$$

每個分區 $s$ 以相同有效原生樣本求 L2 與 quiet-MSIS 平均，再定義

$$
\widehat\rho_{s,i}=C_i\,\rho_{\mathrm{MSIS,q},s,i},\qquad
e_{s,i}=\ln\!\left(\frac{\rho_{\mathrm{L2},s,i}}{\widehat\rho_{s,i}}\right).
$$

這是固定整圈倍率下的**分區延伸診斷**；不是 Phase 3 Trial4 原本的逐點預測。所有分區按有效樣本數加權合回整圈時，L2、quiet-MSIS 與固定倍率預測都必須重現原錨點值；若不能重現，停止於資料準備，不跑 Ridge。少於 10 個 paired 30 秒樣本的分區保留在覆蓋審核，但不進 Ridge。

## 特徵與模型契約

| 特徵／欄位 | 處理方式 | 用途 |
| --- | --- | --- |
| `t_rel_s` | 錨點 UTC `time_us` 減該場最深 SYM-H 低點 `t0_time_us`，換成秒 | Ridge 時間座標；負值不可直接稱「磁暴前」 |
| `solar_local_sin`, `solar_local_cos` | 原生樣本以 UTC 與經度求當地太陽時角，再在分區內分別平均正弦、餘弦 | 表示上午／下午與跨午夜連續性；不平均 0--24 時數 |
| `solar_zenith_rad`, `illumination` | 以原生 UTC、地理緯經度算當地太陽天頂角；$<\pi/2$ 為日側，其餘為夜側 | 真正的日夜分區；是當地大氣日照，不是衛星是否進入地影 |
| `magnetic_latitude_rad`, `latitude_band` | 原生時間、位置與高度轉磁緯度；分區內保留平均磁緯度 | 區分南北及高緯；地理緯度只作來源與對照，不冒充磁緯度 |

先用 DNSAPOD 內既有地理緯經度與高度；無需從 Phase 1 軌道重建位置。環境已有 `astropy`，日照幾何先用它計算。環境尚無磁緯度轉換工具；實際執行前須選定並核對可用的地磁座標實作。若此門檻未通過，只可做地理緯度覆蓋診斷，不產出「磁緯度 Ridge」結果。

Ridge 只讀 `{t_rel_s, solar_local_sin, solar_local_cos, illumination, magnetic_latitude_rad}`。設計矩陣固定為常數、標準化後的時間、日照正弦／餘弦、日照旗標、磁緯度的一次與二次項，以及 `illumination * magnetic_latitude_rad`；所有連續欄位只由訓練區標準化。固定 `alpha=1.0`，不在遮住區調參。`compound`、`n_minima`、SME、SYM-H、ap、$H_\tau$、$R_k$、$\tau_k$ 與原始密度都不作 Ridge 輸入；既有物理修正只透過固定的 $C_i$ 進入基線。高度只保留供覆蓋審核，不進第一個模型。

## 複合磁暴的四條處理規則

1. 沿用 Phase 2 的 `storm_id` 與完整事件窗。相鄰 SYM-H 局部低點不拆成獨立訓練事件。
2. $t_0$ 只是同場時間座標。第二波或第三波再增強可能發生在 $t_0$ 前後，不把事件強制分成一次主相與一次恢復。
3. `compound` 與 `n_minima` 不作模型特徵。25 場中 24 場標為複合；局部低點數不等於獨立能量脈衝數。SME、ap 已參與既有模型或試驗，不在 Ridge 中重學。
4. 每場圖同時保留 L2、固定 Trial4、Ridge 殘差、SME 與 SYM-H。對主要再增強時段逐段查殘差；脈衝標記只供圖與報告解讀，不作 Ridge 標籤或輸入。

## 執行順序與停止條件

| 順序 | 動作 | 必須留下的檢查 | 狀態 |
| --- | --- | --- | --- |
| 1 | 固定 2,295 個錨點；重讀配對原生樣本與 quiet-MSIS；計算日照及磁緯度 | 原生時刻、有效旗標、配對數、座標轉換版本與缺口清單 | [not created] |
| 2 | 建立六個分區與固定倍率殘差 | 加權合回整圈後與 Trial4/L2/quiet-MSIS 一致；分區樣本數與各場覆蓋 | [not created] |
| 3 | 先畫 25 場時間、日夜、緯度及複合脈衝診斷 | 哪些分區實際有資料；主要再增強時段有無一致偏差 | [not created] |
| 4 | 只有覆蓋與重建檢查通過才做同場 Ridge | 固定設計矩陣與 `alpha=1.0`；只用同場未遮住的分區 fit | [not created] |
| 5 | 遮住連續約 6 小時的完整軌道群，再補回 | 訓練與遮住區不得共享原生樣本；逐場及逐分區比較固定基線與 Ridge 的對數 RMSE、MAE | [not created] |
| 6 | 寫報告、圖與資料血緣 | 25 場摘要、主要複合事件個案、失敗案例、來源與方法限制 | [not created] |

第 5 步只驗證**固定 Trial4 基線上的同場事後殘差補值**：Trial4 參數本身已使用整場 L2，不能把遮住區分數寫成整條密度模型的獨立外測。若日夜／緯度沒有可辨認的殘差結構，或 Ridge 在遮住區未改善，直接報負結果，不再任意添加 driver 或調整基底。

## 預留輸出與開始條件

```text
code/                 prep_trial6_sector_features.py、calc_trial6_ridge.py、prep_trial6_ridge.py
data/sqlite/          swarm_a_trial6_sector_features.sqlite、swarm_a_trial6_sector_ridge.sqlite
data/analysis/        trial6_feature_audit.csv、trial6_block_metrics.csv、trial6_event_metrics.csv
figures/              trial6_25storm_diagnostics.png、逐場重點圖
reports/              trial6_daynight_compound_report.md
docs/lineage/          trial6_daynight_compound.md（執行後依 data-lineage RULES 寫 P4.8 起各步）
tests/                 非平凡日照、分區及合回整圈計算的最小可執行檢查
```

目前只建立目錄、本計畫與入口文件；上列程式和結果檔都尚未建立。下一次開始執行時，先解決磁緯度工具與來源座標的核對，再做第 1 步。到第 3 步看完覆蓋及殘差圖，才決定是否進入 Ridge。Phase4 Final 保持 `[not created]`。
