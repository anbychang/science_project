# Swarm-A 磁暴與軌道衰減研究

研究目標是釐清地磁暴與 Swarm-A 軌道衰減的關係。目前密度研究主線是 `Phase 2 -> Phase 3（歷史輸入）-> Phase 3 Trial4（修正基線）-> Phase 4`：固定三年磁暴分鐘資料與事件後，Trial4 以自由 $R_k$／$\tau_k$ 取代舊 M1 固定參數，再描述其殘差與高度。衰減率候選仍未校準。

先看 [OUTPUT.md](OUTPUT.md) 閱讀 GitHub 上的成果；[CATALOG.md](CATALOG.md) 列出本機資料庫、程式與文件位置。[GLOSSARY.md](GLOSSARY.md) 定義術語，[ISSUE.md](ISSUE.md) 記錄暫緩問題。

## 各 Phase 狀態

| Phase | 狀態 | 目前結果與入口 |
| --- | --- | --- |
| [Phase 0](phases/phase0/docs/plans/PLAN.md) | 共用基礎 | 保存原始來源、下載／載入程式與共用計算；沒有獨立研究結果。 |
| [Phase 1](phases/phase1/reports/orbit_analysis_report.md) | [done: candidate] 三年 | 逐 10 秒衰減候選、對齊特徵與資料契約稽核已完成；真實阻力衰減的物理校準未完成。 |
| [Phase 1R](phases/phase1r/reports/orbit_analysis_report_2014_2026.md) | [working] 十二年 | 逐 10 秒候選與 2014-07 起報告範圍已核對、缺圖已補；尚未建立獨立 release，也未完成物理校準。 |
| [Phase 2](phases/phase2/reports/phase_2_final_report.md) | [done] 三年 | 25 場磁暴、一分鐘事件資料與 P2.6 描述性 peak QC；檢查點已固定。 |
| [Phase 2R](phases/phase2r/reports/phase_2r_final_report.md) | [done] 十二年 | Phase 2 方法的獨立重現；49 場候選中 46 場有完整分鐘資料；檢查點已固定。 |
| [Phase 3](phases/phase3/reports/phase_3_final_report.md) | [retained] 三年 | 唯讀歷史 M1 基線；固定 $R_k$／共同 $\tau$ 的設定不作後續密度分析基線。 |
| [Phase 3 Trial4](phases/phase3-trial4/reports/trial4_joint_fit_tau15_report.md) | [done: descriptive] | 現行修正基線；25 場自由 $R_k$／$\tau_k$ 的 joint fit，已核對來源、公式與保存輸出，仍未外測。 |
| [Phase4 Trial1](phases/phase4/reports/phase_4_trial4_altitude_gpr_report.md) | [done] | Trial4 固定基線上的五特徵資料內 GPR；只量測貼合能力。 |
| [Phase4 Trial2](phases/phase4/reports/phase_4_trial4_groupcv20_5_report.md) | [done] | 20/5 storm-group held-out GPR；RMSE 0.11028，未改善 Trial4 的 0.11005。 |
| [Phase4 Trial3](phases/phase4/reports/phase_4_trial4_nested_groupcv_report.md) | [done] | nested 20/5 storm-group 四特徵 GPR；RMSE 0.12014，劣於 Trial4 的 0.11005。 |
| [Phase4 Trial4](phases/phase4/reports/phase_4_time_tau_season_report.md) | [done] | 時間、固定 Trial4 tau、季節 nested GPR；RMSE 0.11323，仍劣於 Trial4。 |
| [Phase4 Trial5](phases/phase4/reports/phase_4_trial5_driver_report.md) | [done] | 新 geomagnetic driver nested GPR；RMSE 0.13203，明顯劣於 Trial4。 |
| Phase4 Final | [not created] | 保留給通過明確驗收條件的最終方法；不得把 Trial1--Trial5 升格為 final。 |

Phase4 Trial1--Trial5 的特徵組合比較與每個欄位目前可主張的範圍，見[特徵貢獻整理](phases/phase4/reports/phase_4_feature_contribution_summary.md)。
所有歷史、現行與 working Trial 的狀態及報告入口，見 [Trial 索引](docs/trial_index.md)。

Phase 1／1R 的舊 10 分鐘分支是歷史資料，不能與現行逐 10 秒候選混用。Phase 2／2R 的 peak QC 是描述性結果；Trial4 是現行修正的資料內基線，不能當作外測預報，也不能把它的參數解釋成物理量。舊 Phase 3 M1 與 M0 比較使用不同校準機會，不能宣稱 M1 已勝出。現階段沒有完成 drag propagator 或 XYZ 預報。

## 專案位置

```text
phases/
  phase0/       共用來源與程式
  phase1/       三年軌道資料與工作結果
  phase1r/      十二年軌道資料與工作結果
  phase2/       三年磁暴分鐘資料與結案報告
  phase2r/      十二年重現與結案報告
  phase3/       三年密度響應的唯讀歷史基線
  phase3-trial4/ 現行修正的自由 R_k／tau_k 描述性基線
  phase4/       Trial1 資料內描述、Trial2--Trial5 held-out 驗證
docs/           跨 Phase 的報告索引、資料血緣與寫作規則
```

各 Phase 的程式在 `code/`，SQLite 在 `data/sqlite/`，報告在 `reports/`，圖在 `figures/`。原始來源只存於 `phases/phase0/data/raw/`。大型 SQLite 與多數原始檔留在本機，未上傳 GitHub；GitHub 上的連結以 [OUTPUT.md](OUTPUT.md) 為準。

從專案根目錄執行 `python -m phases.<phase>.code.<module>`；`phase3-trial4` 因目錄名含連字號，直接執行其 `code/` 下的入口檔。各步參數、Input／Output 與重算順序依所屬 Phase 的計畫和資料血緣。資料血緣格式及不可變原始資料規則見 [RULES.md](docs/data_lineage/RULES.md)。歷史決策見 [TIMELOG.md](TIMELOG.md)。

一般 Python 依賴列在 [requirements.txt](requirements.txt)。P1.5.1 的 Orekit 平均軌道計算另需本機 `.orekitvenv/` 內的 `orekit-jpype`、`jdk4py` 與 `orekit-data`；版本與環境紀錄見 [P1.5 方法文件](phases/phase1/docs/plans/p1_5_resample_and_decay.md)。`.orekitvenv/` 未提交 GitHub。
