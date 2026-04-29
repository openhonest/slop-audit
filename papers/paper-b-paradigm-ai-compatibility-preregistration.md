# Paper B Pre-Registration

**Working title.** Paradigm-AI Compatibility: Grading Programming Paradigms by Their Alignment with AI Code Generation.

**Author.** Adam Z. Wasserman.

**Pre-registration date.** 2026-04-12.

**Amended.** 2026-04-15. The amendment (a) adds a no-paradigm control condition (P0) alongside the original P1–P5 and (b) expands the language scope from Python-only to the four languages used by Paper A (Python, TypeScript, Java, C#). Both changes were filed before any data collection began. Full amendment rationale in `paper-b-amendment-justification.md`.

---

## 1. What this paper tests

AI coding assistants generate code using token prediction. Different programming paradigms produce code with different structural properties: some paradigms produce functions whose behavior is locally deterministic; others produce methods whose behavior depends on runtime state, inheritance chains, and execution order. This paper measures whether these structural differences produce measurable differences in AI code generation outcomes.

The paper does NOT assert that AI has specific limitations (e.g., "AI cannot simulate runtime state"). It MEASURES whether paradigm properties correlate with AI performance across six dimensions. The structural properties of each paradigm and the AI's performance on each dimension are both empirical findings, not premises.

If all paradigms produce similar AI performance across all dimensions, paradigm choice does not matter for AI-assisted development. If some paradigms consistently outperform others, the data identifies which paradigm properties drive the difference.

## 2. Design

**Multi-paradigm measurement study.** Same tasks, six paradigm conditions (P0 control plus P1–P5), three AI models, four languages, six measurement dimensions. No paradigm is pre-designated as "expected winner." The scorecard is an empirical result.

### 2.1 Task set

25 business-logic tasks of varying complexity, drawn from common enterprise operations. Each task is specified in natural language with explicit input/output contracts and edge cases. The specification is paradigm-neutral: it describes WHAT the code should do, not HOW it should be structured.

Tasks are organized in five categories (5 tasks each):

| Category | Example tasks |
|---|---|
| **Data validation** | Email validation, phone number normalization, address parsing, credit card Luhn check, password strength scoring |
| **Access control** | Role-based permission check, subscription-tier gating, rate-limit evaluation, IP allowlist matching, multi-tenant scope enforcement |
| **Business rules** | Tax calculation by jurisdiction, shipping cost computation, discount application with stacking rules, order status state machine, invoice generation |
| **Data transformation** | CSV-to-JSON conversion, nested object flattening, date range overlap detection, currency conversion with rounding, pagination with cursor encoding |
| **Error handling** | Retry with exponential backoff, circuit breaker state management, graceful degradation with fallback, input sanitization pipeline, structured error response formatting |

### 2.2 The six paradigm conditions

For each task, the AI is prompted to implement the specification under each of six paradigm conditions. The paradigm instruction is the only variable. The specification text is identical across conditions.

| # | Paradigm | Prompt instruction (summary) | Structural property being tested |
|---|---|---|---|
| **P0** | **No architecture specified (control)** | Specification plus output-hygiene footer; paradigm section omitted entirely | Model's natural/default shape, unprompted |
| P1 | **Pure functions with dispatch tables** | No classes, no mutable state, dispatch tables for branching, all inputs as parameters, all outputs as return values | Maximum context locality, maximum signature determinism |
| P2 | **Dataclasses + standalone functions** | Use dataclasses/TypedDicts for data, standalone functions for behavior, no methods on data, no inheritance | High context locality, separated data from behavior |
| P3 | **Class-based OOP without inheritance** | Use classes with methods, instance variables for state, but no inheritance hierarchies, composition only | Moderate context locality, mutable state present but contained |
| P4 | **Class-based OOP with inheritance** | Use classes with methods, instance variables, inheritance hierarchies where appropriate, polymorphic dispatch | Low context locality, runtime-dependent behavior |
| P5 | **Deep inheritance with framework patterns** | Use abstract base classes, template method pattern, mixin inheritance, framework lifecycle hooks | Minimum context locality, maximum runtime dependence |

P1 through P5 form a gradient from maximum to minimum structural locality. P0 is the no-instruction baseline: it reveals the model's natural shape before any paradigm prompt nudges it. Comparisons along the gradient (P1 vs P5) test whether paradigm choice affects outcomes; comparisons with P0 (e.g., P0 vs P3) test whether paradigm instructions move the model away from its default at all.

### 2.3 For each task, the following artifacts are prepared BEFORE any AI generation

1. **A natural-language specification** describing the task, inputs, outputs, edge cases. Paradigm-neutral AND language-neutral.
2. **Six paradigm prompts** (P0 through P5), each instructing the AI to implement the specification in the specified style (or giving no paradigm instruction in the case of P0).
3. **A comprehensive test suite** covering the full specification including edge cases and boundary values. Written BEFORE any code generation. The Gherkin feature files are language-agnostic and shared across all four languages; step definitions and reference implementations are ported per language. The same behavioural tests are used for all six paradigm conditions.

### 2.4 AI models

| Model | Access method |
|---|---|
| Claude (Anthropic) | API |
| GPT-4 (OpenAI) | API |
| Gemini (Google) | API |

If additional models become available before the experiment runs, they may be added. No model will be removed after the pre-registration is timestamped.

### 2.5 Target languages

All tasks are implemented in four languages: **Python**, **TypeScript**, **Java**, and **C#**. These are the same four languages used by Paper A, so Paper A's validated L1.18 analyzers apply to all generated code in Paper B without modification.

Python, TypeScript, and C# each support the full paradigm span from P1 (pure functions) through P5 (deep inheritance with framework patterns) natively. Java is comparatively class-heavy but permits every paradigm through static utility classes, records, interface default methods, and abstract base classes. The language set deliberately includes one paradigm-restricted language (Java) alongside three paradigm-flexible ones to let the analysis surface any language × paradigm interaction effects.

### 2.6 Total generation runs

25 tasks × 6 paradigms × 4 languages × 3 models = **1,800 generation runs** (first-generation dimension §3.1). Convergence-speed and self-verification dimensions each add a comparable run count. Generation-consistency (§3.3) adds up to 7,200 runs (10 tasks × 6 paradigms × 4 languages × 3 models × 10 repeats); if budget constraints force a reduction, repeat counts will be scaled uniformly rather than preferentially by paradigm or language.

## 3. Six measurement dimensions

Each dimension is computed from the generated code and its test results. No dimension requires subjective judgment. All are mechanical and reproducible.

### 3.1 First-generation test pass rate

Run the pre-written test suite against the AI's first-generation output. Record: tests passed / total tests. No iteration, no human editing.

**What it measures:** how often does the paradigm produce working code on the first attempt?

### 3.2 Convergence speed

If the first generation does not pass all tests, iterate: send failing test names and error messages back to the model, ask for a fix, run tests again. Repeat up to 5 iterations. Record: iteration number at which all tests pass, or "did not converge."

**What it measures:** when the AI's output is wrong, how quickly can the AI fix it in this paradigm?

### 3.3 Generation consistency

For a subset of 10 tasks, generate each task 10 times in each paradigm (at temperature > 0). Measure pairwise structural similarity between the 10 outputs using AST-level diff (normalized edit distance on the abstract syntax tree).

**What it measures:** does the paradigm produce consistent code, or does the AI generate structurally different solutions each time? High consistency suggests the paradigm has a natural "canonical form" that the AI converges to. Low consistency suggests the paradigm has many valid designs and the AI picks arbitrarily.

### 3.4 Self-verification accuracy

After the final generation, send the code back to the model: "Review this code for correctness. List any bugs you find." Record bugs identified. Cross-reference against actual test failures. Compute: true positive rate (real bugs found / actual bugs), false positive rate (non-bugs flagged / total flags).

**What it measures:** can the AI verify its own output in this paradigm? If the AI can find its own bugs, the paradigm's structure is transparent to AI reasoning. If it cannot, the paradigm's structure hides information the AI cannot recover.

### 3.5 Human reviewer verification time

A human reviewer reads the final generated code and records the time to either confirm correctness or identify the first bug. Timed per task per paradigm.

**What it measures:** is the paradigm's structure transparent to human reasoning? This complements 3.4 (AI verification) with the human analog.

### 3.6 L1.18 mutable state ratio of generated code

Run the Paper A L1.18 script on each generated output. Record the mutable state ratio.

**What it measures:** did the paradigm prompt actually control the structural property Paper A identifies as the testability driver? This connects Paper B to Paper A directly. If P1 (pure functions) produces code with L1.18 near 0% and P5 (deep inheritance) produces code with L1.18 above 50%, the paradigm prompt effectively controls the testability property. If the AI ignores the paradigm instruction and produces similar L1.18 regardless of prompt, the paradigm control is not effective.

## 4. Pre-registered predictions

### 4.1 The gradient prediction

The primary prediction: AI performance will degrade monotonically along the paradigm gradient from P1 (most self-contained) to P5 (most context-dependent). Specifically, within each language:

| Dimension | Predicted ordering (best to worst) |
|---|---|
| First-generation pass rate | P1 > P2 > P3 > P4 > P5 |
| Convergence speed | P1 > P2 > P3 > P4 > P5 |
| Generation consistency | P1 > P2 > P3 > P4 > P5 |
| Self-verification accuracy | P1 > P2 > P3 > P4 > P5 |
| Human reviewer speed | P1 > P2 > P3 > P4 > P5 |
| L1.18 (inverted: lower is better) | P1 < P2 < P3 < P4 < P5 |

If the ordering holds across all six dimensions and all three models in at least three of the four languages, the finding is: paradigm-AI compatibility is a gradient driven by structural locality, and it is consistent across models and across paradigm-flexible languages.

### 4.1a The baseline (P0) prediction

The P0 (no-paradigm-specified) condition's placement on the gradient is itself a prediction:

- On the L1.18 dimension, P0 is expected to fall between P3 and P4 across all four languages. The model's default shape is expected to reflect the class-based idioms dominant in training data.
- On first-generation pass rate, P0 is expected to fall at or slightly above P3 for class-natural tasks (e.g., shopping cart, LRU cache, event bus) and at or slightly above P2 for function-natural tasks (e.g., tax calculation, password strength, semver parsing), reflecting a mild task-sensitive default.
- If P0 matches or outperforms P1 on every dimension, the paradigm instructions are adding nothing and the experiment has a null finding on paradigm instruction efficacy even if P1-P5 differ from each other.

### 4.1b The cross-language prediction

The P1-P5 gradient is expected to be present in all four languages but compressed in Java relative to Python, TypeScript, and C#. Specifically, the P1-P5 gap on first-generation pass rate in Java is expected to be **at least 10 percentage points narrower** than the same gap in Python. This reflects Java's comparatively class-heavy idiomatic range. If Java exhibits a gradient of the same magnitude as Python, the paradigm effect is stronger than training-data language norms; if Java shows no gradient at all, the paradigm effect depends on language paradigm flexibility and does not generalise uniformly.

### 4.2 Specific threshold predictions

Thresholds apply to the primary confirmatory test: Python × P1-P5 × three models pooled. Results from P0 and from Java/TypeScript/C# are reported as planned secondary analyses against the same thresholds.

| Prediction | Value |
|---|---|
| P1 mean first-generation pass rate (Python) | > 65% |
| P5 mean first-generation pass rate (Python) | < 40% |
| P1-P5 gap on first-generation pass rate (Python) | > 25 percentage points |
| P1 mean L1.18 (Python) | < 10% |
| P5 mean L1.18 (Python) | > 45% |
| P1 "did not converge" rate (Python) | < 15% |
| P5 "did not converge" rate (Python) | > 35% |
| P0 mean L1.18 (Python) | between 25% and 55% (expected default is class-shaped) |
| Java P1-P5 gap on first-generation pass rate | > 15 percentage points (compressed relative to Python) |

### 4.3 Cross-model consistency

The gradient ordering (P1 > P2 > P3 > P4 > P5) will be the same across all three models on the first-generation pass rate dimension. If the ordering differs across models, the finding is model-specific rather than paradigm-driven.

## 5. Falsification criteria

1. **The gradient hypothesis** is falsified if the first-generation pass rate does NOT decrease monotonically from P1 to P5 across at least two of the three models. A non-monotonic result (e.g., P3 scores higher than P2) would mean the gradient model is wrong and the relationship between paradigm structure and AI performance is non-linear or non-existent.

2. **The paradigm-matters hypothesis** is falsified if the difference in mean first-generation pass rate between the best-performing paradigm and the worst-performing paradigm is less than **15 percentage points** (across all models pooled). A gap smaller than 15 points would mean paradigm choice has a detectable but not practically significant effect on AI code generation.

3. **The cross-model consistency hypothesis** is falsified if the best-performing paradigm differs across models. If P1 is best on Claude but P3 is best on GPT-4, the finding is model-specific and no general paradigm recommendation can be made.

4. **The L1.18 control hypothesis** is falsified if the mean L1.18 of P1-generated code exceeds **20%**. This would mean the pure-function paradigm prompt does not effectively control mutable state in the generated output, undermining the connection between paradigm instruction and testability.

5. **The self-verification hypothesis** is falsified if self-verification true-positive rate does NOT vary across paradigms by more than **10 percentage points**. If the AI finds bugs equally well (or poorly) regardless of paradigm, then paradigm structure does not affect AI self-reasoning ability.

## 6. What this paper explicitly does NOT test

- Whether enterprise code is systematically untestable (Paper A)
- Whether the Slop Audit instrument is reproducible (Paper C)
- Whether converting to Honest Code reduces rework (Paper D)
- Whether developers prefer one paradigm (this paper measures AI performance, not developer preference)
- Whether the measured differences are caused by the structural properties we describe or by some other property correlated with the paradigm gradient (the paper measures correlation, not causation; causal claims would require a different design)

## 7. Sequence of events

1. **2026-04-12:** predictions and falsification criteria locked in this document
2. **After timestamp:** 25 task specifications written, reviewed, finalized
3. **After specifications:** 25 test suites written (spec-before-code)
4. **After test suites:** 5 paradigm prompts per task finalized (125 prompts total)
5. **After prompts:** experiment runs (375 generation runs + 150 generation-consistency runs)
6. **After data collected:** six dimensions computed; analysis performed per pre-registered predictions
7. **Manuscript drafted**
8. **Submitted:** target venue EMSE or ICSE; arXiv preprint posted simultaneously

## 8. What this paper does NOT protect against

- **Prompt sensitivity.** The paradigm instructions may influence the model beyond the intended structural difference. Mitigation: the five prompts are published in full; others can critique and test alternative phrasings.
- **Task selection bias.** The 25 tasks are chosen to represent common enterprise operations. A different task set might produce different results. Mitigation: the task set is published in full.
- **Four-language-specificity.** The experiment spans Python, TypeScript, Java, and C# — the four dominant enterprise application languages shared with Paper A. A language outside this set (Haskell, Rust, Go) might produce different paradigm gradients. Mitigation: acknowledged as a limitation; follow-up studies in additional languages encouraged.
- **Model evolution.** Results are specific to model versions at time of experiment. Mitigation: model version strings published.
- **Training data confound.** If pure-function Python is over-represented in model training data relative to deep-inheritance Python, the AI might perform better on P1 simply because it has seen more examples, not because the paradigm is structurally better aligned. Mitigation: this confound cannot be controlled without access to training data, which is proprietary. It is disclosed as a limitation. The generation-consistency dimension (3.3) provides partial evidence: if the AI converges on a single canonical form for P1 but produces diverse forms for P5, training density is at least one factor.

## 9. Timestamp anchor

**Timestamp anchor:** [TO ADD: Zenodo DOI or OSF registration ID once minted].

---

## Appendix A: Pre-registration checklist

- [x] Write the 25 task specifications (5 per category) — complete 2026-04-15
- [x] Write the 25 paradigm-neutral Gherkin test suites — complete 2026-04-15, 564 scenarios total
- [x] Write 6 paradigm prompts (P0 control + P1-P5) — complete 2026-04-15
- [x] Write Python reference implementations for all 25 tasks (sanity check)
- [ ] Port step definitions and reference implementations to TypeScript
- [ ] Port step definitions and reference implementations to Java
- [ ] Port step definitions and reference implementations to C#
- [ ] Validate L1.18 analyzers work against small generated samples in all 4 languages
- [ ] Set up API access for Claude, GPT-4, and Gemini
- [ ] Write the experiment runner script (25 × 6 × 4 × 3 grid)
- [ ] Write the generation-consistency analysis script (AST diff, per-language)
- [ ] Write the self-verification prompt and scoring script
- [x] Register amendment on OSF (2026-04-15)
- [ ] Run the experiment (~1,800 first-gen runs + up to 7,200 consistency runs)
- [ ] Human reviewer timing pass
- [ ] Draft the manuscript
- [ ] Submit to EMSE or ICSE; post arXiv preprint

## Appendix B: Relationship to the publication sequence

| Paper | What it tests | Connection to this paper |
|---|---|---|
| **Paper A** | Is enterprise code systematically untestable? | Paper A identifies L1.18 (mutable state) as the testability driver. This paper measures whether L1.18 varies by paradigm in AI-generated code and whether it correlates with AI performance. |
| **Paper B (this paper)** | Which paradigm properties correlate with AI code generation performance? | |
| **Paper C** | Is the Slop Audit reproducible by independent assessors? | Independent of this paper |
| **Paper D** | Does converting to Honest Code reduce rework? | Paper D measures the practical consequence of adopting the paradigm this paper identifies as most AI-aligned |
