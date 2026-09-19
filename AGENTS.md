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

Every function must show its input and output in a short docstring. Prefer visual
shapes such as `Input: [state_1, state_2, ...]` and
`Output: {time, frame, position_m, velocity_m_s}` over long prose.

Use one orbit-state shape everywhere in the pipeline:
`{time, frame, position_m, velocity_m_s}`. Pass this single state between the
loader, coordinate changes, forces, RK4, and error calculation. One orbit series
is `[state, ...]`. Force functions, including two-body and J2, also receive the
whole state. Do not split time, position, and velocity into separate inputs.

A state is one time-point snapshot. Time-varying space weather and atmosphere
values may be added to it, such as `{f107_sfu, f107a_sfu, ap_values,
density_kg_m3}`. Fixed constants such as Earth gravity and satellite mass stay
outside the state.

Use SI units inside the project: m, m/s, m/s^2, s, rad, kg, m^2, and kg/m^3.
Convert source units once in the loader. Convert again only when an external
library requires another unit, and keep that conversion at the library call.
