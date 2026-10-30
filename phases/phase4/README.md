# Phase4 Trial 與 Final 保留位

目前有五個完成的 Trial；Trial6 已建立計畫，尚未執行：

| Phase4 Trial | 方法 | 結果報告 |
| --- | --- | --- |
| Trial1 | Trial4 固定基線上的五特徵資料內 GPR | [Trial1 報告](../phase4-trial1/reports/phase_4_trial4_altitude_gpr_report.md) |
| Trial2 | Trial1 的 20/5 storm-group held-out 檢查 | [Trial2 報告](../phase4-trial2/reports/phase_4_trial4_groupcv20_5_report.md) |
| Trial3 | nested 20/5 四特徵 GPR | [Trial3 報告](../phase4-trial3/reports/phase_4_trial4_nested_groupcv_report.md) |
| Trial4 | 時間、固定 Trial4 tau、季節 nested GPR | [Trial4 報告](../phase4-trial4/reports/phase_4_time_tau_season_report.md) |
| Trial5 | `dSYM-H/dt`、`ap_step`、`F10.7` nested GPR | [Trial5 報告](../phase4-trial5/reports/phase_4_trial5_driver_report.md) |
| Trial6 | 複合磁暴日夜／磁緯度分區與同場事後 GPR | [Trial6 計畫](../phase4-trial6/docs/plans/PLAN.md)；結果 [not created] |

檔名中的 `trial4` 多半指「以 Phase3 Trial4 D-model 為基線」，不是該檔屬於 Phase4 Trial4。這是舊命名，不能用檔名前綴判定 Phase4 Trial 編號。

Phase4 Final 狀態：[not created]。它保留給後續通過明確驗收條件的方法；不得重用 Trial1--Trial5 的成績宣稱 final。

Trial1--Trial5 的共同比較、每個特徵目前可主張的貢獻，以及不可主張的範圍，見[特徵貢獻整理](reports/phase_4_feature_contribution_summary.md)。單欄 `only-feature`／`drop-feature` 數值見[單一特徵 GPR 消融](reports/phase_4_feature_ablation_report.md)。
