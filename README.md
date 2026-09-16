# Swarm-A Orbit Project

This project builds a Swarm-A orbit propagator. The current model uses two-body
gravity and J2.

## Layout

- `satellite_orbit/down_swarm_pod.py`: get Swarm-A POD files from ESA.
- `satellite_orbit/load_swarm_pod.py`: read a local Swarm-A POD ZIP file.
- `satellite_orbit/calc_coordinates.py`: change states between GCRF and ITRF.
- `satellite_orbit/calc_time.py`: change GPS time to UTC.
- `satellite_orbit/calc_forces.py`: gravity and orbital state derivative.
- `satellite_orbit/calc_integrator.py`: RK4 state propagation.
- `satellite_orbit/calc_position_error.py`: compare prediction with official POD.
- `satellite_orbit/calc_orbital_response.py`: semi-major axis and orbit-decay signals.
- `data/`: source orbit files. They remain unchanged.

## Orbit-data convention

- Main coordinate frame: GCRF
- POD source frame: ITRF
- Time system: UTC
- Position: km
- Velocity: km/s

The active source is Swarm-A precise orbit data.

Swarm-A POD points must be changed from ITRF to GCRF before propagation.

Coordinate changes use Astropy and IERS Earth orientation data. Install the
packages in `requirements.txt` before running the project.

## Model limits

The current model is useful for short tests. It does not yet include atmospheric
drag or a full Earth gravity model, so it is not a complete long-term predictor.
