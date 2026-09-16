# Swarm-A Orbit Project

This project builds a Swarm-A orbit propagator. The current model is two-body
gravity only.

## Layout

- `satellite_orbit/download_swarm_pod.py`: get Swarm-A POD files from ESA.
- `satellite_orbit/load_swarm_pod.py`: read a local Swarm-A POD ZIP file.
- `satellite_orbit/calculate_forces.py`: gravity and orbital state derivative.
- `satellite_orbit/calculate_integrator.py`: RK4 state propagation.
- `satellite_orbit/calculate_orbital_response.py`: semi-major axis and orbit-decay signals.
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
