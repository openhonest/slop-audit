# Slop Audit Methodology — Validation Protocol

**Status:** v0
**Owner:** Adam Zachary Wasserman
**Purpose:** Define the validation cycle that confirms the slop audit methodology produces correct results before it is used on a paying client engagement.

---

## Why this document exists

The slop audit methodology in `the methodology documents (see ../README.md)` is a v0 instrument with eighteen dimensions, each scored across four layers, drafted from first principles and from the Wasserman 2026 paper. Before the methodology is used on a paying client engagement, it must be **validated** against codebases whose true classification is already known.

Validation does two things:

1. **Confirms that the methodology distinguishes structured from unstructured codebases**, by running it against a known-structured (positive control) codebase and a known-unstructured (negative control) codebase and confirming that the resulting scores fall in the expected bands.
2. **Surfaces any dimension whose markers do not discriminate**, so that those markers can be revised before the methodology is locked at v1.

A methodology that has not been validated is a methodology that nobody can defend in front of a hostile auditor or a skeptical CIO. The validation cycle is what converts the v0 draft into a defensible v1 instrument.

## Controls

### Positive control: `idd` honest-conversion branch

**Repository:** `/Users/adam/dev/buckler/idd`
**Branch:** `honest-conversion`
**Why this is the positive control:** This branch is the canonical example of a codebase that was deliberately built (and partially converted) under the structured AI SDLC documented in Wasserman 2026. It is the same class of system as Application A in the paper. By construction, it should score in the *Structured* band on Layer 1 and score *Present* on most or all of the 18 dimensions on Layer 2 and Layer 3. If it does not, the methodology has a calibration problem.

**Availability.** As of 2026-04-09, the `honest-conversion` branch is expected to be complete within three weeks (by 2026-04-30 at the latest, probably sooner). The positive-control audit should be run immediately upon branch stabilization. This date is the gating prerequisite for the Paper 2 drafting effort (see `project_peer_review_strategy.md` in the user's auto-memory).

**Expected outcome.** Layer 1 slop signal count ≤ 3 of the panel (see the note below on what the denominator is). Layer 2 dimensions scoring *Present*: ≥ 14 of 18. Layer 3 markers in aggregate scoring *Present*: ≥ 70%.

**If the result deviates from the expected outcome:** investigate before changing the methodology. The deviation may be a real finding (the branch has actually drifted), or it may be a methodology calibration problem. Determine which before adjusting anything.

### Negative control: TBD

**Status:** to be selected.

**Selection criteria.** The negative control should be a codebase that:

1. Was built primarily by AI assistance without structured process discipline (no spec-before-code, no quality gates, no AI safeguards)
2. Is in a regulated-enterprise-adjacent domain (web application, API service, admin panel) so that the 18 dimensions are all applicable
3. Is large enough to produce meaningful Layer 1 signal (≥ 30 commits, ≥ 5,000 LOC)
4. Is legally inspectable (open source under a permissive license, OR a Buckler internal repository, OR a synthetic repository deliberately constructed for validation)
5. Has not been used to train any of the AI tools that the validation process will discuss, to avoid the appearance of cherry-picking

**Candidates being considered.**

- A purpose-built synthetic repository constructed by deliberately running an AI agent against a small spec without any of the safeguards. This produces a maximally-clean negative control but raises the question of whether the result is contaminated by the construction process.
- An open-source repository identified through hotspot analysis (a project with high churn, low delete-to-add ratio, and visible signs of unsupervised AI assistance). This is the most ecologically valid choice but selection is delicate.
- The `idd` repository on a pre-conversion branch (e.g., `develop` before the `honest-conversion` work began). This is the cleanest comparison because the same codebase is its own positive and negative control on different branches.

**Decision deadline.** Negative control must be selected before the v1 methodology is finalized. Recommendation: use the `idd develop` branch as the first negative control because it is the cleanest comparison; add a synthetic or open-source negative control in v2.

**Expected outcome (once selected).** Layer 1 slop signal count ≥ 11 of 20, which is the spec's own high-confidence threshold (see the note below). Layer 2 dimensions scoring *Present*: ≤ 4 of 18. Layer 3 markers in aggregate scoring *Present*: ≤ 30%.

---


## Note on the denominator, added 2026-08-17 after the first run

This document was written against an eleven-indicator panel and said "of 11" in both expected outcomes. The methodology now defines **twenty** indicators, and `spec/03-layer1-indicators.md` sets the high-confidence threshold itself: *"A codebase scoring in the slop column on eleven or more of the twenty indicators is considered to exhibit the unstructured-condition pattern with high confidence."* The same paragraph rules that indicators returning **n/a** are excluded from both the numerator and the denominator of the slop signal count, so the denominator is twenty minus however many came back n/a on that repository.

The expected outcomes above have been repointed at the spec rather than left to contradict it. That is a correction to a document that lagged the methodology, not a change to the methodology, which the first run was explicitly forbidden from making.

The first run is recorded in `results/2026-08-17-layer1.md`. Read the deviation there against this note: the negative control's apparent miss was measured against a threshold this document had already outgrown.

## Validation procedure

### Step 1 — Positive control run

1. Clone the `idd` repository at the `honest-conversion` branch to a fresh working directory. Confirm full git history (no shallow clone).
2. Run the Layer 1 reference indicators (twenty of them, per methodology Section 3). Record the results in `validation/results/positive-control-layer1.md`.
3. Run the Layer 2 inspection procedures for all 18 dimensions, per methodology Section 4. Record scores and evidence in `validation/results/positive-control-layer2.md`.
4. Run the Layer 3 marker assessments for all 18 dimensions. Record scores in `validation/results/positive-control-layer3.md`.
5. Compute the combined dimension scores per the rubric in each Section 4 entry. Record in `validation/results/positive-control-combined.md`.
6. Compare the combined scores against the expected outcome. Record any deviation, with hypothesis as to cause, in `validation/results/positive-control-deviations.md`.

### Step 2 — Negative control run

Same as Step 1, but against the selected negative control branch and writing to `validation/results/negative-control-*.md`.

### Step 3 — Discrimination analysis

For each of the 18 dimensions, compare the positive-control score against the negative-control score. A dimension that scores *Present* on the positive control and *Absent* on the negative control is a discriminating dimension. A dimension that scores the same on both is a non-discriminating dimension and indicates either:

- a methodology problem (the markers do not actually distinguish what they claim to), or
- a control problem (one or both controls do not have the property the dimension measures), or
- a real finding (the dimension is genuinely orthogonal to the structured/unstructured distinction).

Each non-discriminating dimension is investigated and the cause is recorded in `validation/results/discrimination-analysis.md`.

### Step 4 — Methodology revision

Based on the discrimination analysis:

- Markers that do not discriminate are revised
- Dimensions whose Layer 2 procedure produced ambiguous evidence are clarified
- Time budgets that proved inaccurate during the runs are updated
- Section 4 entries are revised in place; the v0 entries are preserved in git history

The output is a v1 methodology document.

### Step 5 — Cross-rater run

A second qualified assessor (when available — initially this is unlikely to happen during v1 validation, but should happen before v2) runs the same protocol against the same controls. Inter-rater agreement is computed at the dimension level. Disagreements are investigated and either reconciled or flagged as residual ambiguity in the methodology.

---

## Validation results location

Results live in `methodology/validation/results/` as a set of dated directories:

```
methodology/validation/
├── protocol.md                            ← this file
└── results/
    ├── 2026-04-DD-positive-control/
    │   ├── layer1.md
    │   ├── layer2.md
    │   ├── layer3.md
    │   ├── combined.md
    │   └── deviations.md
    ├── 2026-04-DD-negative-control/
    │   └── ...
    └── 2026-04-DD-discrimination-analysis.md
```

Each run is dated to support the eventual cross-rater comparison and the year-over-year stability check (does the methodology produce stable results when re-run on the same codebase a year later?).

---

## What validation does not do

- **Validation does not certify that the methodology is correct in absolute terms.** It certifies that the methodology distinguishes the controls. Whether the controls are themselves correctly classified is a separate question, answerable only by appealing to ground truth (the Wasserman 2026 paper, the original architect's assessment, peer review).
- **Validation does not replace inter-rater reliability testing.** The cross-rater test (Step 5) is what produces the inter-rater number used for L2 certification. Validation against controls is necessary but not sufficient for that test.
- **Validation does not lock the methodology forever.** The methodology will be revised as new failure modes surface in real engagements, as the underlying AI tooling changes, and as the regulatory environment shifts. Validation is a checkpoint, not a freeze.

---

## Open questions for the validator

1. Is the `idd` `develop` branch a clean enough negative control, or does it already contain enough conversion work that the discrimination is muddied? Inspect before committing.
2. Should the validation runs be done blind (the assessor does not know which is the positive and which is the negative until after scoring) to eliminate confirmation bias? Recommendation: yes for v2 once a second assessor exists; not feasible for v1 with a single assessor who knows both repositories.
3. How is the methodology revised when the controls *agree* on a dimension that the methodology *predicts* should discriminate? This is the hardest case and the one most likely to surface a genuine methodology weakness. Recommendation: document the case, revise the markers, re-run.
4. What is the time budget for a full validation cycle? Estimate: 3 to 5 working days for the positive-control run, 3 to 5 working days for the negative-control run, 1 day for discrimination analysis, 2 to 4 days for revision. Total: 9 to 15 working days for the v0 → v1 transition.

---

## Status

- v0 protocol drafted (this document)
- Positive control identified (`idd honest-conversion`)
- Negative control: not yet selected; recommendation pending
- v0 methodology run against positive control: not yet performed
- v0 methodology run against negative control: not yet performed
- v1 methodology: not yet produced
