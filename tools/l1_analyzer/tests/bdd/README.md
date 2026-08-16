# Honest Audit Test Suite (L1.1-L1.20)

This directory contains the behavioural (Gherkin) specification and executable tests for the Slop Audit Layer 1 indicators.

The suite is written in Gherkin so the expected behaviour of each indicator is readable by auditors, assessors, and AI agents without reading the implementation scripts.

## Every step runs the real analyzer

The step definitions build a real fixture (a temp file, a real git repository, real stub binaries on `PATH`) and call the real `l1_analyzer` on it, then assert its real output. There is no in-memory simulation, no substring ladder, and no reimplementation of an indicator's formula inside the test. A step that cannot import the analyzer fails loudly at collection time. A suite that stays green without the system under test is a lie, so this suite cannot be green without it.

Where a scenario carried a fabricated number in units the analyzer does not use (for example a dead-code density where the analyzer reports a finding count), the scenario states the real units, and the reconciliation is noted in a comment in the `.feature` file. Two L1.18 scenarios once carried `@xfail` tags because wiring them to real code surfaced genuine gaps. Both are resolved: the analyzer's own source is self-clean again, and the IO-boundary exclusion was withdrawn on 2026-08-15 after it was measured to be undoable by analysis, so that scenario now asserts the withdrawal rather than a promise the instrument does not keep.

## Structure

- `features/` - one `.feature` file (or group file) per L1 family, using tables for git histories and code snippets.
- `step_defs/` - pytest-bdd steps. Each builds real fixtures and calls the real analyzer; state is threaded through a per-scenario `ctx` fixture, never module globals.

This suite sits under `tools/l1_analyzer/tests/` because it tests `l1_analyzer` and imports it. It was previously kept in `validation/`, next to the instrument-validation methodology, which put a test suite in a directory of prose and split the analyzer's tests across two roots. `validation/` now holds `protocol.md` alone.

## Running

This suite is part of the `l1_analyzer` test tree, so the ordinary command runs it along with everything else:

```bash
# from anywhere in the repository
uv run --project tools/l1_analyzer --extra dev pytest tools/l1_analyzer/tests -q

# or, from slop-audit/tools/l1_analyzer/
uv run --extra dev pytest -q
```

Both commands collect the same tests and report the same result. To run only the Gherkin scenarios, point pytest at `tools/l1_analyzer/tests/bdd`.

An earlier version of this file said "Do not run it from the repository root: that environment loads an unrelated pytest plugin that fails to import, which blocks collection." That was measured on 2026-08-16 and is false. Running from the repository root and running from `tools/l1_analyzer/` produced the identical result, and no plugin failed to import. The real defect was `bdd_features_base_dir = "tests/features"` in `../../pyproject.toml`: pytest-bdd resolves that setting against pytest's rootdir, and rootdir depends on where pytest is invoked, so the same `scenarios("../features/...")` call resolved to different places from different directories. The setting is now removed, and pytest-bdd resolves each feature path against its own step-definition module, which no working directory can change.

## Coverage goal

Every L1 indicator has at least one scenario per threshold band (Healthy / Not Healthy / Slop) plus adversarial and boundary cases (exactly on the threshold, zero, 100%, IO-boundary, bound literals). The complete corpus-scale suite lives in the Paper A replication package.
