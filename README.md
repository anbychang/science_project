# ISS Orbit Project

This project builds an ISS orbit propagator. The current model is two-body
gravity only.

## Layout

- `iss_orbit/data_orbit.py`: orbit-data loading and reboost exclusion.
- `iss_orbit/data_space_weather.py`: space-weather loading and time alignment.
- `iss_orbit/calc_forces.py`: gravity and orbital state derivative.
- `iss_orbit/calc_integrator.py`: RK4 state propagation.
- `iss_orbit/calc_orbital_response.py`: semi-major axis and orbit-decay signals.
- `data/`: source orbit files. They remain unchanged.

## Orbit-data convention

- Coordinate frame: EME2000
- Time system: UTC
- Position: km
- Velocity: km/s

`load_iss_oem` reads the source data. `remove_reboost_periods` returns a
separate subset that excludes a chosen window around every reboost.

## Model limits

The two-body model is useful for testing the integrator, not for predicting the
real ISS over long durations. J2 and atmospheric drag must be implemented
before making that claim.
