# Paper C Pre-Registration

**Working title.** Independent Validation of the Slop-Audit Methodology: Third-Party Reproduction of an 18-Dimension, 20-Indicator Enterprise Software Quality Assessment.

**Author.** Adam Z. Wasserman.

**Pre-registration date.** 2026-04-10.

**Methodology version under test.** the methodology documents (see `methodology/README.md`) at commit [TO ADD — the commit hash at time of Zenodo timestamp] of the the Open Honest repository. The 18 dimensions, the 20 Layer 1 indicators (including L1.18 mutable state ratio, L1.19 decision-space coverage, and L1.20 test determinism), the four-layer model, and the scoring rubrics are frozen at this commit for this paper.

---

## 1. What this paper tests

The Wasserman 2026 preprint (*Process Discipline as the Key Variable in AI-Assisted Enterprise Software Development*, Zenodo DOI 10.5281/zenodo.19355460) reported that a structured-condition codebase (Application A) satisfied 18 of 18 enterprise audit dimensions, while an unstructured-condition codebase (Application B) satisfied 2 of 18. Those scores were produced informally by the author: not using a documented, transferable methodology instrument.

This paper tests whether an **independent third-party assessor**, working from the formal v0 slop-audit methodology document alone, **reproduces the original findings** on the same codebases. The question is not "are the codebases good or bad?" (the preprint already answered that). The question is: **is the slop-audit instrument reliable and transferable?** Can someone other than the author, using only the documented methodology, arrive at the same scores?

This is the foundational validation that the entire Open Honest certification model depends on. If the instrument is not reproducible by a trained independent assessor, the certification has no basis. If it is, the certification model is empirically grounded.

### 1.1 Novel components of the instrument under validation

The instrument being validated contains multiple components that have no direct precedent in the literature. The assessors are not validating a routine audit; they are testing the transferability of several individually novel contributions bundled into a single operational instrument:

1. **The first compliance-mapped, multi-dimension codebase audit instrument.** ISO/IEC 25010 defines 8 quality characteristics but provides no operational scoring procedure, no per-dimension evidence citations, and no compliance-framework cross-mapping. SonarSource and CodeScene measure code metrics but do not map findings to SOC 2, NIST 800-53, OSFI B-13, or OWASP ASVS. No prior instrument combines 18 enterprise dimensions with compliance-framework mappings and a formal scoring rubric.

2. **The four-layer judgment model.** No prior software quality instrument formally separates mechanical measurement (Layer 1), artifact inspection (Layer 2), qualitative specified-marker assessment (Layer 3), and elite architectural judgment (Layer 4) into distinct layers with distinct training requirements and inter-rater reliability targets per layer.

3. **L1.18: Mutable state ratio as a formal indicator.** No prior work has operationalized "what percentage of functions reference mutable state outside their parameters" as a quantitative software quality indicator computed at scale. The closest prior art is Unkel & Lam 2008 (POPL), who measured immutability potential of Java fields (44-59% stationary), but they measured fields, not function behavior, and did not operationalize the measurement as an audit indicator.

4. **L1.19: Decision-space coverage.** Line coverage and branch coverage exist as standard metrics. "Of the finitely enumerable decisions in the code (dispatch table keys, match/case arms, enum branches), what percentage are exercised by tests?" is a metric that does not exist in the published literature. L1.19 defines it, operationalizes it, and includes it in the instrument.

5. **L1.20: Test determinism as a formal indicator.** Running test suites in randomized order is a known testing technique. Operationalizing the pass rate under randomized order as a formal quality indicator with defined threshold bands (Healthy/Not Healthy/Slop) is new.

The validation study therefore tests not only whether the instrument is reproducible, but whether these individually novel components are clear enough in the methodology document for an independent assessor to apply without coaching. Each component that an assessor cannot apply is a finding about which part of the instrument needs revision.

## 2. Design

**Reproduction + generalizability study.** Independent assessors run the formal v0 slop-audit methodology against codebases the author has previously assessed (reproduction) AND against codebases the author has never seen (generalizability). If multiple assessors participate, inter-rater reliability is measured.

### 2.1 The codebases

**Set 1: reproduction (author-assessed).** Two codebases with known scores from the Wasserman 2026 preprint:

| Codebase | Repository | Paper 1 designation | Paper 1 informal score | Condition |
|---|---|---|---|---|
| **Application A** | The structured-condition codebase documented in Wasserman 2026 §3.2 | Application A | 18 of 18 dimensions satisfied | Structured AI-assisted SDLC with spec-before-code, BDD-first, real-time architectural review, pre-commit hooks, automated quality gates |
| **Application B** | The unstructured-condition codebase documented in Wasserman 2026 §3.1 | Application B | 2 of 18 dimensions satisfied | AI-assisted development without structured process discipline |

**Set 2: generalizability (assessor-selected).** Each assessor independently selects 2-3 public open-source codebases that Adam has never seen and has no involvement with. Selection criteria: must meet the Paper A corpus filter (application, 10K+ LOC, test directory present), should span at least two programming languages, and should include at least one codebase the assessor expects to score well and one they expect to score poorly. The assessor does NOT share their selections with Adam until after the audit is complete. Adam makes NO predictions for Set 2 codebases because he has never seen them. The Set 2 results test whether the instrument produces interpretable, defensible findings on code it was not designed around.

### 2.2 The independent assessor

The assessor must be:
- **Not Adam Wasserman:** the methodology author cannot validate his own instrument
- **Not involved in the development of either codebase:** the assessor must be blind to the architectural decisions and their rationale
- **Not commercially affiliated with the Honest Foundation, the audit partner, or Buckler** at the time of the audit: no financial interest in the instrument validating well
- **Working from the methodology document alone:** the assessor receives the methodology documents v0, the L1.18/L1.19/L1.20 analysis scripts, and the Section 5 operational walkthrough. No coaching, no clarifying conversations with Adam, no supplementary materials beyond what the document contains. This constraint is the transferability test: if the documents and scripts are sufficient, the assessor produces valid scores; if they aren't, the methodology needs revision

### 2.3 Multi-assessor design (if applicable)

If two or more independent assessors participate, each assessor runs the full methodology independently on the Set 1 codebases (Application A and Application B). Both assessors produce scorecards without seeing each other's work. Inter-rater reliability is measured:

- **Layer 1 agreement:** L1 indicators are mechanical; any disagreement is a methodology bug, not a judgment difference. Expected: 100% agreement.
- **Layer 2 agreement:** per-dimension Present/Partial/Absent scores. Measured as: number of dimensions where both assessors agree / 18. Target: ≥16/18 agreement.
- **Layer 3 agreement:** per-dimension marker scores. Measured as: number of markers where both assessors agree / total markers. Target: ≥80% agreement (lower threshold because Layer 3 involves qualitative judgment).
- **L1.18/L1.19/L1.20 agreement:** these are script-computed, so agreement should be exact. Any disagreement indicates a script bug or environment difference.

For Set 2 codebases (assessor-selected), inter-rater reliability is measured only if both assessors happen to select the same codebase (unlikely). Otherwise, Set 2 measures generalizability per assessor independently.

**Candidates under consideration (all contacted, awaiting responses as of 2026-04-12):**
1. **Jeremy Bradbury** (Ontario Tech University, AI-SQE 2026 PC member): collaboration ask sent. His SEER Lab students could serve as independent assessors.
2. **AI-SQE workshop community** (Onn Shehory, Eitan Farchi): post-workshop introduction sent.
3. **Robert Feldt** (Chalmers, EMSE co-Editor-in-Chief): EMSE fit-check sent.
4. **Christoph Treude** (Singapore Management University, FSE 2026 co-chair): contacted via X post.
5. **Sebastian Baltes** (Heidelberg University): contacted via X post.
6. **the audit partner (the audit partner's principals):** currently unaffiliated. Would also serve as a transferability test: untrained assessors producing valid scores from the document alone.
7. **Daniel Beauchemin (QFrBLiMP author):** procedural witness on chain of custody, not primary assessor.

### 2.4 What the assessor receives

1. The methodology documents at the pinned version
2. The L1.18, L1.19, and L1.20 analysis scripts from the Paper A research directory
3. Read access to the Set 1 repositories (Application A and Application B) under NDA
4. The Section 5 operational walkthrough (the 5-day audit procedure)
5. Nothing else. No pre-briefing, no hints about expected scores, no access to the Wasserman 2026 preprint's dimension-level findings (the assessor should NOT know what scores the author produced; only that two codebases are to be audited)

### 2.5 What the assessor does NOT receive

- The Wasserman 2026 preprint (or if they have already read it, this is disclosed as a limitation)
- Any indication of which codebase is "expected to score well" and which is "expected to score poorly"
- Any communication with Adam during the audit beyond technical access issues (repository credentials, methodology document clarifications limited to "what does this sentence mean," not "how should I score this")
- The predictions in §3 of this pre-registration document

## 3. Pre-registered predictions

The predictions for this paper are aggregate, not per-dimension. The independent assessor produces per-dimension scores; the pre-registration predicts the *totals* and the *gap*, because the question is "does the instrument reproduce the original findings?" not "does the author correctly predict each dimension."

### 3.1 Aggregate predictions

| Codebase | Paper 1 self-audit result | Predicted independent-audit result | Tolerance |
|---|---|---|---|
| **Application A** (structured condition) | 18 of 18 dimensions satisfied | **≥16 of 18 dimensions Present** | ±2 from self-audit |
| **Application B** (unstructured condition) | 2 of 18 dimensions satisfied | **≤4 of 18 dimensions Present** | ±2 from self-audit |
| **Gap (A minus B)** | 16 dimensions | **≥10 dimensions** | The separation must remain dramatic |

### 3.2 Layer 1 indicator prediction

The author predicts that the independent assessor's Layer 1 indicator values will **exactly match** the author's values for both codebases, because Layer 1 is mechanical (git-history queries with defined thresholds). Any disagreement on Layer 1 is a methodology bug, not a judgment difference, and must be reported as such.

### 3.3 L1.18-L1.20 predictions

The assessor runs the L1.18, L1.19, and L1.20 scripts on both Set 1 codebases. These are script-computed and should exactly match the author's values:

| Indicator | Application A predicted | Application B predicted |
|---|---|---|
| L1.18 Mutable state ratio | < 15% | > 40% |
| L1.19 Decision-space coverage | > 80% | < 30% |
| L1.20 Test determinism | 5/5 | < 3/5 |

Any disagreement between the author's and assessor's L1.18-L1.20 values on the same codebase indicates a script bug or environment difference (not a judgment difference), and must be investigated and resolved before the data is reported.

### 3.4 What the predictions deliberately do NOT include

Per-dimension predictions are not pre-registered because they are not what this paper tests. The paper tests whether the instrument is *reproducible*: whether an independent assessor, working from the document alone, arrives at approximately the same aggregate result. Which specific dimensions the assessor scores differently (if any) is a *finding* of the paper, not a prediction. The per-dimension divergences, when they occur, are the most valuable data in the paper because they identify which dimensions need clearer scoring criteria in the methodology's next revision.

## 4. Falsification criteria

1. **The reproduction hypothesis** is falsified if the independent assessor's total Present count for either codebase differs from the self-audit result by more than **2 dimensions**. Application A must score ≥16 Present. Application B must score ≤4 Present. If either condition fails, the instrument does not reliably reproduce the original findings.

2. **The discrimination hypothesis** is falsified if the gap between Application A's Present count and Application B's Present count is **fewer than 10 dimensions**. The self-audit gap was 16. The formal instrument must reproduce a dramatic separation; a collapsed gap indicates the instrument lacks discriminating power.

3. **The transferability hypothesis** is falsified if the independent assessor reports that the methodology document was **insufficient to score 3 or more dimensions** without clarification from the author. Each clarification request is a point where the document failed its job. Fewer than 3 is acceptable for v0; 3 or more triggers a methodology revision before commercial use.

4. **The Layer 1 exactness hypothesis** is falsified if any Layer 1 indicator value differs between the author's computation and the assessor's computation on the same codebase. Layer 1 is deterministic; any disagreement is a methodology bug.

## 5. Sequence of events

1. **2026-04-10:** Predictions in §3 filled in by Adam. Pre-registration timestamped via Zenodo.
2. **2026-04-10 onward:** Predictions are locked. Adam may edit prose, formatting, and the assessor identity field; not the predicted scores or falsification criteria.
3. **Assessor identified and committed:** before audit begins. Target: confirmed by 2026-04-30.
4. **Assessor receives the methodology document and repository access:** assessor does NOT receive this pre-registration document or the Wasserman 2026 preprint's dimension-level findings.
5. **Assessor runs the audit:** approximately 5 working days per codebase, ~10 working days total per the Section 5 walkthrough.
6. **Assessor produces dimension scorecards** for both codebases.
7. **Pre-registration predictions and audit results compared.** Falsification criteria applied.
8. **Manuscript drafted** reporting both predictions and results, including any falsifications.
9. **Submitted** to target venue (EMSE Registered Reports for Stage 1 protocol, or IEEE Software for a standard submission). The pre-registration DOI is cited in the methods section.

## 6. What this paper explicitly does NOT test

- **The Honest Code methodology's effect.** This paper tests the *instrument*, not the *methodology*. Whether the Honest approach reduces rework is Paper D.
- **Whether enterprise code is systematically untestable.** That is Paper A. This paper tests whether the instrument that measures testability is reproducible.
- **Which paradigms are most AI-compatible.** That is Paper B. This paper tests whether the instrument can be transferred to independent assessors, not whether the findings of other papers are correct.

## 7. What this paper does NOT protect against

- **The assessor having read the Wasserman 2026 preprint.** If the assessor already knows the original scores (18/18 and 2/18), their assessment may be anchored. This is disclosed as a limitation. Mitigation: the assessor is asked not to re-read the preprint before the audit, and the pre-registration document (which contains the predictions) is withheld until after the audit.
- **The codebases having changed since the original assessment.** Application A and Application B are production codebases that may have received commits since the Wasserman 2026 assessment period. The audit should be scoped to the same branch and date range as the original study; any divergence is disclosed.
- **The author's predictions being informed by the author's existing knowledge of the codebases.** The predictions in §3 are not blind predictions; Adam built Application A and knows exactly what is in it. The pre-registration's value is not in the predictions being blind (they cannot be) but in being *locked before the independent assessment* so they cannot be retroactively adjusted.

## 8. Timestamp anchor

**Timestamp anchor:** [TO ADD — Zenodo DOI or OSF registration ID once minted].

This pre-registration acquires its scientific value when timestamped via a third-party service. Acceptable anchors: Zenodo DOI (recommended), OSF Registration, or GPG-signed timestamped git commit.

---

## Appendix A: Pre-registration checklist

- [ ] Confirm the branch and date range for Application A and Application B to match the Wasserman 2026 assessment period
- [ ] Confirm the methodology version commit hash in the header
- [ ] Identify and confirm the independent assessor
- [ ] Mint Zenodo DOI, paste into §8
- [ ] Commit and push
- [ ] Send DOI to the assessor candidates and to Daniel Beauchemin (procedural witness)
