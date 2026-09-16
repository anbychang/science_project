# Swarm-A Orbit Project

The active scope is a Swarm-A orbit propagator. The current implementation has
two-body gravity and RK4 integration. It does not yet include J2 or atmospheric
drag.

Keep code readable: separate physics, numerical methods, data I/O, and command
entry points; name physical quantities by meaning and unit; document model
assumptions rather than obvious syntax. Do not retain verification scripts in
the main package unless the user explicitly asks for them.

Use four-letter file prefixes to show purpose: `calc_` for math and physics,
`down_` for internet downloads, and `load_` for local file reading.

Use short, simple English in code comments. Use Chinese only when simple English
cannot explain the idea. Show data shapes with `[]` and `{}` when that is easier
to read than a full sentence.
