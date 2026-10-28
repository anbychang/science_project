# Swarm-A 磁暴與軌道衰減研究

研究目標是釐清地磁暴與 Swarm-A 軌道衰減的關係。目前已完成三年與十二年的磁暴分鐘資料，以及三年密度響應分析；衰減率候選仍未校準。Phase 4 的 GPR 殘差修正已建立計畫，尚無模型結果。

先看 [OUTPUT.md](OUTPUT.md) 閱讀 GitHub 上的成果；[CATALOG.md](CATALOG.md) 列出本機資料庫、程式與文件位置。[GLOSSARY.md](GLOSSARY.md) 定義術語，[ISSUE.md](ISSUE.md) 記錄暫緩問題。

## 各 Phase 狀態

| Phase | 狀態 | 目前結果與入口 |
| --- | --- | --- |
| [Phase 0](phases/phase0/docs/plans/PLAN.md) | 共用基礎 | 保存原始來源、下載／載入程式與共用計算；沒有獨立研究結果。 |
| [Phase 1](phases/phase1/reports/orbit_analysis_report.md) | [done: candidate] 三年 | 逐 10 秒衰減候選、對齊特徵與資料契約稽核已完成；真實阻力衰減的物理校準未完成。 |
| [Phase 1R](phases/phase1r/reports/orbit_analysis_report_2014_2026.md) | [working] 十二年 | 獨立的 P1.5.1 checkpoint 與逐 10 秒候選工作庫；尚非正式衰減率 release。 |
| [Phase 2](phases/phase2/reports/phase_2_final_report.md) | [done] 三年 | 25 場磁暴、一分鐘事件資料與 P2.6 描述性 peak QC；檢查點已固定。 |
| [Phase 2R](phases/phase2r/reports/phase_2r_final_report.md) | [done] 十二年 | Phase 2 方法的獨立重現；49 場候選中 46 場有完整分鐘資料；檢查點已固定。 |
| [Phase 3](phases/phase3/reports/phase_3_final_report.md) | [done] 三年 | 25 場離線密度響應、逐場 $R_k$ 校準與 M1 回溯曲線；結果已結案。 |
| [Phase 4](phases/phase4/docs/plans/PLAN.md) | [plan] | GPR 殘差修正已有計畫；尚未交付模型結果。 |

Phase 1／1R 的舊 10 分鐘分支是歷史資料，不能與現行逐 10 秒候選混用。Phase 2／2R 的 peak QC 是描述性結果；Phase 3 的 M1 與 M0 比較使用不同校準機會，不能宣稱 M1 已勝出。現階段沒有完成 drag propagator 或 XYZ 預報。

## 專案位置

```text
phases/
  phase0/       共用來源與程式
  phase1/       三年軌道資料與工作結果
  phase1r/      十二年軌道資料與工作結果
  phase2/       三年磁暴分鐘資料與結案報告
  phase2r/      十二年重現與結案報告
  phase3/       三年密度響應與結案報告
  phase4/       新研究計畫
docs/           跨 Phase 的報告索引、資料血緣與寫作規則
```

各 Phase 的程式在 `code/`，SQLite 在 `data/sqlite/`，報告在 `reports/`，圖在 `figures/`。原始來源只存於 `phases/phase0/data/raw/`。大型 SQLite 與多數原始檔留在本機，未上傳 GitHub；GitHub 上的連結以 [OUTPUT.md](OUTPUT.md) 為準。

從專案根目錄執行 `python -m phases.<phase>.code.<module>`；各步參數、Input／Output 與重算順序依所屬 Phase 的計畫和資料血緣。資料血緣格式及不可變原始資料規則見 [RULES.md](docs/data_lineage/RULES.md)。歷史決策見 [TIMELOG.md](TIMELOG.md)。

一般 Python 依賴列在 [requirements.txt](requirements.txt)。P1.5.1 的 Orekit 平均軌道計算另需本機 `.orekitvenv/` 內的 `orekit-jpype`、`jdk4py` 與 `orekit-data`；版本與環境紀錄見 [P1.5 方法文件](phases/phase1/docs/plans/p1_5_resample_and_decay.md)。`.orekitvenv/` 未提交 GitHub。
