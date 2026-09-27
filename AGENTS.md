# Swarm-A Orbital Decay Research

The research goal is to study how geomagnetic storms affect Swarm-A orbital
decay. XYZ orbit prediction is a later validation tool, not the main research
question. The active phase only prepares a reproducible 10-minute analysis
dataset. Do not add machine learning or connect atmospheric drag until the
phase plan requires it.

The existing support code has two-body gravity, J2, RK4 integration, and
NRLMSIS 2.0 density calculation. Atmospheric drag is not connected to the
propagator.

Keep code readable: separate physics, numerical methods, data I/O, and command
entry points; name physical quantities by meaning and unit; document model
assumptions rather than obvious syntax. Do not retain verification scripts in
the main package unless the user explicitly asks for them.

Use Ponytail-style engineering for every code change. The best code is code
that does not need to be written. First understand the task and trace the real
flow touched by the change, then choose the first path that works:

1. Does this need to exist, or is it speculative?
2. Does this project already have a helper, data shape, constant, or pattern?
3. Can the Python standard library do it?
4. Can the native platform or an existing installed dependency do it?
5. Can this be a small local edit or one line?
6. Only then add the minimum new code.

No unrequested abstraction, framework, dependency, wrapper, config layer, or
future-proofing. Prefer deletion over addition, boring over clever, and the
fewest files possible. If two small standard-library options fit, choose the
edge-case-correct one, not the flimsiest one.

For bug fixes, fix the root cause, not only the named symptom. Search the callers
of the function being changed and put the guard or correction in the shared path
when that is the smaller correct fix.

Do not simplify away trust-boundary validation, data-loss prevention, security,
accessibility, physics assumptions, calibration needs, or anything explicitly
requested. If a deliberate simplification has a real ceiling, mark it with a
short `ponytail:` comment naming the ceiling and the upgrade path. Non-trivial
logic should leave one small runnable check behind; trivial one-line changes do
not need new tests.

Use four-letter file prefixes to show purpose: `calc_` for math and physics,
`down_` for internet downloads, `prep_` for making prepared data files, and
`load_` for local file reading.

Use short, simple English in code comments. Use Chinese only when simple English
cannot explain the idea. Show data shapes with `[]` and `{}` when that is easier
to read than a full sentence.

Write project Markdown documents in Traditional Chinese. Use English there only
for proper technical terms, file names, database fields, function names, and
code. Keep code comments in English.

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
