# Slop Audit Methodology

A **slop audit** is an open standard for measuring whether a codebase can be exhaustively verified, not just tested. Code coverage tells you how many lines a test executed. It cannot tell you whether verifying the code's behaviour is even possible. The Slop Audit measures that directly, through finite-testability indicators (mutable-state ratio, decision-space coverage, test determinism) and an eighteen-dimension compliance mapping. It is not a detector of AI-generated text and it is not a slang term.

The methodology is documents, and it is runnable by an assessor from those documents alone. Layer 1 is also a tool: twenty indicators over git history, source and the target's own test run, across nine languages, in a Python reference implementation and a single-file portable binary. [Jump to running it](#run-it-on-a-repo).

> ### ▶ Try it on your own code
> Paste any public GitHub repo at **[try.slopaudit.org](https://try.slopaudit.org)** and get its finite-testability scorecard in seconds. Nothing is installed, and your code is never executed.
>
> **What not running your tests costs the report.** Two of the twenty indicators need the suite to run, and this one does not run it. L1.19 reports how many decision points exist, not what fraction your tests reach. L1.20, test determinism, reports nothing at all. Everything else on the scorecard is static and complete.
>
> So the grade answers whether the code **can** be exhaustively verified, which is a property of how it is built. It does not answer whether it **is** verified, which is a property of your test suite. A repository with no tests at all can grade A here, and that is not a bug in the grade: the two questions are separate, and the first one is the one nobody else measures. Run the tool locally, without `--no-exec`, to answer the second.

**About.** The Slop Audit is an open, reproducible measurement instrument that scores an existing production codebase across eighteen dimensions mapped to compliance frameworks (SOC 2, NIST SP 800-53, OSFI B-13, OWASP ASVS, ISO/IEC 25010), calibrated to detect the failure modes of AI-generated code at deployment scale. Four-layer judgment model, runnable by a trained assessor from these documents alone. It is one of the three open standards governed by the Open Honest Foundation, alongside the Honest Framework and MÉTRON. It is not a social-media account, a band, or a slang term. By **Adam Zachary Wasserman** ([ORCID](https://orcid.org/0009-0002-8865-6583), [OSF](https://osf.io/user/8t64r)), founder of the [Open Honest Foundation](https://openhonest.org).

**Companion standard.** [Honest Framework](https://github.com/openhonest/honest-framework) is the other half of the same idea, pointed the other way. The Slop Audit measures whether a codebase can be exhaustively verified; the Honest Framework is the architectural discipline that makes the answer yes by construction: no Big State, pure-function dispatch tables in place of classes, no hidden state. The connection is not thematic, it is mechanical. L1.18 measures the mutable state the framework's rules forbid, and L1.19 measures the decision space those rules keep finite. A codebase built to the framework scores well on the audit because the audit measures what the framework eliminates. Read the audit first if you have inherited a codebase and need to know what you have; read the framework first if you are writing one and want to avoid needing the audit.

**Companion instrument.** [Umbra](https://github.com/openhonest/umbra) applies the same discipline at the level of a single module and its tests: it reports what a test suite is structurally unable to see and proves each gap with a real failing test, across six languages. Where the Slop Audit scores a whole codebase, Umbra is the module-level tool you point at the code an assistant just wrote.

## Run it on a repo

Layer 1 is mechanical, so it ships as a tool. Three ways to run it, in the order most auditors will want them.

### 1. The portable binary

One self-contained file. No interpreter, no install, no network, and no shipped grammar libraries: the nine tree-sitter grammars are linked into the binary. This is what to carry to a client site or a machine you are not allowed to install on.

```bash
git clone https://github.com/openhonest/slop-audit && cd slop-audit/tools/slop-audit-rs
cargo build --release
./target/release/slop-audit-rs /path/to/repo
```

The primary language is detected from the repo's file counts. Override it with `--lang`, which takes `python`, `rust`, `c`, `java`, `typescript`, `csharp`, `javascript`, `ruby` or `go`. Add `--tsv` for one tab-separated row per indicator.

Tagged releases run [`.github/workflows/release.yml`](.github/workflows/release.yml), which cross-builds a static Linux binary, a Windows binary and a macOS binary, and fails the release if the Linux and macOS panels disagree by one byte. The v0.1.0 release predates that workflow and carries no binaries, so build from source until the next tag.

### 2. Docker

For a machine with neither Python nor Rust. Mount the repo read-only; the panel comes back on stdout.

```bash
cd slop-audit                       # the repo root, where the Dockerfile is
docker build -t slop-audit .
docker run --rm -v "/path/to/repo:/repo:ro" slop-audit
```

### 3. The Python reference

The canonical instrument. It computes every indicator the portable binary does, plus the finite-testability analysis (L1.18, L1.18b), the runtime indicators (L1.19 coverage, L1.20 determinism), the additive thread-surface and path-cover checks, and the opt-in prove loops.

```bash
cd tools/l1_analyzer
uv sync --extra dev
uv run l1-analyzer /path/to/repo              # report card
uv run l1-analyzer /path/to/repo --no-exec    # skip running the target's test suite
uv run l1-analyzer /path/to/repo --format json
```

L1.19 and L1.20 run the target repo's own test suite under the target's own runtime, which the tool detects from the repo (`.venv`, rustup, `go.mod`, `global.json`, nvm, rbenv). Pass `--no-exec` to skip that half. Nothing else in Layer 1 executes the code under audit.

### What each one measures today

| | Portable binary | Python reference |
|---|---|---|
| L1.1 to L1.11 git history and config | yes | yes |
| L1.15, L1.16, L1.17 source density | yes | yes |
| L1.19 decision-point enumeration | yes | yes |
| L1.18, L1.18b finite testability | not yet | yes |
| L1.19 coverage, L1.20 determinism (runtime) | not yet | yes |
| L1.12, L1.13, L1.14 | not yet | only when `vulture`, `jscpd` and `gitleaks` are installed, otherwise `n/a` |
| Additive: absolute paths | yes | yes |
| Additive: thread surface, path cover, schedule silence | not yet | yes |

The portable binary is a certified-equivalent redistribution, not a second opinion. Each ported indicator is validated equal to the Python reference on a real repository in each of the nine languages, and [`.github/workflows/parity.yml`](.github/workflows/parity.yml) fails the build if the two ever disagree. Where they differ in coverage, the Python instrument is canonical.

Requiring `vulture`, `jscpd` and `gitleaks` for three indicators is a defect, not a design. Those three are being reimplemented natively so that a complete panel needs nothing but the binary.

## What one run produces

The report card, on this repository:

```
# Slop Audit — slop-audit (python)

**Grade: A** — 100% of its state is finitely testable

This code definitely CAN be exhaustively tested.

None of the data this code keeps can grow without limit, so a fixed number of tests
can check every case. The Slop Audit worked out the fewest test runs that reach every
path: 930 runs cover them all.

- Finitely testable: 0
- Provably unbounded: 0
- Undetermined: 0
- test runs cover every path through the code, both sides of every yes-or-no: 930

## How it maps to your audit

| Check | Value | Band | Counts toward |
|---|---|---|---|
| L1.15 · type-escape density | 0.0/kloc | Clean | Dependency injection · 4.12 · NIST SA-11 · ISO/IEC 25010 (testability) |
| L1.17 · god-file concentration | 0.0% | Clean | Tech-debt management · 4.17 · NIST CM-8 / SA-15 · SOC 2 CC7.1 |
| L1.16 · trailing-whitespace density | 0.0% | Clean | SDLC with AI safeguards · 4.16 · NIST SA-3 / SA-8 · SOC 2 CC8.1 |
| L1.10 · CI/CD pipelines | 5 | Clean | CI/CD · 4.10 · NIST SA-11 / SA-15 / CM-3 · SOC 2 CC8.1 · SSDF PW.7 |
| L1.11 · containerization | present and parameterized | Clean | Containerization · 4.11 · NIST SP 800-190 |
| L1.9 · pre-commit hooks | present | Clean | CI/CD · 4.10 + SDLC safeguards · 4.16 · NIST SA-11 |

## Thread-safety surface — clean

No concurrency escape hatches found. Nothing overrides or bypasses the language's own
thread-safety guarantee.
```

Every row carries the compliance clause it feeds, because the point of a Layer 1 number is the evidence it becomes.

The portable binary prints the raw panel instead, one line per indicator, bands and all. The same repository:

```
primary language: python
L1.1      doc-only-commits         9.5          Not Healthy
L1.2      code-only-commits        57.1         Healthy
L1.3      mixed-commits            31.0         Healthy
L1.4      doc-line-ratio           24.2         Not Healthy  7051 doc / 29190 total lines added
L1.5      delete-add-ratio         11.0         Slop
L1.6      net-negative-commits     3.6          Slop
L1.7      high-delete-commits      17.9         Not Healthy
L1.8      test-to-prod-ratio       0.52         Healthy      5877 test / 11233 production LOC
L1.9      pre-commit hooks         present      Healthy
L1.10     CI/CD pipelines          5            Healthy
L1.11     containerization         present      Healthy
L1.15     type-escapes             0.0          Healthy      0 escapes in ~9kLOC
L1.16     trailing-whitespace      0.0          Healthy      0 lines with trailing ws
L1.17     god-files                0.0          Healthy      0/48 files >1k LOC, 0 >4k LOC
L1.19     decision-space           2017         n/a          2017 finite decision points across 37 files
abs-paths absolute-paths           0            Healthy      no hardcoded machine-specific absolute paths
```

### Five bands come back short of Healthy, and they stay

Two read Slop, three read Not Healthy, and all five are printed rather than exempted. A standard that scores everyone else and quietly excuses itself is not a standard, so every threshold here was applied to this repo on the same terms it applies to a client's.

**L1.5, L1.6 and L1.7 measure deletion, and this repository accumulates.** That is a true reading of the behaviour and a poor reading of the health, which is worth separating. The deletion indicators are calibrated against production enterprise codebases, where accumulated dead code is the sediment of unsupervised generation. This repository is mostly a methodology canon: prose that is written once, revised in place and rarely deleted, alongside two tool packages. A canon that deleted 15 percent of its own commits would not be healthier, it would be unstable. The indicator is measuring something real against the wrong baseline, which is exactly the kind of finding Layer 4 judgment exists to resolve and Layer 1 cannot. Naming that is more useful than hiding it, and it is a calibration note the validation program owes an answer to.

**L1.1 and L1.4 land just under the line in a repository that is three quarters prose,** which looks like a contradiction and is not. Both count documentation against a commit, and here the prose usually changes in the same commit as the code it describes. A mixed commit is neither doc-only nor a doc-line majority, so a repo that documents everything it does scores like one that documents nothing. That is a measurement artefact worth knowing about before it is read as a verdict.

What would be dishonest is moving the numbers. Writing commits shaped to shift a ratio is the failure this audit exists to detect, and no instrument, this one included, can tell that apart from the real thing. The readings change when the behaviour changes.

## Reading order

| # | File | Contents | Lines |
|---|---|---|---|
| 0 | [Frontmatter](00-frontmatter.md) | Title, status, confidentiality statement | ~14 |
| 1 | [Purpose and scope](01-purpose-and-scope.md) | What the audit produces, who runs it, scope of one audit | ~28 |
| 2 | [Four-layer model](02-four-layer-model.md) | Layer 1 through Layer 4 definitions, composition, why the model exists, Phase 0/Phase 1 boundary | ~135 |
| 3 | [Layer 1 indicators](03-layer1-indicators.md) | Twenty quantitative indicators (seventeen git-history + three finite-testability), reporting format, automation, limitations | ~314 |
| 4 | [Dimensions](dimensions/) | The 18 per-dimension entries (Layer 2 + Layer 3 + Layer 4 for each) | ~1,700 |
| 5 | [Conducting an audit](05-conducting-audit.md) | The 5-day operational walkthrough, prerequisites, common time-budget failures | ~90 |
| 6 | [Slop Report template](06-slop-report-template.md) | Report structure, SOC 2 deliverable extraction, length/tone guidance | ~214 |
| 7 | [Validation](07-validation.md) | Validation set, cross-rater test, "would the auditor agree" test | ~38 |
| 8 | [Training](08-training.md) | Curriculum tracks, certification levels, cross-rater calibration, recertification | ~182 |
| 9 | [TODO and attribution](09-todo-and-attribution.md) | Outstanding work items, source attribution, future extensions backlog | ~95 |

## Dimensions index

Each dimension is a self-contained file in `dimensions/`. An assessor can reference one dimension at a time during an audit.

| # | File | Dimension | Lifecycle category |
|---|---|---|---|
| — | [Quick reference](dimensions/00-quick-reference.md) | The one-row-per-dimension lookup table for mid-audit use | — |
| 4.1 | [01-entitlement.md](dimensions/01-entitlement.md) | Entitlement system | Security architecture |
| 4.2 | [02-authentication.md](dimensions/02-authentication.md) | Authentication | Security architecture |
| 4.3 | [03-inter-service-security.md](dimensions/03-inter-service-security.md) | Inter-service security | Security architecture |
| 4.4 | [04-multi-tenancy.md](dimensions/04-multi-tenancy.md) | Multi-tenancy | Data architecture |
| 4.5 | [05-audit-infrastructure.md](dimensions/05-audit-infrastructure.md) | Audit infrastructure | Compliance engineering |
| 4.6 | [06-rate-limiting.md](dimensions/06-rate-limiting.md) | Rate limiting | Operational security |
| 4.7 | [07-configuration-secrets.md](dimensions/07-configuration-secrets.md) | Configuration and secrets | Operational security |
| 4.8 | [08-caching.md](dimensions/08-caching.md) | Caching | Performance engineering |
| 4.9 | [09-notifications.md](dimensions/09-notifications.md) | Notifications | Operations |
| 4.10 | [10-cicd.md](dimensions/10-cicd.md) | CI/CD | DevOps |
| 4.11 | [11-containerization.md](dimensions/11-containerization.md) | Containerization | Infrastructure |
| 4.12 | [12-dependency-injection.md](dimensions/12-dependency-injection.md) | Dependency injection | Software architecture |
| 4.13 | [13-pattern-sophistication.md](dimensions/13-pattern-sophistication.md) | Pattern sophistication | Software architecture |
| 4.14 | [14-architectural-philosophy.md](dimensions/14-architectural-philosophy.md) | Architectural philosophy | Software architecture |
| 4.15 | [15-live-documentation.md](dimensions/15-live-documentation.md) | Live documentation | Governance |
| 4.16 | [16-sdlc-ai-safeguards.md](dimensions/16-sdlc-ai-safeguards.md) | SDLC with AI safeguards | Process engineering |
| 4.17 | [17-tech-debt-management.md](dimensions/17-tech-debt-management.md) | Tech debt management | Lifecycle management |
| 4.18 | [18-ux-from-code.md](dimensions/18-ux-from-code.md) | UX from code | Software development |

## Other methodology files

| File | Contents |
|---|---|
| [papers/peer-review-strategy.md](papers/peer-review-strategy.md) | Publication program, venue selection, framework extension cadence |
| [papers/paper-2-preregistration.md](papers/paper-2-preregistration.md) | Pre-registration for the independent instrument validation study |
| [validation/protocol.md](validation/protocol.md) | Validation protocol details |

## Tools

The methodology is stack-agnostic. A tool here demonstrates how to mechanise part of an audit; it is never a requirement to use that tool. The one exception is `l1_analyzer`, which is the canonical implementation of the Layer 1 indicators: where a number produced by any other implementation disagrees with it, it is the other implementation that is wrong.

| Tool | Purpose |
|---|---|
| [tools/l1_analyzer/](tools/l1_analyzer/) | **Canonical.** The Python implementation of L1.1 through L1.20, the additive checks (finite-testability classification, thread surface, path cover, absolute paths, schedule silence) and the opt-in prove loops, which generate a runnable failing test for an uncovered branch or a concurrency hazard. Git indicators are language-agnostic; source indicators use tree-sitter across nine languages; the runtime indicators execute the target's own suite under the target's own detected runtime. |
| [tools/slop-audit-rs/](tools/slop-audit-rs/) | The portable redistribution: one static binary per platform with the nine grammars linked in, no interpreter and no shipped `.so`. Ported indicator by indicator and validated equal to the canonical instrument on a repository in each language, with a CI job that fails on any disagreement. Cross-builds to macOS, Linux and Windows. |
| [tools/ui-audit/](tools/ui-audit/) | One example implementation for stacks that use the playground/enhance component pattern. Compares playground controls against the component library's enhance functions and reports dead controls, hidden features, and wiring mismatches. Maps to one aspect of dimension 4.18 (UX from code). |

## License

Apache License 2.0. See [LICENSE](LICENSE).
