# Phase 1 Glossary

## Raw record

One immutable observation written from a local source file. Raw records are never updated by a calculation.

## Source file

One POD ZIP recorded in `source_files`. Its parsed SP3 metadata is derived provenance, not raw history.

## State

One POD time snapshot:
`{time, frame, position_m, velocity_m_s}`.

## Chunk

One P1.4 sequence of usable states with the same product stream, SP3 frame, cadence, and continuous time.
`chunk_id` is not a maneuver classification.

## 10-minute orbit bin

One UTC `[end - 600 s, end)` aggregate from exactly one chunk. It stores the mean semi-major axis,
POD count, and maximum POD gap.

## Contiguous run

One consecutive 600-second subset inside a chunk. Decay smoothing uses runs, so a chunk can contain
more than one run if a 10-minute orbit bin is missing.

## Decay row

One interior contiguous-run row with smoothed semi-major axis, derivative, and decay rate. It excludes
the Savitzky-Golay window edges.

## Analysis row

One decay row plus causal SYM-H, Ap, F10.7, and F10.7A features. Density and AE are not Phase 1 core features.

## Working audit

An audit of the current SQLite database. It may pass before a fresh raw-file rebuild has been executed.

## Rebuild provenance

P1.7 manifest 的 `rebuild_status`。它說明現行 database 是 fresh rebuild 還是 verified cache reuse；
它不表示不同資料值、不同研究版本或第二個 release。
