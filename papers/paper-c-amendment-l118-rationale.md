# Paper C Pre-Registration Amendment — Rationale for L1.18 as an Audit Indicator

**Amendment date.** 2026-04-16.
**Original registration date.** 2026-04-10.
**Original document.** `paper-c-instrument-validation-preregistration.md`.
**Purpose.** To add explicit theoretical justification for why L1.18 (mutable state ratio) is a relevant audit indicator. The original preregistration (§1.1 item 3) describes what L1.18 measures and notes the absence of direct prior art, but does not state the underlying reason the measurement is relevant. This amendment supplies that reasoning.
**Data-collection status.** No data has been collected under Paper C at the time of this amendment. All predictions, falsification criteria, and study design elements in the original preregistration remain unchanged.

---

## 1. What this amendment adds

The original Paper C preregistration, §1.1 item 3, establishes that L1.18 is an original operationalization with no direct prior art. It leaves implicit the underlying question: *why is measuring mutable state ratio relevant to enterprise software quality auditing in the first place?*

This amendment makes the answer explicit. The reasoning is mathematical, not subjective. It is stated here so that reviewers evaluating Paper C's instrument validation have a clear basis on which to assess the indicator's theoretical grounding, separate from its operational reliability (which is what Paper C directly tests).

## 2. The mathematical claim

A function's behavior is determined by the values of the information it reads. For a function whose signature is `f(x₁, x₂, …, xₙ)` and whose body reads only `x₁ … xₙ`, the set of possible behaviors is fully characterized by the Cartesian product of the parameter domains:

    Behavior domain of f = D₁ × D₂ × … × Dₙ

If every `Dᵢ` is finite, the behavior domain is finite. Exhaustive behavioral verification — evaluating `f` over every element of its behavior domain and comparing against a specification — is possible in finite time, subject only to a budget linear in the product `|D₁| × … × |Dₙ|`.

A function whose body additionally reads external mutable state `S` (instance variables, class variables, module-level mutables, captured closures, heap references) has an effective signature:

    f(x₁, …, xₙ, S)

The behavior domain becomes:

    Behavior domain of f = D₁ × … × Dₙ × State(S)

where `State(S)` is the set of all values `S` can take across the history of program execution. In the general case, `State(S)` is unbounded: it can include histories of prior calls, accumulated data, heap addresses that vary across runs, timing-dependent values, open file handles, network connection states, and so on. Unbounded state makes `State(S)` infinite.

An infinite behavior domain cannot be exhaustively enumerated in finite time. Therefore, the behavior of a function that references unbounded external mutable state cannot be verified by exhaustive testing, regardless of the test budget.

This is a mathematical statement, not a subjective claim about engineering style. It is a direct consequence of the definition of "exhaustive testing" (evaluating every element of the behavior domain) and the elementary property of infinite sets (not enumerable in finite time).

The mathematical impossibility of exhaustive testing under unbounded mutable state is complemented by a cognitive limitation: humans systematically fail at the conditional logic required to reason about mutable-state transformations. The Wason Selection Task (Wason 1966), replicated across decades with fewer than 10% of participants solving it correctly on first attempt (Evans 2016), demonstrates that humans default to heuristic reasoning (Kahneman's System 1) rather than the formal logical reasoning (System 2) that mutable-state code demands. Mutable state provides "escape hatches from formal reasoning" (Wasserman 2025) — mutation replaces provable transformation with informal assertion, side effects replace explicit dependency tracking with implicit coupling, and procedural sequencing replaces function composition with unchecked state evolution. L1.18 therefore measures the fraction of code subject to both limitations simultaneously: mathematically unverifiable by testing AND cognitively unreliable for human reasoning.

## 3. Why this matters for an audit

An auditor assessing whether an enterprise codebase is adequately verified is asking: for what fraction of the code is "verified by testing" a mathematically coherent claim? The answer depends on the fraction of functions whose behavior domains are finite.

L1.18 operationalizes this fraction directly. A function with L1.18 contribution zero (references no external mutable state outside its parameter list) has a behavior domain determined by its parameters alone; it belongs to the finitely-testable fraction of the codebase. A function with L1.18 contribution one (references external mutable state) has a behavior domain that includes `State(S)`; in the general case, it belongs to the not-finitely-testable fraction.

Reported test coverage numbers (typically 70-90% line coverage in enterprise reports) conflate these two populations. Line coverage at 90% on a codebase where 60% of functions reference external mutable state means: 90% of lines were exercised by at least one test, but only 40% of functions have a behavior domain for which exhaustive testing is even theoretically possible. The reported coverage number overstates the degree of behavioral verification by a factor of at least `1 / (1 - L1.18)` in the worst case.

An audit indicator that measures L1.18 therefore tells the auditor what fraction of the codebase's reported test coverage is *verification in the finitely-testable sense* versus *sampling of a domain that cannot be exhaustively covered*. This distinction is the core of what the Open Honest audit produces and is the answer to the implicit question in Paper C's §1.1 item 3.

## 4. What this amendment does NOT claim

1. It does not claim that code with high L1.18 is buggy. Code with unbounded behavior domains can be correct; the claim is about the impossibility of exhaustive verification, not about defect density.

2. It does not claim that code with low L1.18 is automatically verified. A codebase with L1.18 = 0% but no tests remains unverified; L1.18 establishes only the *possibility* of exhaustive testing, not its execution.

3. It does not claim that all mutable state makes verification impossible. Functions that reference bounded external state (e.g., a small enumerated set of configuration flags) have finite behavior domains and are finitely testable. The claim concerns unbounded mutable state — heaps, histories, accumulated data, heap-allocated object identity — which is the overwhelmingly dominant form of mutable state in practice.

4. It does not claim that non-exhaustive testing is useless. Sampling-based testing is the established practice of the field and produces useful evidence of absence of defects. The claim is narrower: sampling is not *verification*, and the distinction is obscured by coverage metrics that report both as if they were the same.

5. It does not claim novelty for the underlying mathematical fact. The state-space explosion problem is well known in the model-checking literature (Clarke, Grumberg, Peled et al.). What is novel is the operationalization of the fraction of code affected by it into a single audit indicator computable at scale.

## 5. Relationship to prior literature

The mathematical claim in §2 is a direct consequence of the finite-state/infinite-state distinction familiar from:

- **Golomb 1961**, "A mathematical theory of discrete classification," in *Information Theory: Fourth London Symposium* (C. Cherry, ed.). The canonical early reference for combinatorial explosion as a general property of discrete systems whose state space grows faster than any polynomial budget can enumerate.
- **Model checking literature** (Clarke & Emerson 1981; Queille & Sifakis 1982). The specialization of Golomb's combinatorial-explosion observation to the verification of concurrent and reactive systems, where it acquired the specific name "state-space explosion."
- **Hoare logic** (Hoare 1969), which frames program verification in terms of pre- and post-conditions, implicitly over the full behavior domain.
- **Rice's theorem** (Rice 1953), which bounds what can be decided about program behavior in general.
- **Unkel & Lam 2008 (POPL)** — the closest prior work on field-level immutability in Java, cited in the original Paper C preregistration §1.1 item 3. They measured the fraction of fields that are stationary after initialization (44-59% in their corpus). L1.18 differs in that it measures functions (not fields) and operationalizes the result as an audit indicator.

The novelty of L1.18 is not in recognizing the mathematical fact that unbounded-state functions are not finitely testable. That is well-established — traceable at least to Golomb 1961 as a general property of discrete systems and specialized to program verification by the model-checking community in the 1980s. The novelty is in operationalizing "what fraction of a given codebase's functions fall into the not-finitely-testable population" as a single number computable from the repository alone, applying it across 200 enterprise codebases, and positioning it as a formal indicator in a compliance-mapped audit instrument.

## 6. Clarification: scope of the Wasserman 2026 assessment

The original Paper C preregistration (§2.1) states that Application A scored "18 of 18 dimensions satisfied" in Wasserman 2026. This refers to the original 18 Layer-4 dimensions (4.1 Entitlement through 4.18 UX from code) assessed in that preprint. The three finite-testability indicators — L1.18 (mutable state ratio), L1.19 (decision-space coverage), and L1.20 (test determinism) — were added to the instrument after Wasserman 2026 was published. Application A and Application B have not been formally assessed against L1.18, L1.19, or L1.20 by any prior study.

The predictions in Paper C §3.3 for L1.18/L1.19/L1.20 on Application A and Application B are therefore **first-time assessments**, not reproductions of prior scores. This is a feature of the study design: Paper C tests both reproduction (the original 18 dimensions, where the author's prior scores exist as a baseline) and extension (the 3 new indicators, where no prior assessment exists and the independent assessor's results constitute the first formal measurement).

The "18 of 18" claim in §2.1 is accurate as written; this clarification ensures reviewers do not interpret it as including L1.18-L1.20.

## 7. Correction: assessor candidate contact status

The original Paper C preregistration §2.3 states "all contacted, awaiting responses as of 2026-04-12" for the listed assessor candidates. This is incorrect. No assessor candidates have been contacted specifically for Paper C as of the date of this amendment. The individuals listed (Bradbury, Shehory, Feldt, Treude, Baltes, the audit partner, Beauchemin) were contacted in relation to the broader research program but were not asked to serve as Paper C assessors.

As of 2026-04-16, a potential co-investigator (Prof. Hafedh Mili, UQAM/LATECE) has expressed interest in the research program. If Prof. Mili joins Paper C as a co-investigator, assessor recruitment — including which candidates to approach and on what terms — will be jointly decided. The candidate list in §2.3 should be read as "candidates under consideration," not "candidates contacted."

## 8. Clarification: assessor access to the methodology author

The original Paper C preregistration §2.4-2.5 restricts assessor-author communication but does not specify a logging protocol. This amendment clarifies.

Assessors may contact the methodology author (or co-investigator, if applicable) during the audit. All communications are logged verbatim and categorized:

| Category | Permitted? | Counted as methodology gap? |
|---|---|---|
| **Technical access** (repository credentials, build environment, script installation) | Yes | No |
| **Methodology ambiguity** ("what does this sentence in §4.7 mean?") | Yes | **Yes** — each question is a finding about where the document failed to be self-sufficient |
| **Scoring guidance** ("how should I score this dimension?") | Not permitted — assessor must make their own judgment | N/A |

The log of methodology-ambiguity questions is published as an appendix to the Paper C manuscript. Each question constitutes evidence about which parts of the instrument need revision before commercial use. The transferability hypothesis (§4 item 3 of the original preregistration) is falsified if the assessor logs **3 or more** methodology-ambiguity questions — this threshold is unchanged from the original.

## 9. Clarification: Layer 1 exact-match prediction scope

The original Paper C preregistration §3.2 predicts that the independent assessor's Layer 1 indicator values will "exactly match" the author's values. This prediction applies to L1.1 through L1.17 only, because those indicators were computed against the codebases during or before Wasserman 2026. L1.18, L1.19, and L1.20 were added to the instrument after that assessment (see §6 above) and have no prior author-computed values to match against. The §3.3 predictions for L1.18/L1.19/L1.20 are first-time directional predictions, not exact-match reproduction targets.

## 10. Correction: L1.18-L1.20 author's values do not yet exist

The original Paper C preregistration §3.3 states that the assessor's L1.18-L1.20 values "should exactly match the author's values" and that "any disagreement between the author's and assessor's L1.18-L1.20 values" must be investigated. This implies the author has already computed these values on Application A and Application B. He has not. The L1.18, L1.19, and L1.20 scripts exist and are validated (Paper A), but they have not been executed against the Wasserman 2026 codebases.

The predictions in the §3.3 table (e.g., Application A L1.18 < 15%, Application B L1.18 > 40%) are directional estimates based on the author's knowledge of the codebases, not reproductions of prior computed values.

**Amended protocol:** Before the assessor begins, the author will compute L1.18, L1.19, and L1.20 on both Application A and Application B, seal the values in a dated appendix filed on OSF, and share them with the co-investigator (if applicable) but NOT with the assessor. The assessor then computes independently. Values are compared after both computations are complete. Since the scripts are deterministic, any disagreement is a script bug or environment difference — not a judgment difference — and must be resolved before the data is reported.

The directional predictions in the §3.3 table remain as preregistered falsification targets. The sealed author's values become the exact-match reproduction target once computed.

## 11. Methodology gap noted during pre-experiment review

L1.11 (Containerization configuration) currently checks for the *presence* and *parameterization* of containerization artifacts (Dockerfile, docker-compose.yml, Helm charts, Kubernetes manifests). It does not distinguish between versioned and unversioned base images — i.e., `FROM python:latest` scores the same as `FROM python:3.13-slim`. Unversioned base images are a reproducibility failure: builds are not deterministic across time, and the resulting container may behave differently depending on when it was built. This is structurally analogous to the unbounded-state problem L1.18 measures at the function level — an unversioned base image introduces uncontrolled external state into the build. This refinement (requiring version-pinned base images for the "Healthy" threshold) is queued for the v1 methodology revision and does not affect the v0 instrument under validation in Paper C.

## 7. Status of this amendment

This amendment is public supplementary material to the Paper C preregistration. It does not modify any pre-registered prediction or falsification criterion. It is timestamped as of the date in the header and is attached to the Paper C OSF registration as an addendum. It is cited in the Paper C manuscript's theoretical-framework section.
