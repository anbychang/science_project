# Swarm-A Orbit Project

This project builds a Swarm-A orbit propagator. The current model uses two-body
gravity and J2.

## Layout

- `satellite_orbit/down_swarm_pod.py`: get Swarm-A POD files from ESA.
- `satellite_orbit/down_space_weather.py`: get raw F10.7 and Ap data.
- `satellite_orbit/load_swarm_pod.py`: read a local Swarm-A POD ZIP file.
- `satellite_orbit/load_space_weather.py`: add F10.7 and Ap to one state.
- `satellite_orbit/prep_month_states.py`: make one readable prepared monthly CSV.
- `satellite_orbit/load_prepared_states.py`: read prepared CSV into states.
- `satellite_orbit/calc_coordinates.py`: change states between GCRF and ITRF.
- `satellite_orbit/calc_atmosphere.py`: calculate NRLMSIS 2.0 mass density.
- `satellite_orbit/calc_time.py`: change GPS time to UTC.
- `satellite_orbit/calc_forces.py`: gravity and orbital state derivative.
- `satellite_orbit/calc_integrator.py`: RK4 state propagation.
- `satellite_orbit/calc_position_error.py`: compare prediction with official POD.
- `satellite_orbit/calc_orbital_response.py`: semi-major axis and orbit-decay signals.
- `data/`: source orbit files. They remain unchanged.

## Orbit-state convention

```text
state = {
    time,
    frame,
    position_m: [x, y, z],
    velocity_m_s: [vx, vy, vz],

    # Added when the atmosphere is needed:
    f107_sfu,
    f107a_sfu,
    ap_values,
    f107_data_type,
    density_kg_m3,
}
```

- Functions pass one `state` instead of separate time, position, and velocity.
- One orbit series is `[state, state, ...]`.
- Derived time series still use one row for each time.
- Main coordinate frame: GCRF
- POD source frame: ITRF
- Time system: UTC
- Position: m
- Velocity: m/s
- Acceleration: m/s^2
- Angle: rad
- Density: kg/m^3

The raw POD uses km and dm/s. The loader changes these values to SI once.
NRLMSIS requires degrees and km, so only its adapter changes rad to degrees and
`altitude_m` to km. F10.7 and Ap keep the units required by NRLMSIS.

`SW-All.csv` is downloaded only when the local file is missing. Space-weather
rows are prepared once for each day and then reused from memory.

The active source is Swarm-A precise orbit data.

Swarm-A POD points must be changed from ITRF to GCRF before propagation.

Coordinate changes use Astropy and IERS Earth orientation data. Install the
packages in `requirements.txt` before running the project.

## Run one POD error test

Use the default start point and predict 10 minutes:

```powershell
python main_pod_error.py
```

Choose another GPS start time and prediction length:

```powershell
python main_pod_error.py --day 2025-01-01 --start 01:30:00 --minutes 60
```

Prepare one UTC month for repeated experiments:

```powershell
python -m satellite_orbit.prep_month_states 2025-01
```

The output is `data/prepared_swarm_a_2025-01.csv`. It is generated data and is
not committed to Git.

## Model limits

The current model is useful for short tests. It can calculate NRLMSIS 2.0 mass
density, but atmospheric drag is not connected to RK4 yet. It also does not use
a full Earth gravity model, so it is not a complete long-term predictor.
