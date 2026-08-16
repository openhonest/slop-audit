## 7. Validation

A methodology is not real until it has been validated against known cases. This section defines the validation protocol that establishes the slop audit methodology as defensible before any client engagement runs.

### 7.1 The validation set

Three codebases form the validation set:

**Positive control: a codebase known to satisfy the structured-condition criteria.** The honest-conversion branch of the buckler/idd repository (locally checked out at `/Users/adam/dev/buckler/idd`) is the canonical positive control. It is currently in active conversion to the Honest Code patterns, has TDD discipline visible in commit history, has pre-commit hooks running pytest, has structured phase planning, has security fixes (XSS, HMAC, rate limiting), and has middleware tests for auth, security headers, rate limiting, and request IDs. Running the methodology on this codebase should produce a Layer 1 pattern classification of "Structured" and a Layer 2 score of approximately 14 to 17 dimensions present.

**Negative control: a codebase known to exhibit the unstructured-condition pattern.** A specific pre-conversion branch of the same repository (selection TBD; candidate branches include `bigseed`, `bob`, or one of the `feature/*` branches that predates the honest conversion work). Running the methodology on this codebase should produce a Layer 1 pattern classification of "Unstructured" or "Mixed" and a Layer 2 score of significantly fewer dimensions present.

**Calibration reference: the Wasserman 2026 paper itself.** The paper documents the structured condition (Application A: 18/18 dimensions) and the unstructured condition (Application B: 2/18 dimensions). Running the methodology on snapshots of those codebases (if accessible) should reproduce those scores within reasonable tolerance.

### 7.2 The cross-rater test

Two assessors run the methodology independently on the same codebase. Their Layer 1 indicator values must agree exactly (Layer 1 is mechanical, so any disagreement is a methodology bug). Their Layer 2 scores must agree on at least 16 of 18 dimensions for the methodology to be considered reliable. Disagreements on more than 2 dimensions trigger a methodology review and a clarifying revision to the affected dimension definitions in Section 4.

The cross-rater test is run at three points: once before any client engagement (initial validation), once after the first three client engagements (calibration), and at six-month intervals thereafter (drift detection).

### 7.3 The "would the auditor agree" test

For each dimension scored *absent* in a real client engagement, the assessor must be able to write the following sentence with confidence:

> "If a financial services technology auditor or technology risk committee at [SOC 2 / NIST / OSFI / FFIEC] inspected this codebase against [the published threshold for this dimension], they would record the same finding."

If the assessor cannot write this sentence with confidence, the dimension was scored on judgment, not on threshold. The score is downgraded from *absent* to *partial* or removed. This test prevents the methodology from drifting toward stricter-than-published criteria, which would damage its defensibility.

### 7.4 What validation produces

A signed validation report attached as an annex to this methodology document, naming the assessors, the validation set, the cross-rater agreement rate, and the dates. Without a signed validation report, the methodology is "v0 frame" and cannot be sold to clients. With a signed validation report, the methodology becomes "v1 production" and is the basis for the audit partner's commercial Phase 0 engagements.

### 7.5 Validation status as of this document

**Not yet validated, but unblocked.** Section 4 (the per-dimension catalog) is now complete in v0 form across all 18 dimensions under the four-layer model, which was the prerequisite for running the validation cycle. Validation is the next gating step before the methodology can be used in a client engagement. The positive control (`idd honest-conversion` branch) is expected to be validation-ready on 2026-04-30 per `methodology/validation/protocol.md`; the validation run can begin immediately thereafter.

---

