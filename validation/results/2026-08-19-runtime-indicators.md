# L1.19 and L1.20, measured on this repository for the first time

**Status:** first execution-backed reading of the two runtime indicators against the analyzer's own package.
**Analyzer commit:** `9d9c7fd`. **Interpreter:** the package's own `.venv`.

## Bottom line

L1.19 reads **82.8%, Not Healthy**: 2,694 of 3,254 decision branches are exercised by tests, so 560 are not. Every panel this instrument has produced carried L1.19 as `n/a`, because every run passed `--no-exec`. The number was available and nobody had asked for it.

L1.20 reads **5/5, Healthy**: five randomized-order runs of the suite passed cleanly.

| indicator | before | now |
|---|---|---|
| L1.19 decision-space coverage | n/a on every run ever made | 82.8%, Not Healthy |
| L1.20 test determinism | n/a on every run ever made | 5/5, Healthy |

## What the 560 unreached branches are

Concentrated in the language tracers. Measured the same day: rust_trace 42% line coverage, csharp_trace 48%, race_harness 53%, coverage_prove 53%, c_trace 55%, java_trace 57%, go_trace 62%, cli 64%. Those modules drive external toolchains, and their untested paths are the report-parsing and refusal arms.

Every toolchain they need is present on this machine — cargo, node, go, java, dotnet and ruby all resolve — so the gap is unwritten tests rather than an unrunnable harness.

## What this does not show

A single machine and a single interpreter. L1.19 is a share of branches the suite reached, not a statement that the reached ones are correctly asserted. L1.20 at 5/5 bounds order-dependence over five runs and is not a proof of determinism; the details line says so.

`--no-exec` remains the default for the dogfood gate, because running the target's suite five times is not something a pre-commit hook should do. That is why the figure had never been taken, and it is why it has to be taken deliberately.
