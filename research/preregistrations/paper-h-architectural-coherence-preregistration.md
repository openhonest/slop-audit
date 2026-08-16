# Paper H Pre-Registration

**Working title.** Architectural Coherence Under Multi-Turn AI Development: A Paradigm × Generation-Mode Factorial on a Bounded Enterprise Application.

**Author.** Adam Z. Wasserman.

**Pre-registration date.** 2026-04-13.

---

## 1. What this paper tests

Papers A, B, and D measure single-shot properties of AI-assisted code. Paper A measures static structural metrics on snapshots. Paper B measures first-generation correctness on isolated tasks. Paper D measures rework longitudinally on specific codebases. None of them test whether AI can maintain architectural coherence across a multi-module application as it grows over many development turns.

This gap matters because enterprises do not use AI to generate one function at a time. They use AI to add module N+1 to an app that already has N modules, and to modify module K without breaking module J. The question is whether paradigm choice affects the AI's ability to sustain consistency at that scale.

This paper tests two hypotheses:

1. **The paradigm-coherence hypothesis.** AI maintains architectural coherence more effectively in pure-functional paradigms (P1, P2) than in class-based paradigms (P3, P4, P5) when building a multi-module application. The mechanism: pure functions make dependencies explicit (imports, parameters, dispatch table entries); class hierarchies hide dependencies in inheritance, runtime polymorphism, and shared mutable state.

2. **The generation-mode × paradigm interaction.** The paradigm effect on coherence is larger in incremental generation (one module at a time, across 15+ turns) than in one-shot generation (the entire application built in a single prompt). The mechanism: one-shot generation lets the AI plan the architecture upfront; incremental generation requires the AI to reason over existing code at each step, and that reasoning is easier when the code is structurally local.

If both hypotheses are confirmed, the finding is: **paradigm choice compounds over development time**. The single-task paradigm advantage reported in Paper B is a floor, not a ceiling.

### 1.1 What is novel about this study

1. **First multi-turn architectural coherence study of AI code generation.** Prior AI code-generation studies (HumanEval, MBPP, SWE-Bench) test one-shot correctness on isolated tasks or single-file bug fixes. None measure coherence across a growing multi-module codebase over many turns.

2. **Factorial design (5 paradigms × 2 generation modes).** The interaction effect is the primary contribution. A main-effect-only study would answer "does paradigm matter?" A factorial answers "does paradigm matter differently when the AI has to maintain state across turns?"

3. **Coherence metrics defined operationally.** Pattern consistency, regression rate, coupling drift, and duplicate abstraction count are all computed mechanically from the generated codebase and its test suite. No subjective judgment.

4. **Direct test of the Honest Code scalability claim.** Honest Code advocates pure functions and dispatch tables partly because they are claimed to compose better at scale. This paper operationalizes that claim and tests it.

## 2. Design

**Target application.** A bounded multi-tenant expense-tracking service implemented in Python. The application is specified in full before any generation occurs, in a specification document that is paradigm-neutral (Appendix A). Approximate size: 12 modules, 40--60 public functions/methods, 100+ test cases across all modules.

**Why this application.** It is small enough to be feasible (an expert human can implement it in 1-2 days) and large enough to exhibit architectural drift (12 modules with cross-cutting concerns like auth, validation, audit logging, and multi-tenant scoping). It covers common enterprise patterns: CRUD, validation, authorization, reporting, audit trails.

### 2.1 Factorial cells

**5 paradigms × 2 generation modes = 10 cells.** Each cell is run with 3 AI models = **30 total applications generated**.

| Paradigm | P1 pure functions | P2 dataclasses | P3 classes no inherit | P4 classes w/ inherit | P5 deep inherit |
|---|---|---|---|---|---|
| **One-shot** | | | | | |
| **Incremental** | | | | | |

**One-shot cells.** The AI receives the complete specification in a single prompt, along with the paradigm instruction, and generates all 12 modules in one response. No iteration based on test results.

**Incremental cells.** The AI receives the specification in 15 sequential turns. Turn 1 generates module 1. Turn 2 receives module 1's code and the next module's sub-specification, generates module 2. Turns 12-15 are modification turns: the AI is asked to add a feature that cuts across previously-generated modules. At each turn, the AI has access to all previously-generated code but not to the tests.

The incremental sequence is identical across paradigms: the same 15-turn prompt sequence is used for P1 through P5. Only the paradigm instruction (injected in each turn) varies.

### 2.2 AI models

Same three as Paper B: Claude, GPT-4, Gemini. API access. Identical parameters (temperature 0, same max-token budget).

### 2.3 Pre-written artifacts

All of these are written, reviewed, and frozen BEFORE any generation occurs:

1. **Application specification** (paradigm-neutral, ~3000 words, describes the 12 modules, their interfaces, data types, and cross-cutting requirements).
2. **Behavioral test suite** (~100 tests, Gherkin + pytest-bdd, same format as Paper B). Tests are purely behavioral. They do not inspect structure.
3. **Incremental turn sequence** (15 sub-prompts that decompose the specification into a sensible build order).
4. **Coherence metric scripts** (Section 3).

## 3. Coherence metrics

Computed mechanically from each generated application. No subjective judgment.

### 3.1 First-pass pass rate

Percentage of the 100 behavioral tests that pass on the final generated codebase (no human edits). Applies to both one-shot and incremental cells.

### 3.2 Pattern consistency (intra-codebase)

For each pair of modules (i, j), compute a pattern-similarity score using AST fingerprinting: the set of structural patterns used (dispatch table vs if/elif, dataclass vs class, function vs method, composition vs inheritance). Higher intra-codebase similarity means the AI used consistent patterns across modules. Low similarity means the AI chose differently each time.

Reported as the mean pairwise similarity across all module pairs, 0.0 (all different) to 1.0 (all identical).

### 3.3 Regression rate (incremental only)

For each modification turn (turns 12--15 of incremental cells), record the number of previously-passing tests that fail after the modification. Lower is better. A value of 0 means the AI modified the codebase without breaking existing behavior; a high value means cross-module edits routinely broke distant tests.

Not computable in one-shot cells (no turns to regress on).

### 3.4 Coupling drift

Build the import graph (or for P3--P5, the class-dependency graph) at each turn (incremental) or on the final codebase (one-shot). Compute the average number of edges per node. Report the slope of this metric over turns for incremental cells and the terminal value for one-shot cells. Rising slope means the codebase becomes more coupled as it grows.

### 3.5 Duplicate abstraction count

For each paradigm, identify functions or classes that are semantically near-identical to functions or classes already present in the codebase. Operationally: cosine similarity of function-level AST embeddings above 0.85 between two functions with different names. Each duplicate increments the count. Lower is better.

### 3.6 L1.18 drift

Run the Paper A L1.18 script on the codebase after each turn (incremental) and on the final codebase (one-shot). Report the trajectory of the mutable state ratio over turns and the terminal value. Paradigm compliance check: P1 should stay near 0%; P5 should stay near or above the Paper A median for its language.

### 3.7 Efficiency (exploratory, not preregistered)

Token consumption and wall time per generation call. Reported as total input tokens, total output tokens, total wall seconds per cell. Clearly labeled exploratory.

## 4. Pre-registered predictions

### 4.1 Main effects

| Metric | Predicted ordering |
|---|---|
| Pass rate | P1 > P2 > P3 > P4 > P5 |
| Pattern consistency | P1 > P2 > P3 > P4 > P5 |
| Regression rate (incremental) | P1 < P2 < P3 < P4 < P5 |
| Coupling drift | P1 < P2 < P3 < P4 < P5 |
| Duplicate abstractions | P1 < P2 < P3 < P4 < P5 |

### 4.2 Interaction prediction (central)

The P1--P5 gap on pass rate and regression rate is **at least twice as large** in the incremental mode as in the one-shot mode. Operationally: if (mean_P5_pass_rate - mean_P1_pass_rate) in one-shot is X percentage points, the same gap in incremental is >= 2X percentage points.

### 4.3 Specific thresholds

| Prediction | Value |
|---|---|
| P1 incremental pass rate | > 80% |
| P5 incremental pass rate | < 50% |
| P1--P5 incremental pass rate gap | > 30 percentage points |
| P1 coupling drift slope (incremental) | < 0.2 edges/turn |
| P5 coupling drift slope (incremental) | > 0.5 edges/turn |
| P5 duplicate abstraction count | > 3 per application |
| P1 duplicate abstraction count | < 1 per application (on average) |

## 5. Falsification criteria

1. **The paradigm-coherence hypothesis** is falsified if pass rate does not decrease monotonically from P1 to P5 across at least two of the three models, in either one-shot or incremental.

2. **The interaction hypothesis** is falsified if the P1--P5 gap in incremental is not substantially larger than in one-shot (operationally: less than 1.5x the one-shot gap). A null interaction means paradigm matters for single tasks but not for multi-module coherence, which would be a surprising and important finding.

3. **The L1.18 compliance check** is falsified if P1-generated applications have mean L1.18 > 15% or P5-generated applications have mean L1.18 < 40%. This would mean the paradigm instructions are not effective at scale.

## 6. What this paper explicitly does NOT test

- The quality of AI-human collaboration (this paper measures AI-only generation)
- The effect of tooling (IDE, linters, type checkers) on coherence
- The effect of test-driven development on AI coherence (the AI does not see tests during generation)
- The interaction with human code review (reviewed code is out of scope)
- Long-term maintenance over months (15 turns is not a long time horizon; it is a feasibility bound)

## 7. Sequence of events

1. **2026-04-13:** Predictions and falsification criteria locked in this document.
2. **After timestamp:** Application specification written and reviewed.
3. **After spec:** Behavioral test suite written.
4. **After tests:** Incremental turn sequence drafted.
5. **After turns:** Coherence metric scripts written and validated on a handcrafted reference implementation.
6. **After scripts:** 30 applications generated (5 paradigms x 2 modes x 3 models).
7. **After generation:** Metrics computed, analysis performed per pre-registered predictions.
8. **Manuscript drafted.**
9. **Submitted:** target venue ICSE or FSE; arXiv preprint posted simultaneously.

## 8. Known limitations

- **Single application.** The study uses one expense-tracking app. Results may not generalize to apps with different domain properties (real-time systems, data pipelines, numeric computation).
- **Python only.** The paradigm gradient may behave differently in languages with stronger OOP enforcement (Java) or stronger functional support (OCaml, Haskell).
- **15 turns is not months.** True long-term architectural drift over months of development is out of scope. This study establishes a first-point-of-measurement, not a final characterization.
- **AI-only, no human in the loop.** Real development involves review, refactoring, and correction by humans. This study isolates the AI's contribution.
- **Training data confound.** Same as Paper B: we cannot control for paradigm distribution in training data.

## 9. Relationship to other papers

| Paper | What it tests | Connection |
|---|---|---|
| **Paper A** | Is enterprise code systematically untestable (single-shot structural)? | This paper asks whether the paradigm Paper A identifies as more testable also scales better under multi-turn AI development. |
| **Paper B** | Which paradigm properties correlate with single-task AI generation? | This paper is the multi-module, multi-turn extension of Paper B. |
| **Paper D** | Does converting to Honest Code reduce rework (human-driven, longitudinal)? | Paper D is human-driven; this paper is AI-driven. Together they bracket the paradigm-rework relationship. |
| **Paper G** | Do all 19 indicators cluster into coherent profiles? | This paper's coherence metrics could become new indicators in Paper G's framework. |

## 10. Timestamp anchor

**Timestamp anchor:** [TO ADD: Zenodo DOI or OSF registration ID once minted].

---

## Appendix A: Sketch of the target application

A multi-tenant expense-tracking service with:

1. **Authentication** — password-based user login, session tokens.
2. **Tenants** — each user belongs to exactly one tenant. Data is scoped to the user's tenant.
3. **Users within tenants** — roles: `admin`, `manager`, `employee`.
4. **Expense categories** — CRUD, tenant-scoped.
5. **Expenses** — CRUD, with amount, category, date, description, receipt URL.
6. **Budgets** — per-category monthly limits.
7. **Approval workflow** — expenses over a threshold require manager approval.
8. **Reporting** — aggregate expenses by category, by user, by month.
9. **Audit log** — append-only record of all state-changing operations.
10. **Permissions** — admin sees all; manager sees direct reports + own; employee sees own.
11. **Validation** — amounts positive, dates not in the future, categories exist, receipts are valid URLs when provided.
12. **Persistence** — in-memory store with a clear interface that the other modules consume (not an actual database, to keep the study focused on architecture rather than infrastructure).

The full specification (~3000 words) will be written after this preregistration is timestamped, following the same paradigm-neutral style as Paper B's task specifications.

## Appendix B: Pre-registration checklist

- [ ] Write the application specification (~3000 words, paradigm-neutral)
- [ ] Write the behavioral test suite (~100 tests)
- [ ] Write the 15-turn incremental sequence
- [ ] Write the coherence metric scripts (consistency, regression, coupling, duplicate detection, L1.18 trajectory)
- [ ] Validate the scripts on a handcrafted reference implementation
- [ ] Set up API access and runner for Claude, GPT-4, Gemini
- [ ] Mint Zenodo DOI for this pre-registration
- [ ] Run the experiment (30 applications)
- [ ] Compute all metrics
- [ ] Draft the manuscript
- [ ] Submit to ICSE or FSE; post arXiv preprint
