# Swarm-A Orbital Decay Research

The research goal is to study how geomagnetic storms affect Swarm-A orbital
decay. XYZ orbit prediction is a later validation tool, not the main research
question. Phase 2 and its 12-year Phase 2R replication are complete and
frozen. Their reproducible 1-minute datasets and descriptive peak QC are
documented in `research_workspace/phases/phase2/reports/phase_2_final_report.md` and
`research_workspace/phases/phase2r/reports/phase_2r_final_report.md`. Treat both
checkpoint chains as read-only; new research needs a separate phase and
output. Do not revise either chain without Anby's explicit request. Do not add
machine learning or connect atmospheric drag until the phase plan requires it.

Phase 1 is the three-year working branch; Phase 1R is its 2014–2026 twelve-year
working branch. Keep their SQLite, reports, and figures in separate phase
directories. Neither candidate decay-rate database is a calibrated release.

Phase 3's three-year density-response analysis is complete. Its final record is
`research_workspace/phases/phase3/reports/phase_3_final_report.md`; its per-event $R_k$
calibration is final and must not be relabeled as provisional. Treat the Phase
3 result as read-only; any extension needs a separate phase and output.

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

Markdown is an operating document, not an essay. Lead with the decision,
status, constraint, or result. Use short paragraphs and compact bullets; remove
transition phrases and repeated context. Prefer one small ASCII flow, tree, or
`{field, ...}` shape when it makes a relationship clearer. Do not add decorative
icons, emoji, prose summaries of tables, or a second explanation of a diagram.
Historical reports keep only date, result, evidence, decision, and unresolved
work. A reader should be able to scan any section without reading every line.

Before creating, editing, or reviewing lineage Markdown under
`research_workspace/`, read and apply
`research_workspace/docs/data_lineage/RULES.md`; check every affected
step's action, Input, Output, and example against that format before finishing.

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

Treat raw SQLite tables as immutable source records. A calculation reads raw
tables and writes a separate derived table keyed by the original `time_us`;
it must not update or delete raw observations.
