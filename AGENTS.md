# ISS Orbit Project

The active scope is an ISS orbit propagator. The current implementation has
two-body gravity and RK4 integration. It does not yet include J2 or atmospheric
drag.

Keep code readable: separate physics, numerical methods, data I/O, and command
entry points; name physical quantities by meaning and unit; document model
assumptions rather than obvious syntax. Do not retain verification scripts in
the main package unless the user explicitly asks for them.
