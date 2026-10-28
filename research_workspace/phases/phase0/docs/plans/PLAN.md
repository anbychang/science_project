# Phase 0：全專案共用基礎

狀態：[active]。Phase 0 保存各 Phase 共用的原始來源、讀取與下載程式、基礎計算及測試；不產生獨立的研究結論。

```text
phases/phase0/data/raw/     ESA、SuperMAG、京都、GFZ、CelesTrak 原始檔
research_workspace/phases/phase0/code/data/         下載、讀取與原始資料寫入
research_workspace/phases/phase0/code/calculation/  共用座標、時間、密度與數值計算
phases/phase0/tests/        上述共用程式的測試
```

原始檔只保留一份。各 Phase 的 SQLite、分析 CSV、圖和報告仍寫入自己的目錄；Phase 0 程式不得回寫已結案的 Phase 2、2R、3 檢查點。原始 SQLite table 保持不可變，衍生結果寫入獨立 table。

Phase 1 的 mean orbit 與衰減候選流程位於 `research_workspace/phases/phase1/code/`；Phase 2／2R 的磁暴分鐘流程位於各自的 package；Phase 3 的密度響應流程位於 `research_workspace/phases/phase3/code/`。[資料血緣索引](../../../../docs/data_lineage/README.md)列出各研究 Phase 的來源與輸出契約。
