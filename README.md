# Swarm-A Orbit Project

This project builds a Swarm-A orbit propagator. The current model is two-body
gravity only.

## Layout

- `satellite_orbit/data_swarm_download.py`: Swarm-A file download.
- `satellite_orbit/data_orbit.py`: orbit-data loading.
- `satellite_orbit/data_space_weather.py`: space-weather loading and time alignment.
- `satellite_orbit/calc_forces.py`: gravity and orbital state derivative.
- `satellite_orbit/calc_integrator.py`: RK4 state propagation.
- `satellite_orbit/calc_orbital_response.py`: semi-major axis and orbit-decay signals.
- `data/`: source orbit files. They remain unchanged.

## Orbit-data convention

- Coordinate frame: EME2000
- Time system: UTC
- Position: km
- Velocity: km/s

The active source is Swarm-A precise orbit data.

## Model limits

The two-body model is useful for testing the integrator, not for predicting the
real Swarm-A orbit over long durations. J2 and atmospheric drag must be implemented
before making that claim.
