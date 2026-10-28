# POD 執行順序

NOTE: 下列 06--09 的 10 分鐘 rebuild 是 retained legacy，不會生成現行
P1.5.6 v2／P1.6 v2／P1.7 v2。現行 checkpoint 與下游 working copy 的接續、
輸入和輸出見 [phase_1_execution_plan.md](phase_1_execution_plan.md)。

決定：POD 的可執行 processing module 使用兩位數編號。編號是資料依賴順序；`load_` 是 reader helper，`down_` 是下載工具，report/audit 是檢查工具，均不編入寫入順序。

完整 rebuild 只由下列入口執行：

```powershell
python -m research_workspace.phases.phase1.code.prep_phase1_rebuild NEW_DATABASE
```

```text
01 prep_01_raw_pod.py
   -> raw POD state
02 prep_02_source_provenance.py
   -> source/header provenance
03 prep_03_orbital_elements.py
   -> instantaneous semi-major axis
04 prep_05_pod_quality.py
   -> usable rows and chunks
05 prep_04_mean_orbit.py
   -> Brouwer-Lyddane mean semi-major axis
06 prep_06_orbit_10min.py
   -> 10-minute mean-orbit bins
07 prep_07_decay_rate.py
   -> signed 3h/6h/12h semi-major-axis rates
08 phase1/prep_08_analysis_10min.py
   -> causal SYM-H and space-weather features
09 phase1/prep_09_release_audit.py
   -> manifest and integrity audit
```

`04` 先於 `05`：quality 先建立可發布 rows 與 chunks；cache restore 若顯式指定 cache artifact，
`prep_mean_orbit_cache.py` 只在 source signature、完整 ITRF state 與 numerical environment 相符，且舊
mean rows 覆蓋所有 current usable rows 時重用。否則 fail fast，不得回退成未驗證的 cache。不得在重建途中手動跳過任何編號。
