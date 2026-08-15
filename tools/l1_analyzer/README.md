# l1_analyzer

The reference implementation of the twenty Layer 1 quantitative indicators (L1.1 through L1.20), plus the additive refinements and the prove loops. It reads a repository and prints a panel: a grade, the finitely-testable share, each indicator's value and band, and (opt-in) generated proofs for the gaps it finds.

This is the canonical instrument. The pre-registered study designs are validated against its output. A separate, validated-equivalent Rust redistribution for portability lives at `../slop-audit-rs/`.

## Run it

```
uv run slop-audit-l1 <repo>                      # the full panel, text
uv run slop-audit-l1 <repo> --format json        # machine-readable
uv run slop-audit-l1 <repo> --no-exec            # static only, skip the runtime indicators
uv run slop-audit-l1 <repo> --report ./out       # write <slug>.md and <slug>.html cards
```

Tests run with the dev extra: `uv run --extra dev pytest`.

## What it measures

- **L1.1 through L1.8** are `git log` ratios (doc-only, code-only, mixed commits, doc-line ratio, delete/add, net-negative, high-delete, test-to-production). Language-agnostic.
- **L1.9 through L1.11** are config-presence checks (pre-commit hooks, CI/CD, containerization).
- **L1.12 through L1.17** are source metrics via tree-sitter (dead code, duplication, secrets, type-escape density, trailing whitespace, god-file concentration), across `--lang {c, csharp, go, java, javascript, python, ruby, rust, typescript}` or `auto`.
- **L1.18** mutable-state ratio and **L1.18b** the state-bounds classifier: the finite-testability meter. This sets the grade (see below).
- **L1.19** decision-space coverage and **L1.20** test determinism: the two runtime indicators. They execute the target's own suite.
- **Additive checks** reported alongside: `path_cover`, `thread_surface`, `absolute_paths` (hardcoded machine-specific paths), and, when the prove loops run, `coverage_proofs` and `interleaving_robustness`.

## The grade

Verifiability first, by a published rule (`report.py`): any promiscuous state that drives a decision makes the code provably-not-exhaustively-testable, so the verdict is CANNOT and the grade is **F**. State the analyzer could not decide is **silence**, reported beside the grade and never inside it, because a state we did not read is not evidence about the audited code; above a silence floor of 50% no grade is issued at all, so hiding state from the analyzer buys no letter rather than a good one. D is the COARSE verdict: a reaching partition that is finite and countable, but unordered and wider than a published bound. Boundary values cover a large ordered domain with a handful of tests and cover a large unordered one with none, which is why cardinality alone was never the test. No bound is configured at present (`report.UNORDERED_CLASS_BOUND` is `None`) because the measured distribution does not support one; see `candidate-methods/silence-index-for-finite-testability.md`. When every piece of state is finitely testable and coverable the verdict is CAN, and the grade is A/B/C by hygiene (god-files and type-escapes weigh most). The finitely-testable percentage is a detail, not the tier: a 94%-clean codebase with one promiscuous decision-driver still grades F, because one such driver breaks exhaustive verification.

## Directory-insensitive by design

The two runtime indicators (L1.19, L1.20) run the target's suite under the **target's own runtime**, not whatever launched the analyzer, so the result depends only on the repository:

| Language | Coverage (L1.19) | Determinism (L1.20) | Runtime it resolves |
|---|---|---|---|
| Python | coverage.py branch | pytest-randomly | the repo's `.venv` (auto-detected) |
| Rust | cargo-llvm-cov region | libtest thread order | rustup + `rust-toolchain.toml` |
| Go | `go test -cover` (statement) | `go test -shuffle` | `go.mod` toolchain |
| Ruby | SimpleCov branch (when wired) | rspec / minitest `--seed` | rbenv / asdf / jenv shim |
| JS / TS | c8 (V8 branch) | vitest / jest seed | nvm `.nvmrc` (sourced) |
| Java | JaCoCo branch (when configured) | surefire random order | `./mvnw` + JDK |
| C# | coverlet cobertura branch | `dotnet test` x5 | `global.json` SDK |
| C | (no standard runner) | (no standard randomizer) | honest n/a |

Pass `--python PATH` to force the interpreter (for example a 3.11 target audited from a 3.12+ analyzer). Every measured result **names the runtime that ran it**, and when a toolchain, plugin, or dependency is missing the tool returns n/a with the exact remedy ("needs c8 for coverage", "needs pytest-randomly", "no branches instrumented") rather than a fabricated number.

## Prove loops (opt-in, CLI-only)

These generate and run code, so they are explicit and need `ANTHROPIC_API_KEY`:

- `--prove` locates concurrency hazards and generates a test that reproduces the race (concurrency proofs → `interleaving_robustness`).
- `--prove-coverage-repo` locates uncovered decision branches (L1.19's own gaps) and generates one test per gap, runs it under the target's runtime, and keeps it only if it fails on its own assertion (a proven divergence). Missing-test generation exists for **Rust and Python**; the flag dispatches by language. `--coverage-repair-rounds N` caps the compiler/setup-error repair loop; `--prove-max` caps gaps per module.

slop-audit proves the gap; it never writes into your test file. Adopting a surviving proof is your choice.

## Key flags

| Flag | Effect |
|---|---|
| `--lang` | Primary language (default `auto`). |
| `--python PATH` | Interpreter for the L1.19/L1.20 harness; defaults to auto-detecting the target's venv. |
| `--no-exec` | Skip the runtime indicators (static panel only). |
| `--format {text,json}` | Output format. |
| `--report [DIR]` | Write the Markdown and HTML cards. |
| `--gate` | Pass/fail mode for a pre-commit hook (god-files + finite-testability). |
| `--no-state-bounds` | Emit exactly the frozen L1.18 set (used by pre-registered runs). |
| `--prove` / `--prove-coverage-repo` / `--prove-coverage MODULE` | The prove loops (need `ANTHROPIC_API_KEY`). |
| `--timeout N` | Seconds per test-suite execution. |
