# P6.4：POD、M0 與 Phase 5 V2 Ridge 下降重整

## 決定

P6.4 不重新積分、不重新擬合模型。它精確連接 P6.2 與 P6.3，整理成三個讀取層次：

1. 每場磁暴的 POD 總下降量。
2. POD 隨時間的累積下降曲線。
3. L2 參考密度、M0 與 Phase 5 V2 Ridge 的 density、累積預測下降及 POD 誤差。
4. 每一個完整 orbit 的局部下降誤差，並以每場 orbit MAE 決定 25 場磁暴的 winner。

```text
P6.2 M0 minute/event result
  + P6.3 Ridge minute/event result
  -> exact join by {storm_id, time_us}
  -> event endpoint table
  -> minute density/decline table
  -> 25-storm decline figure
  -> exact {storm_id, time_us} join to L2 reference density
  -> L2/M0/Ridge density figure
```

## 時間曲線

P6.2、P6.3 在每個 continuous block 內各自從零積分。P6.4 為了畫出整場累積曲線，將前一個已覆蓋 block 的 endpoint 加到下一個 block；資料缺口本身仍不補值，下降圖也不跨缺口連線。

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

六天 endpoint 保留 MAE、RMSE、MAPE 與 mean signed error，但只作累積量輔助結果。

底層誤差使用相鄰完整 orbit 的局部變化：

\[
\Delta a_{POD,j}=\bar a_j-\bar a_{j-1},
\qquad
e_j=\Delta a_{model,j}-\Delta a_{POD,j}.
\]

模型在兩個 orbit endpoint 各對應到最近 UTC minute；兩點必須在同一 density block。POD orbit 必須連續且 `chunk_id` 相同。任何一側有缺口就不計該圈，不插值。

每場先報告 orbit mean error、MAE、median absolute error、RMSE 與 closer-orbit count。M0 與 Ridge 由該場 orbit MAE 較低者勝出；25 場等權計票。全部 orbit pooled 指標只作輔助。局部 POD 變化可接近零，因此不使用逐圈 MAPE。

## 圖的 POD 顯示

POD 逐分鐘半長軸含明顯軌道週期振盪。下降圖沿用 Phase 1 `swarm_a_phase_orbit_mean_v2` 的 complete-orbit 定義，每圈只畫一個 phase-weighted mean；不使用任意 rolling window。整場以窗口開始前最後一個完整 orbit 為共同零點。

POD 圖不繼承 density pairing 的 block。只有 POD orbit 本身不連續或 `chunk_id` 改變才斷黑線；M0 與 Ridge 仍依 P6.4 block 處理 density 缺口。

Density 圖對真實缺口的兩端做線性內差，以同色實線連續顯示，不另外標示缺口。這是圖面處理，不寫回 SQLite，也不參與積分或評分。

逐圈線同時提供磁暴 score 的 POD orbit means。圖使用相對事件起點的曲線；每場 score 使用相鄰兩圈的局部差計算 orbit MAE，不重複累積前面各圈的誤差。`B_eff` 不重新擬合。

## 主張界線

- P6.4 是既有結果的 descriptive comparison，不是新模型。
- P6.1 `B_eff` 由同一三年 L2/POD 資料擬合。
- M0 與 Ridge density 都是 orbit-phase average，P6.1 使用逐分鐘 L2 density。
- Ridge 特徵由相同 25 場選出，沒有新事件獨立外測。
- 所有下降曲線仍使用 POD 半長軸計算積分核，不是自由軌道 propagation。
