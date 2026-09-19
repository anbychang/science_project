# Swarm-A Orbit Project

The active scope is a Swarm-A orbit propagator. The current implementation has
two-body gravity, J2, and RK4 integration. NRLMSIS 2.0 density calculation is
available, but atmospheric drag is not connected to the propagator yet.

Keep code readable: separate physics, numerical methods, data I/O, and command
entry points; name physical quantities by meaning and unit; document model
assumptions rather than obvious syntax. Do not retain verification scripts in
the main package unless the user explicitly asks for them.

Use four-letter file prefixes to show purpose: `calc_` for math and physics,
`down_` for internet downloads, and `load_` for local file reading.

Use short, simple English in code comments. Use Chinese only when simple English
cannot explain the idea. Show data shapes with `[]` and `{}` when that is easier
to read than a full sentence.

Store every time series in row form: one point is
`{time, named_value_1, ..., named_value_n}` and one series is `[point, ...]`.
Do not store time and values in separate arrays. RK4 may still use a temporary
`[x, y, z, vx, vy, vz]` vector during calculation.

Use SI units inside the project: m, m/s, m/s^2, s, rad, kg, m^2, and kg/m^3.
Convert source units once in the loader. Convert again only when an external
library requires another unit, and keep that conversion at the library call.
