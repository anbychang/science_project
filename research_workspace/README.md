# 研究資料目錄

共用原始來源放在 `phases/phase0/data/raw/`；每個 Phase 的程式、資料庫、分析 CSV、文件、圖和報告放在自己的 `phases/<phase>/`。Python 程式位於各 Phase 的 `code/`；例如從專案根目錄執行 `python -m research_workspace.phases.phase1.code.prep_report_figures`。

```text
research_workspace/
  docs/                  全專案資料血緣、寫作規則與報告索引
  phases/
    phase0/              共用 code、原始來源、基礎計畫與測試
    phase1/              code、工作資料庫、計畫、血緣、圖、報告、測試
    phase1r/             十二年 code、工作資料庫、計畫、圖、報告、測試
    phase2/              code、三年結案資料庫、計畫、血緣、圖、報告、測試
    phase2r/             十二年 code、結案資料庫、計畫、血緣、圖、報告、測試
    phase3/              code、三年密度響應資料庫、分析 CSV、計畫、血緣、圖、報告、測試
    phase4/docs/plans/   Phase 4 計畫
```

Phase 2、2R、3 的結案資料作唯讀研究來源。Phase 4 的新分析寫入自己的目錄，不回寫結案檢查點。執行 Python 模組與測試時，以專案根目錄為工作目錄。
