# Honest Audit Test Suite (L1.1–L1.20)

This directory contains the behavioural (Gherkin) specification and executable tests for the Slop Audit Layer 1 indicators.

The suite is deliberately written in Gherkin so that the expected behaviour of each indicator is readable by auditors, assessors, and AI agents without reading the implementation scripts.

## Structure

- `features/` — one .feature file (or group file) per L1 family, using tables for git histories and code snippets.
- `step_defs/` — pytest-bdd steps. They simulate git histories in memory for L1.1-8 and call (or stub) the real L1 analyzer scripts for L1.12+.
- `fixtures/` — sample code and git fixtures for multi-language cases (Python, Rust, C, etc.).

## Running

The full production suite lives in the Paper A replication package (`adamzwasserman/openhonest-paper-a-finite-testability/tests/`).

To run a local copy here:

```bash
# from slop-audit/
PYTHONPATH=../../adamzwasserman/openhonest-paper-a-finite-testability uv run pytest validation/tests/ -q --gherkin-terminal-reporter
```

The steps are written to fall back to in-memory simulation when the paper package is not on PYTHONPATH, so the suite is self-documenting even if the analyzers are not present.

## Language-agnostic design

Per L1.18 (and the finite-testability group), all static analysis indicators (L1.12, L1.13, L1.15, L1.18, L1.19) use tree-sitter + LANG_CFG dispatch tables exactly so the same semantic property can be measured in any language. The Gherkin scenarios include examples in Python, Rust, C, etc.

## Coverage goal

Every L1 indicator has at least one scenario for each threshold band (Healthy / Not Healthy / Slop) plus adversarial and boundary cases (exactly on the threshold, zero, 100%, mixed language repos, IO-boundary exclusions, bound literals, etc.).

See the replication package for the complete 300+ scenario suite that was used to validate the 200-repo corpus in Paper A.
