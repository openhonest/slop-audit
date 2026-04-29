# Amendment v1 Pre-Registration

**Working title.** Amendment v1 to *Finite Testability of Enterprise Software*: Refinement of the L1.18 Operationalization to Exclude Bound Literals.

**Author.** Adam Z. Wasserman.

**Pre-registration date.** 2026-04-24.

**Amends.** Wasserman, *Finite Testability of Enterprise Software: A Quantitative Survey of Mutable State Across 200 Public Open-Source Codebases*, preprint, April 2026.

**Scope.** This is a **methodology amendment**, not a new empirical study. It pre-registers the refined operationalization of an existing indicator (L1.18) and the protocol for rerunning the existing corpus under that refinement. It does not register a new hypothesis for confirmatory test.

**Why pre-register a methodology amendment.** Three reasons:

1. The amendment changes numbers in a deposited empirical paper. Pre-registration prevents the appearance that the definition was tweaked post-hoc to preserve a desired finding.
2. Every other artifact in the Open Honest empirical research program (Papers A–H) is pre-registered. Structural consistency matters for the program's review audiences.
3. The refinement introduces a known residual false negative (opaque library mutation). Pre-registering the limitation — with the magnitude unknown until the rerun — is the honest posture.

---

## 1. What this amendment does

The L1.18 operationalization published in §3.1 of the original paper treats every top-level binding as "mutable at module scope." This over-counts by flagging **bound literals** — module-level bindings assigned once to immutable-typed values and never mutated — as mutable state. A function that reads `GOD_FILE_LINES = 1000` or a frozen dispatch dict has the same exhaustively-testable behavior domain as a function that inlines the literal. The over-counting is not an error the analyzer committed by accident; it is a definitional weakness of the original operationalization.

This amendment:

1. Refines the operationalization to exclude bound literals from the module-mutable reference set (§3 below).
2. Extends the validating behavioural specification from 249 to 276 scenarios (§4).
3. Adds a static pass, `bound_literal_detector.py`, to the replication package.
4. Amends the analyzer `l1_18.py` with a `--strict-mode` flag; amended mode becomes the new default, strict mode preserves original behavior byte-for-byte.
5. Reruns the 200-repository corpus using the amended analyzer (§5).
6. Reports updated per-language medians and reclassification counts (§6).

The scientific case for the refinement — the argument that bound literals do not expand the behavior domain and therefore do not contribute to state-space explosion — is developed in the accompanying methodology paper *Amendment to L1.18: Bound Literals Do Not Expand the Behavior Domain* (`paper-c-amendment-l118-bound-literals-rationale.md`). This pre-registration locks in the operationalization, the analyzer, the corpus, and the protocol; the rationale paper supplies the theoretical justification.

## 2. Relationship to the original paper's claims

The original paper's headline finding is that **most enterprise-scale codebases are structurally incapable of exhaustive behavioural verification on the L1.18 indicator alone**. The finding rests on three load-bearing observations:

1. **Per-language median ordering:** TypeScript ≪ C# < Java < Python.
2. **Classification majority:** in three of four languages (Python, Java, C#), the majority of repositories classify as Slop (ratio ≥ 40%).
3. **TypeScript bimodal structure:** a React-ecosystem frontend subpopulation with ratios below 15% and a NestJS/backend subpopulation in the 25–65% range.

This amendment does not retract or re-test any of these claims. The amendment's rerun reports updated per-language medians; whether the load-bearing observations are preserved is a factual question whose answer is determined by the rerun. This pre-registration pre-commits to publishing the rerun results regardless of whether the observations are preserved.

## 3. The refined operationalization (locked in)

§3.1 of the original paper defines "reference state outside parameter list" using three clauses covering four languages. The first two clauses — `this`/`self`/`cls` receiver references and implicit class-member references — are retained in form, but the implicit-member pass is extended (§3.2 below) so class-level bound literals are also excluded.

The third clause, covering the language-level equivalents of "mutable state visible to functions," is refined uniformly across Python, Java, TypeScript, and C#. A named binding is a **bound literal** — and therefore **not** counted as a mutable-state reference by L1.18 — if and only if **all four** of the following hold:

1. **Declared at module scope (Python, TypeScript) or as a class-level constant (Java `static final`, C# `const` or `static readonly`).** Per-language operationalization:
    - **Python:** module-top-level assignment `NAME = value`.
    - **TypeScript:** module-top-level `const NAME = value`. Top-level `let`/`var` are module-mutable under the original paper's §3.1 and are not eligible regardless of RHS.
    - **Java:** class-level `static final NAME = value`. Interface-level `final NAME = value` (constant by default) is also eligible.
    - **C#:** class-level `const NAME = value` or `static readonly NAME = value`.
2. **Assigned exactly once.** `NAME` is never on the LHS of any subsequent assignment, augmented assignment, or update expression in the file.
3. **Never mutated.** `NAME` is never subject to the language-specific syntactic mutation patterns. Python: `.append/.extend/.update/.pop/.clear/.remove/.sort/.reverse/.insert/.setdefault`, subscript assign, `del`. Java: `.add/.addAll/.put/.putAll/.remove/.clear/.sort`, indexed assign, field assign. TypeScript: `.push/.pop/.shift/.unshift/.splice/.sort/.reverse/.set/.delete/.clear`, subscript or property assign. C#: `.Add/.AddRange/.Insert/.Remove/.RemoveAt/.Clear/.Sort`, indexed assign, field assign. Read-only methods permitted.
4. **Right-hand side is bound-literal-eligible.** Accepts:
    - Immutable primitive literals (per-language: `int`/`str`/`bytes`/`bool`/`None`/`float`/`complex` for Python; `int`/`long`/`double`/`String`/`char`/`boolean`/`null` for Java; `number`/`string`/`boolean`/`null`/`undefined`/`template_string`/`regex` for TypeScript; `integer`/`real`/`string`/`boolean`/`null`/`character` for C#). Unary-signed included.
    - Immutable composite literals: Python `tuple`/`frozenset`; Java `List.of(...)`/`Set.of(...)`/`Map.of(...)`; TypeScript `readonly` tuples and frozen object literals; C# `ImmutableArray`/`ImmutableDictionary` / `readonly` collections.
    - Dict/object/map literals whose keys and values are bound-literal-eligible (recursive).
    - **Any class instantiation or function call** on the right-hand side: Python `ast.Call`, Java `object_creation_expression` or `method_invocation`, TypeScript `call_expression` or `new_expression`, C# `object_creation_expression` or `invocation_expression`. Uniform across languages; instantiation does not expand the behavior domain.
    - Type declarations: Python `TypedDict`/`Protocol`/`NamedTuple`/`@dataclass(frozen=True)`; Java records; C# `readonly record struct`; TypeScript `type` aliases and `interface`.

A binding that fails any of clauses (1)–(4) in its language-specific sense continues to be classified as genuine mutable state.

### 3.1 Scope of exclusion in the analyzer

Bound-literal detection is wired into `l1_18.py` at two passes:

- **Module-mutable pass** (Python, TypeScript): bound-literal names are removed from the `mutable` set passed to `module_mutable_refs`.
- **Implicit-member pass** (Java, C#, TypeScript class fields): bound-literal names are removed from the `class_members` set passed to `implicit_member_refs`. This is where Java and C# bound-literal over-counting manifests, because the original paper's §3.1 already stipulated no module-mutable path for Java/C#.

### 3.2 Secondary fix: kwarg / named-argument suppression

A latent bug was found in `l1_18.py`'s identifier-walk logic during amendment development: the name slot of keyword arguments (Python `keyword_argument.name`) and named arguments (C# `argument` with `name_colon`) was being treated as an identifier reference. The bug pre-dates the amendment and affected both strict and amended analysis. This amendment corrects it by extending `is_suppressed_identifier` and applying the suppression in `module_mutable_refs` (which previously did not use `is_suppressed_identifier`). Java has no keyword arguments; TypeScript's `shorthand_property_identifier` is a distinct AST type not reached by the identifier walk; no fix needed for those languages, verified with Gherkin scenarios.

The kwarg/named-arg fix applies in **both** strict and amended modes. Strict mode post-fix does not reproduce the original deposited analyzer byte-for-byte on any codebase that contains kwarg/named-arg patterns matching module-mutable or class-member names. See §7 (R6) for the retraction-condition implication.

**Code-level pre-commitment.** The implementation of this refined operationalization is:

- `bound_literal_detector.py`: unified tree-sitter-based detector, four languages, at commit hash `[TO BE FROZEN AT PRE-REGISTRATION TIMESTAMP]`.
- `l1_18.py`: amended with `--strict-mode` flag and kwarg/named-arg suppression for Python and C#, at commit hash `[TO BE FROZEN]`.
- `appendices/appendix-c2-bound-literals.feature`: 79+ scenarios covering Python (27), Java (16), TypeScript (18), C# (18), at commit hash `[TO BE FROZEN]`.

These three hashes together constitute the operational definition of the amendment and cannot be altered between this pre-registration and the rerun.

## 4. Validation

The amendment adds **27 behavioural specification scenarios** to the 249 scenarios validating the v3 analyzer in Appendix C of the original paper. The extension is at `appendices/appendix-c2-bound-literals.feature`. Coverage:

- Numeric / string / None bound literals (3 scenarios)
- Compound immutable literals (dict-of-literals, tuple, frozenset, lambda-valued dispatch dict) (5 scenarios)
- Frozen constructor calls (`re.compile`, `Path`) (2 scenarios)
- Class-instantiation RHS (3 new scenarios for the "any Call" principle)
- Type declaration RHS (TypedDict, Literal alias) (2 scenarios)
- Genuine mutable state disqualifying patterns (subscript assign, reassignment, `.append`, `.update`, list literal, dict-with-list, set literal, double-top-level, `del`) (9 scenarios)
- Shadowing (2 scenarios)
- Bootstrap and JSON output (1 scenario)

The combined 276-scenario specification is pre-committed at the same frozen commit hash referenced in §3.

## 5. Analysis protocol

The rerun executes in a single pass with no branching:

1. **Checkout the replication package at the frozen commit hash** (§3).
2. **Verify corpus manifest unchanged** from the original paper. The corpus is the same 200 repositories at the same commit-time snapshots. No repository is added, removed, or reclassified.
3. **Run `l1_18.py` in amended mode (default)** against each of the 200 repositories. Output JSON per repository to `results_amended/<language>/<org_repo>.json`.
4. **Run `l1_18.py --strict-mode`** against each of the 200 repositories. Output JSON to `results_strict_verify/<language>/<org_repo>.json`.
5. **Verify strict-mode output matches `results/`** byte-for-byte for every repository in the corpus. Any divergence is a replication failure that must be resolved before the amendment proceeds. This is the sanity check that strict mode is a true preservation of the original analyzer.
6. **Compute per-language statistics** in amended mode: mean, median, range, Healthy/Not-Healthy/Slop counts.
7. **Compute deltas** against the original paper's Table 1 (strict-mode medians).
8. **Fill Tables A-1, A-2, A-3** in the amendment document `research/paper-1-finite-testability/amendment-v1-bound-literals.md` with the computed numbers.
9. **Commit the filled amendment** as a distinct git commit, tagged `amendment-v1-results`, with commit message referencing the pre-registration date and this pre-registration document.

No intermediate analysis is performed on the output. No parameters are tuned between step 3 and step 6. The protocol is deterministic; a third party re-running steps 1–6 from the same commit hash should obtain identical results.

**Wall-clock time.** Approximately 20–25 minutes on a standard development machine, matching the original paper's reported runtime with a small overhead for the bound-literal pass.

## 6. Predictions

**Directional predictions** (sign committed in advance; magnitudes not):

- **P1.** Median mutable-state ratio in amended mode is **≤** strict-mode median for every language. (Basis: amended mode is strictly more permissive; it excludes a subset of what strict mode counts.)
- **P2.** Ordinal ordering TypeScript ≪ C# < Java < Python is preserved. (Basis: the fraction of functions reading bound literals is approximately language-agnostic at the per-function level; the idiomatic density of bound-literal declarations varies by language, but the dominant driver of language ordering — class-based vs. function-based paradigm — is orthogonal to bound-literal density.)
- **P3.** TypeScript bimodal structure is preserved. (Basis: the frontend/backend distinction is driven by paradigm, not by bound-literal density.)

**Predictions whose outcomes will determine whether further amendment is warranted:**

- **P4.** The C# median (strict: 40.0%, exactly at the Slop threshold) reclassifies downward under amended mode. (Basis: C#'s `static readonly` idiom is heavily used; this is the single most threshold-sensitive language in the corpus.)
- **P5.** No language's median falls below the 40% Slop threshold after the amendment (except TypeScript, which is already below). (Basis: the over-counting contribution of bound literals is expected to be 5–20 percentage points, which should leave Python, Java, and C# in the Slop band or adjacent Not-Healthy band; it should not drop them into Healthy.)

## 7. Falsification conditions

This amendment does not test a hypothesis in the Popperian sense. It refines an instrument. The analog of a falsification condition is a **retraction condition**: under what circumstances would the amendment itself be retracted or further amended?

- **R1. Strict-mode replication failure.** If `l1_18.py --strict-mode` does not reproduce the original `results/` byte-for-byte (step 5 of §5), the amended analyzer has altered strict-mode behavior inadvertently. The amendment is retracted and re-issued after the analyzer is corrected.
- **R2. Bound-literal detector bug.** If the `bound_literal_detector.py` flags a binding that is provably mutable (e.g., `DICT = {}; DICT[k] = v` in the same module), the amendment is retracted and re-issued after the detector is corrected.
- **R3. Bootstrap failure.** If `bound_literal_detector.py` itself scores non-zero L1.18 under amended mode (it should score 0.0%), the amendment's self-consistency is broken. Retract and correct.
- **R4. P1 violated.** If any language's amended-mode median is **greater** than its strict-mode median, the analyzer is definitionally broken (amended mode cannot count more than strict mode). Retract and investigate.
- **R5. P2 violated.** If the ordinal ordering is not preserved, the amendment has perturbed the dominant cross-language signal. The amendment is not retracted on this basis alone (the rerun is still reportable), but §5.2 of the original paper's discussion (Paradigm, not language, drives the ratio) requires re-evaluation in a subsequent amendment.
- **R6. Strict-mode deviation beyond the named kwarg/named-arg fix.** The kwarg/named-arg fix (§3.2) is explicitly acknowledged to break strict-mode byte-for-byte reproduction of the original deposited analyzer. That is the only strict-mode-affecting change sanctioned by this amendment. If a post-amendment strict-mode run on the 200-repo corpus shows *additional* deviations from the original `results/` JSONs — deviations not attributable to kwarg/named-arg suppression — the amendment is retracted and re-issued after the deviation source is identified and either documented or reverted.

Outcomes compatible with R1–R6 not triggering — including any outcome where P4 and P5 are violated — are **reported as published**. The amendment is not retracted for producing numerically inconvenient results.

## 8. Commitment to publish

Regardless of outcome, the amendment is published. The filled Tables A-1, A-2, A-3 in `amendment-v1-bound-literals.md` are the committed report. This pre-registration binds the author to publish whatever those tables contain once the rerun completes, subject only to the retraction conditions in §7.

Publication target: Paper 1 is still in draft and not yet deposited. The amendment's substantive content — the refined operationalization, the four-language detector, the `--strict-mode` flag, the extended behavioural specification, and the per-language medians under both modes — will be folded directly into Paper 1's draft before deposit. This amendment document and its pre-registration are preserved in the repository at `research/paper-1-finite-testability/amendment-v1-bound-literals.md` and `methodology/papers/amendment-v1-bound-literals-preregistration.md` respectively, as the provenance record of the methodology change. Git tag `amendment-v1-final` marks the commit at which the rerun results are frozen.

## 9. Audit trail

The full chain of custody is specified in the companion protocol document `methodology/papers/amendment-v1-audit-trail-protocol.md`. Key commitments:

- This pre-registration is timestamped on OSF before any rerun execution.
- All three pre-committed artifacts (rationale paper, bound-literal detector source, amended analyzer source) are committed to git before the rerun with their hashes recorded in §3.
- The rerun execution is wrapped in a commit-delimited scope: `amendment-v1-pre-rerun` tag → `run_amendment_v1.sh` execution → `amendment-v1-results` tag.
- The amendment document is committed twice: once with placeholder tables (pre-rerun, matching the tag `amendment-v1-pre-rerun`) and once with filled tables (post-rerun, matching the tag `amendment-v1-results`). The diff between these two commits is the amendment's empirical yield.

## 10. Author conflict disclosure

The amendment is authored by the original paper's author. No third party reviewed the amendment's definition before the rerun. This is a limitation of the solo-researcher context; the mitigation is the pre-registration itself, which binds the definition before the numbers are known. A subsequent amendment or revision with independent review would be a strictly stronger audit posture; this pre-registration is the strongest audit posture available within a solo-researcher context.

## 11. Pre-registration provenance

- **Pre-registration timestamp.** 2026-04-24.
- **OSF registration.** To be filed immediately upon finalization of this document, before any corpus rerun execution. The OSF record ID is recorded in `amendment-v1-audit-trail-protocol.md` upon filing.
- **Git commit of this document.** To be recorded in the audit-trail protocol.
- **Linked documents:**
  - `paper-c-amendment-l118-bound-literals-rationale.md` (methodology paper: theoretical justification)
  - `amendment-v1-bound-literals.md` (empirical amendment document: pre-rerun placeholder version)
  - `amendment-v1-audit-trail-protocol.md` (chain-of-custody protocol)
  - `research/paper-1-finite-testability/bound_literal_detector.py` (new analyzer module)
  - `research/paper-1-finite-testability/l1_18.py` (amended analyzer)
  - `research/paper-1-finite-testability/appendices/appendix-c2-bound-literals.feature` (extended behavioural specification)
