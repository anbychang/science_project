# P6.4：POD、M0 與 Phase 5 V2 Ridge 下降重整

## 決定

P6.4 不重新積分、不重新擬合模型。它精確連接 P6.2 與 P6.3，整理成三個讀取層次：

1. 每場磁暴的 POD 總下降量。
2. POD 隨時間的累積下降曲線。
3. M0 與 Phase 5 V2 Ridge 的 density、累積預測下降及 POD 誤差。

```text
P6.2 M0 minute/event result
  + P6.3 Ridge minute/event result
  -> exact join by {storm_id, time_us}
  -> event endpoint table
  -> minute density/decline table
  -> 25-storm decline and density figures
```

## 時間曲線

P6.2、P6.3 在每個 continuous block 內各自從零積分。P6.4 為了畫出整場累積曲線，將前一個已覆蓋 block 的 endpoint 加到下一個 block；資料缺口本身仍不補值，圖上也不跨缺口連線。

每場最後一個 minute row 必須精確等於 P6.2、P6.3 event table 的 endpoint：

\[
\Delta a_{POD,k},\qquad
\Delta a_{M0,k},\qquad
\Delta a_{Ridge,k}.
\]

## 統一比較

兩個 density model 使用相同的：

- 25 場 `t0-2 days` 至 `t0+4 days` 窗口。
- P6.1 fixed `B_eff`。
- POD minute semi-major axis。
- block 與缺口規則。

P6.4 報告 MAE、RMSE、MAPE、mean signed error，以及逐場哪個模型的絕對誤差較小。不因整體平均較好就宣稱每場都改善。

## 圖的 POD 顯示

POD 逐分鐘半長軸含明顯軌道週期振盪。下降圖沿用 Phase 1 `swarm_a_phase_orbit_mean_v2` 的 complete-orbit 定義，每圈只畫一個 phase-weighted mean；不使用任意 rolling window。整場以窗口開始前最後一個完整 orbit 為共同零點。

POD 圖不繼承 density pairing 的 block。只有 POD orbit 本身不連續或 `chunk_id` 改變才斷黑線；M0 與 Ridge 仍依 P6.4 block 處理 density 缺口。

逐圈線只改善閱讀，不改寫 P6.4 SQLite。事件總下降、`B_eff` 與 error metrics 仍使用原始 covered minute endpoint。

## 主張界線

- P6.4 是既有結果的 descriptive comparison，不是新模型。
- P6.1 `B_eff` 由同一三年 L2/POD 資料擬合。
- M0 與 Ridge density 都是 orbit-phase average，P6.1 使用逐分鐘 L2 density。
- Ridge 特徵由相同 25 場選出，沒有新事件獨立外測。
- 所有下降曲線仍使用 POD 半長軸計算積分核，不是自由軌道 propagation。
