## 5. Conducting an audit (operational walkthrough)

### 5.1 Prerequisites before Day 1

Before the audit begins, the assessor must have:

- Read access to the target repository (clone or remote read)
- A defined branch and date range for assessment
- A written statement from the client identifying the codebase as representative of their current AI-assisted development practice
- Confirmation from the client that the codebase contains no material the assessor cannot legally inspect (export-controlled cryptography, regulated personally identifiable information without appropriate contractual cover, classified material)
- A working copy of this methodology document and the Layer 1 reference script
- Approximately 5 working days blocked on the calendar with no other commitments
- **A 30-minute interview slot scheduled with the client's technical lead**, to be held no later than end of Day 3. Two Layer 3 markers in Section 4 require direct conversation with the technical lead to score: dimension 4.16 Marker 5 (the team's list of things the AI is bad at, with reasons) and dimension 4.17 Marker 3 (the worst part of the codebase and the plan for it). These markers cannot be scored from artifacts alone because their evidence is in the team's working knowledge, not in the repository. The assessor should send the two interview prompts to the technical lead with the audit kick-off email so the lead has time to prepare a considered answer rather than an improvised one.

### 5.2 Day 1. Scoping and Layer 1 mechanical pass

**Morning (3–4 hours)**

- Clone the repository locally
- Validate that the date range and branch are accessible
- Run the Layer 1 reference script (or execute the twenty indicators manually, including the dead-code analyzer for L1.12, the fuzzy clone detector for L1.13, the secret scanner for L1.14, the type-escape count for L1.15, the trailing-whitespace scan for L1.16, the god-file count for L1.17, the mutable state ratio for L1.18, the decision-space coverage for L1.19, and the test determinism runs for L1.20)
- Generate the Layer 1 quantitative panel
- Record any anomalies (missing commits, force-pushes, history rewrites)
- Review the file structure to identify which directories contain the bulk of the production code, the test code, the configuration, and the documentation

**Afternoon (3–4 hours)**

- Note the slop signal count from Layer 1 and the resulting overall pattern classification
- Sketch a working hypothesis for which Layer 2 dimensions are most likely to be absent based on what Layer 1 surfaced (this hypothesis is for prioritization only and must not be allowed to bias the Layer 2 scoring)
- Build a per-dimension inspection plan: which files to inspect for each dimension, in what order
- Confirm the time budget for Days 2 and 3 against the per-dimension time estimates in Section 4

**Day 1 deliverable.** The Layer 1 panel as a complete page, plus the per-dimension inspection plan as a working document.

### 5.3 Day 2. Layer 2 dimensions 1–9

The assessor walks through the first nine dimensions in order, applying the per-dimension procedure from Section 4. Each dimension is scored *absent*, *partial*, or *present* with at least one cited evidence file or configuration. The assessor records the score, the evidence, and one to three sentences of qualitative assessment per dimension. Time budget is approximately 1 to 1.5 hours per dimension on a typical mid-size codebase, totaling 9 to 13 hours over the working day.

If a dimension cannot be scored within its time budget because the codebase does not yield clear evidence, the assessor records this as an explicit limitation in the Slop Report and proceeds. Spending more than the time budget on a single dimension is a sign that either the dimension is genuinely ambiguous (rare) or that the assessor is doing Phase 1 work disguised as Phase 0 (common). The latter is forbidden.

**Day 2 deliverable.** Nine completed dimension entries with scores, evidence, and qualitative assessment.

### 5.4 Day 3. Layer 2 dimensions 10–18

Same procedure as Day 2 for dimensions 10 through 18. End of Day 3 produces a complete 18-dimension scorecard.

**Day 3 deliverable.** Eighteen completed dimension entries; the Layer 2 portion of the Slop Report is now complete in raw form.

### 5.5 Day 4. Report writing and Layer 3 flagged findings

**Morning (3 hours)**

- Convert the raw Layer 1 panel and Layer 2 scorecard into the Slop Report template (Section 6)
- Write the executive summary: the Layer 1 pattern classification, the Layer 2 dimension count by score band, and the headline finding
- Identify the three to five most consequential absences (the dimensions whose absence most directly implies that current AI-assisted output is failing audit)

**Afternoon (3 hours)**

- Complete the Layer 3 flagged-for-follow-up section. During the Days 2 and 3 Layer 2 walkthrough, the assessor will have noticed architectural patterns that suggest deeper Layer 3 issues (inheritance hierarchies, hidden state, mocks-as-substitutes, application caches before query optimization). These are recorded here, **without scoring**, as candidates for Phase 1 architectural review.
- Cross-check that no Layer 2 dimension score has been influenced by a Layer 3 observation
- Final pass: grammar, citations, file paths, evidence quotes

**Day 4 deliverable.** A complete draft of the Slop Report, ready for client debrief.

### 5.6 Day 5. Debrief and Phase 1 scoping

**Morning (2 hours)**

- Walk the client's technical lead and CIO through the Slop Report
- Field questions on individual dimension scores; offer to show evidence files live in the IDE
- Distinguish *findings* from *recommendations*: the audit produces findings only, not remediation plans

**Afternoon (3 hours)**

- Use the audit findings to draft the **Escape Pod Proposal** (the third Phase 0 deliverable). The proposal identifies one greenfield candidate module scoped for an 8 to 12 week Phase 1 build, drawing on the audit's identification of which dimensions are most catastrophically absent in the existing landscape
- Use the audit findings to draft the **Self-Service Gap Analysis** (the second Phase 0 deliverable), which identifies which business-user requests cannot currently be safely supported because the underlying code base fails specific audit dimensions

**Day 5 deliverable.** All three Phase 0 deliverables (Slop Report, Self-Service Gap Analysis, Escape Pod Proposal) complete. Phase 0 is now ready to hand off to the CIO for the CPC packaging step.

### 5.7 Common time-budget failures

The 5-day budget is tight. The most common reasons it overruns:

1. **Layer 3 creep during Days 2 and 3.** The assessor finds an architectural pattern violation, becomes interested, and spends two hours investigating instead of recording it as a flagged finding and moving on. This is the single largest risk to the methodology and the most important boundary to enforce.
2. **Codebase larger than 250,000 LOC.** The 5-day budget assumes a mid-size codebase. Larger codebases require either an extended budget (typically 7 to 10 days) or a deliberate scope reduction to a representative subset.
3. **History rewrites or shallow clones.** If the git history has been rewritten or the repository was cloned with `--depth`, the Layer 1 indicators cannot be computed. Validate this on Day 1 morning before committing to the full audit.
4. **Client unavailability for Day 5.** If the technical lead and CIO cannot be in the same room on Day 5, the debrief slips and the Escape Pod Proposal cannot be drafted with their input. Confirm Day 5 attendance during prerequisites.

---

