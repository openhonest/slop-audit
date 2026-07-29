# slop-audit-l1

Reference Python implementation of all 20 Slop Audit Layer 1 indicators.

**Key property:** can be run against codebases in *any* language.

- Git-history indicators (L1.1–L1.8): completely language-agnostic.
- Config indicators (L1.9–L1.11): file presence.
- Source-analysis indicators (L1.12+): use tree-sitter + `LANG_CFG` dispatch tables (same architecture as the research L1.18 / bound-literal analyzers). Wired up for Python, Java, JavaScript, TypeScript, C#, Ruby, Go, Rust, and C. Each language has verified tree-sitter node types and a regression test in `tests/test_basic.py`. Ruby mutable state is detected via `@instance`/`$global` variables and Go via method-receiver field access, not just `self.`/`this.`.
- Runtime indicators L1.19 (decision-space coverage) and L1.20 (test determinism): implemented in `pytest_trace.py` for Python. L1.19 runs the suite under `coverage run --branch` and reports `covered_branches / num_branches`; L1.20 runs the suite five times in randomized order (pytest-randomly) and counts clean passes. The pytest-under-coverage recipe and the process-group timeout kill mirror the sibling Slop Audit instrument [Umbra](https://slopaudit.org/umbra.html). These two indicators execute the target repo's test suite (untrusted code, run in an isolated process group with a hard timeout); pass `--no-exec` to skip execution, in which case L1.19 falls back to a static decision-point count with coverage explicitly marked not-measured. Non-Python targets report `n/a` for now. Never a guessed number.

## Usage

```bash
cd slop-audit/tools/l1_analyzer
uv sync

# Against any repo (auto language detection for source indicators)
uv run l1-analyzer /path/to/some/repo --indicators all

# Force language
uv run l1-analyzer /path/to/some/rust/codebase --lang rust --indicators 18

# Specific date range + json output
uv run l1-analyzer /path/to/repo --since 2025-01-01 --format json
```

## Integration with the Honest Audit Test Suite

The Gherkin behavioural specs in `../../validation/tests/` can use this package (when on PYTHONPATH) to get real numbers instead of pure simulation.

## Extending to more languages

Add the tree-sitter parser and an entry in `LANG_CFG` in `l1_analyzer/indicators.py`. The `_count_mutable_refs` (and future walks for L1.15, L1.19, etc.) already dispatch on the cfg.

See the full production analyzers and 300+ Gherkin scenarios in the Paper A replication package for the complete, battle-tested versions.
