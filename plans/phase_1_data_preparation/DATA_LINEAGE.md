# Swarm-A 資料血緣圖

這張圖只描述資料如何流動：網路來源 -> 本機檔案 -> 解析與新增欄位 -> SQLite -> 衍生分析資料。

實線是現行已完成的資料流；虛線是 P1.5 到 P1.7 已定義、尚未實作的資料流。

```mermaid
flowchart LR
    classDef network fill:#e8f1ff,stroke:#4c78a8,color:#111
    classDef local fill:#fff4d6,stroke:#b07d15,color:#111
    classDef transform fill:#e8f6ea,stroke:#39814a,color:#111
    classDef table fill:#fffbe6,stroke:#8d7414,color:#111
    classDef planned fill:#f2f2f2,stroke:#777,color:#333,stroke-dasharray: 5 5
    classDef hold fill:#fde8e8,stroke:#b44,color:#111

    subgraph pod_lane[Swarm-A POD：主軌道資料]
        direction LR
        POD_WEB[ESA Swarm-A<br/>precise-orbit product]:::network
        POD_FILE[data/swarm_a_pod/*.ZIP<br/>SP3 in ZIP]:::local
        POD_PARSE[讀取 SP3 epoch / P / V<br/>GPS time -> UTC<br/>km -> m；dm/s -> m/s]:::transform
        POD_STATE[{state<br/>time, frame=ITRF,<br/>position_m, velocity_m_s}]:::transform
        POD_RAW[(swarm_a_states<br/>+ time_us, weather_time_us, source_id)]:::table
        POD_WEB --> POD_FILE --> POD_PARSE --> POD_STATE --> POD_RAW
    end

    subgraph weather_lane[F10.7 / F10.7A / Ap：太空天氣]
        direction LR
        WEATHER_WEB[CelesTrak<br/>SW-All.csv]:::network
        WEATHER_FILE[data/space_weather/SW-All.csv]:::local
        WEATHER_EXPAND[每日列展開成 8 個<br/>official 3-hour block<br/>加入前日 F10.7 與 Ap history]:::transform
        WEATHER_RAW[(space_weather<br/>+ f107_sfu, f107a_sfu,<br/>f107a_last81_sfu, ap_*, f107_data_type)]:::table
        WEATHER_WEB --> WEATHER_FILE --> WEATHER_EXPAND --> WEATHER_RAW
    end

    subgraph geomag_lane[SYM-H / AE：地磁指標]
        direction LR
        GEO_WEB[WDC Kyoto HAPI<br/>minute SYM-H / AE]:::network
        GEO_FILE[data/geomagnetic/*.csv]:::local
        GEO_PARSE[跳過 header 與 99999<br/>ISO UTC -> time_us]:::transform
        GEO_RAW[(geomagnetic<br/>+ sym_h_nt, ae_nt,<br/>sym_h_version, ae_version)]:::table
        GEO_WEB --> GEO_FILE --> GEO_PARSE --> GEO_RAW
    end

    subgraph density_lane[DNSAACC density：目前獨立保存]
        direction LR
        DENS_FILE[data/swarm_density_acc/*.ZIP<br/>CDF in ZIP]:::local
        DENS_PARSE[讀取 time / density / altitude / lat / lon / LST<br/>過濾無效 density]:::transform
        DENS_RAW[(swarm_a_density<br/>+ density_kg_m3, altitude_m,<br/>latitude_deg, longitude_deg, local_solar_time_h)]:::table
        HOLD[停止：尚未定義<br/>主分析的物理角色與時間對齊]:::hold
        DENS_FILE --> DENS_PARSE --> DENS_RAW --> HOLD
    end

    subgraph derived_lane[POD 衍生資料：現行已完成]
        direction LR
        GCRF[ITRF state -> GCRF state<br/>保留 time / position_m / velocity_m_s]:::transform
        ELEMENT[(swarm_a_orbital_elements<br/>+ semi_major_axis_m<br/>或 rejection_reason)]:::table
        QUALITY[檢查 finite state、bound energy、時間與 gap<br/>切開不可連續區間]:::transform
        POD_QC[(swarm_a_pod_quality<br/>+ is_usable, rejection_reason, interval_id)]:::table
        POD_RAW --> GCRF --> ELEMENT --> QUALITY --> POD_QC
    end

    subgraph analysis_lane[10 分鐘分析資料：規格已定，尚未實作]
        direction LR
        ORBIT10[只使用 is_usable=1 且同 interval 的 POD<br/>orbit-average / short-period treatment / smoothing]:::planned
        ORBIT_TABLE[(planned: swarm_a_orbit_10min<br/>+ semi_major_axis_smooth_m, da_dt_smooth_m_s,<br/>decay_rate_smooth_m_day, pod_count, max_pod_gap_s)]:::planned
        JOIN[以每個 10-minute time_us 對齊<br/>SYM-H、Ap、前日 F10.7、前日 trailing F10.7A<br/>缺值保留 orbit row，寫 NULL 與 flag]:::planned
        FINAL[(planned: swarm_a_analysis_10min<br/>軌道衰減欄位 + sym_h_nt + ap_now + F10.7/F10.7A<br/>+ source times + quality_flags)]:::planned
        POD_QC -.-> ORBIT10 -.-> ORBIT_TABLE -.-> JOIN -.-> FINAL
        WEATHER_RAW -.-> JOIN
        GEO_RAW -.-> JOIN
    end
```

