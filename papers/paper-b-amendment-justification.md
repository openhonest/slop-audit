# Paper B Preregistration Amendment — Justification

**Amendment date.** 2026-04-15.
**Original registration date.** 2026-04-12.
**Data collected under original design.** None. Task specifications, test suites, and paradigm prompts have been authored, but no generation runs against models have been executed. The amendment is filed before data collection begins.

---

## What is being amended

Two substantive changes and several derived bookkeeping updates.

### Change 1: Addition of a no-paradigm control condition (P0)

The original design specified five paradigm conditions (P1 pure functions through P5 deep inheritance). It did not include a no-paradigm-specified baseline.

Without a baseline the experiment can only talk about **differences between paradigms**, not about how far any paradigm prompt pulls the model from its natural tendency. A reviewer can legitimately ask: "when you omit the paradigm instruction entirely, what does the model do by default? Does P3 merely match the baseline, or does it move the model somewhere meaningfully different?" The original design cannot answer this question.

The amendment adds a sixth condition, **P0 (no architecture specified)**, whose prompt is identical to the other five except that the paradigm section is omitted. The model receives only the specification and the output-hygiene footer.

P0 serves as:

1. A reference point for absolute (not merely relative) paradigm effect sizes.
2. A test of whether the paradigm instructions themselves are necessary at all: if P0 matches one of P1-P5 on every dimension, that paradigm is the model's default and the instruction is redundant for it.
3. A diagnostic for training-data bias (see original pre-registration §8). If P0 consistently resembles a specific paradigm across tasks, the data reveal the model's shape prior, separate from any prompting effect.

### Change 2: Expansion from Python-only to four languages

The original design specified Python as the target language. The justification was that Python supports all five paradigms naturally. This remains true but the restriction is methodologically narrower than needed.

The cross-language claim Paper B implicitly makes — that paradigm choice affects AI code generation outcomes — is stronger if it generalises across languages that differ in how much paradigm flexibility they offer. JavaScript/TypeScript and C# each support the full P1-P5 span (first-class functions, records/dataclasses, classes, inheritance, abstract bases); Java is comparatively class-heavy but still permits all five through static utility classes, records, mixins via interfaces with default methods, and abstract base classes.

The amendment expands the language set to the same four languages used by Paper A:

| Language | Paradigm flexibility | L1.18 analyzer status |
|---|---|---|
| Python | Full (reference) | Paper A validated |
| TypeScript | Full | Paper A validated |
| Java | Partial (class-heavy idioms) | Paper A validated |
| C# | Full | Paper A validated |

All four languages carry Paper A's validated L1.18 analyzer, so the paradigm-control measurement (§3.6 of the original preregistration) transfers directly.

The predictions in §4 of the original document remain directional (P1 best → P5 worst on correctness and testability metrics) in every language, but the amendment allows the effect size to differ by language. Java in particular may compress the P1–P5 gap because its idiomatic range is narrower.

### Derived changes

- **Total generation runs.** Original: 25 tasks × 5 paradigms × 3 models = 375. Amended: 25 tasks × 6 paradigms × 4 languages × 3 models = **1,800 runs**.
- **Generation consistency runs (§3.3).** Original: 10 tasks × 5 paradigms × 3 models × 10 repeats = 1,500. Amended: 10 tasks × 6 paradigms × 4 languages × 3 models × 10 repeats = **7,200 runs**. If budget constraints force a reduction, repeats will be scaled down uniformly across cells rather than preferentially.
- **L1.18 measurement (§3.6).** Applied per-language using Paper A's language-specific analyzers.
- **Test suites.** The 25 Gherkin feature files are already language-agnostic. Step definitions and reference implementations will be ported to TypeScript, Java, and C# before any generation runs begin. The porting process preserves scenario count and content exactly; only the test runner and reference implementations differ.
- **Appendix A checklist.** Extended to include the three additional language ports and the P0 prompt.

## Why these changes belong in a pre-registration amendment rather than an exploratory addition

Both changes affect the experiment's **confirmatory** claims. The P0 baseline enters predictions: the direction of movement from P0 to each of P1-P5 is itself testable. The language expansion changes which population the effects are claimed about: "across four enterprise languages" is a stronger and differently-shaped claim than "in Python." Either change, if added post-hoc after data collection, would blur the line between confirmatory and exploratory results. Filing them as an amendment before data collection begins preserves the bright line and keeps the entire grid under confirmatory protection.

## What is NOT being amended

- Task set (25 tasks in the original five categories). Unchanged.
- Paradigm definitions for P1-P5. Unchanged.
- Six measurement dimensions (§3.1 through §3.6). Unchanged in definition; expanded in application to the new cells.
- Falsification criteria thresholds. Unchanged. They apply to the Python × P1-P5 subset of the grid (the original design) as the primary confirmatory test. Results from the P0 condition and the three new languages are reported in the same paper but analyzed as planned secondary analyses, not as reason to relax the primary falsification.
- Target venue (EMSE or ICSE). Unchanged.

## Data-collection status attestation

At the time of this amendment, zero API calls have been made against the models for Paper B's data collection. The pipeline has been end-to-end validated on task 01 (tax calculation) with 15 generation runs across the 5 paradigms × 3 models, but those runs were labelled *pipeline validation* and are excluded from any analysis reported in Paper B. All 1,800 runs in the amended grid will be fresh generations against the final prompt set.
