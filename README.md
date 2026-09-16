# Swarm-A Orbit Project

This project builds a Swarm-A orbit propagator. The current model is two-body
gravity only.

## Layout

- `satellite_orbit/down_swarm_pod.py`: get Swarm-A POD files from ESA.
- `satellite_orbit/load_swarm_pod.py`: read a local Swarm-A POD ZIP file.
- `satellite_orbit/calc_forces.py`: gravity and orbital state derivative.
- `satellite_orbit/calc_integrator.py`: RK4 state propagation.
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

## Model limits

The two-body model is useful for testing the integrator, not for predicting the
real Swarm-A orbit over long durations. J2 and atmospheric drag must be implemented
before making that claim.
