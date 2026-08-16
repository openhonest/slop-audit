# Peer Review Strategy for the Wasserman Papers

**Status:** v0 strategy + action plan
**Owner:** Adam Zachary Wasserman
**Scope:** The peer-review plan for the follow-on academic papers that anchor the Honest certification credibility chain. Not the Wasserman 2026 Zenodo preprint itself, which stays as a preprint.

---

## The core decision

**Skip peer review for the original Wasserman 2026 Zenodo preprint.** Do peer review for two (optionally three) follow-on papers that repackage the same material under different frames.

## Why skip peer review for the preprint

- Review cycles at software engineering venues are 6–18 months. Publication in 2027 would not affect 2026 sales cycles, which is the window where the paper has to do commercial work.
- Reviewer 2 risk is real: hostile reviewers could demand author-COI caveats, additional control conditions, or softening of the headline numbers in ways that weaken the paper's defensibility for the buyer audience that already accepts it.
- The preprint with a Zenodo DOI, BibTeX-quality citations, and git-history metrics is already sufficient for regulated enterprise buyers, who care that the work is citable and archived, not that it cleared a double-blind review.

## The follow-on paper sequence

1. **"An 18-Dimension Audit Framework for Enterprise Software Maturity"** — target **IEEE Software** or **ACM Computing Surveys**. Framed as a synthesis of NIST 800-53, OWASP ASVS, DORA, OSFI B-13, FFIEC, SIG, AICPA, CISA, CNCF, and Gartner. Synthesis papers have a high hit rate at these venues. ~12 months to publication.

2. **"Operationalizing Process Discipline Audits in AI-Assisted Development: The Slop Audit Methodology"** — target **Empirical Software Engineering** or **Journal of Systems and Software**. Frames the four-layer model, the per-dimension inspection procedures, the inter-rater reliability protocol, and the validation cycle. Methodology papers have a high hit rate at these venues. ~12 months to publication.

3. **(Optional)** "A Four-Layer Model for Software Architecture Assessment under AI-Assisted Development" — target **IEEE Transactions on Software Engineering** or a workshop venue. ~9 months. Lower priority than 1 and 2.

## The framework extension paper cadence (decided 2026-04-09)

After the initial follow-on sequence above, the methodology grows through **standalone framework extension papers**, one per substantive new dimension or per substantive new methodological mechanism. This is the cadence:

1. **One extension paper per real engagement-driven gap.** When a Phase 0 audit surfaces a gap that the existing 18 dimensions cannot capture, the gap becomes a candidate for an extension paper. Extensions are not added to the methodology document directly; they are drafted as standalone papers, pre-registered against a specific methodology version, validated independently, and only then incorporated into a future v1.x catalog release. The cadence is one extension per real gap, not many speculative extensions in a single revision.

2. **Each extension paper has its own pre-registration and its own validation cycle.** The extension paper inherits the pre-registration discipline of Paper 2: predictions are locked before measurement, falsification criteria are stated explicitly, and an independent auditor performs the measurement. Extensions cannot be added to the catalog without clearing the same integrity bar Paper 2 establishes.

3. **The Honest Foundation governance gates the catalog.** When the Honest Foundation is established, its constitution accepts framework extensions to the certified catalog only after the extension has cleared peer review at a recognized venue. This is the structural protection against methodology drift and against commercial-administrator capture: no commercial party (the audit partner or any future licensee) can add dimensions to the certified version of the methodology by themselves. Adding a dimension requires publishing an extension paper, clearing peer review, and submitting the extension to the Foundation for incorporation. The peer-review venue is the gatekeeper, not the Foundation's commercial administrator.

4. **The cadence creates the recurring-revenue cycle for the certification administrator.** Each new version of the certified methodology requires existing certified practitioners to recertify, which is a recurring-revenue event for whoever administers the certification (the audit partner in the projected licensing structure). This is the same pattern Pink Elephant used with ITIL versions (v2, v3, v4), where each major version triggered a recertification cycle and a new training cohort. The Honest framework's version cadence is gated on peer-reviewed extension papers, which means recurring revenue only flows when the methodology has *substantively* improved — not when the administrator has unilaterally decided to charge for an update. This protects the practitioners as well as the foundation.

5. **First identified extension candidate: Dimension 4.19, Operational handoff readiness.** Scope sketch lives in the methodology documents (see `methodology/README.md`) under "Future methodological extensions." This is the dimension that measures the dev-side preparation for handoff to operations: runbooks, on-call playbooks, operational logging configuration, alerting-as-code, rollback procedures, service ownership, smoke tests, and known-issue documentation. Decided 2026-04-09 to defer 4.19 from v0 and develop it as the first framework extension paper, targeting publication after Paper 2 is accepted.

**Working title for the first extension paper:** *Operational Handoff Readiness as a Phase 0 Audit Dimension: Extending the Slop-Audit Methodology to the Dev-Ops Boundary.* Target venue: **EMSE** with the Registered Reports format if available, otherwise **IEEE Software**. The Registered Reports format is the right fit because the extension is pre-registered (predictions and validation protocol locked before measurement) and EMSE is one of the few SE venues that explicitly accepts registered reports.

**Why this cadence works strategically.**

- **It converts each new dimension from "free supporting material" into "publishable methodological contribution."** Adding 4.19 to v0 directly would make it a footnote in Paper 2; publishing it as an extension paper makes it a credentialing event in its own right. That is approximately a 4× value multiplier on the same underlying work.
- **It preserves v0's coherence as the ground-truth mapping to Paper 1.** The 18 dimensions in v0 are the operationalization of what came out of the natural experiment. Adding dimensions that did not come out of the natural experiment dilutes the provenance. Keeping v0 frozen at 18 means every Paper 2 reader can trace v0 directly to the published natural experiment.
- **It builds a 5–10 year publication trajectory** out of material that is already partially identified (the candidate extensions in the methodology document's TODO list). Each extension is a potential paper. The trajectory is concrete, not vague.
- **It strengthens the long-term Honest Foundation credibility argument.** A methodology framework that grows through peer-reviewed extensions has substantially more academic standing than one that grows through unilateral author revisions. The growth pattern is the credibility, not just the catalog.
- **It maps directly onto the Pink Elephant / ITIL versioning analogy** in a way that strengthens the the audit partner licensing pitch. ITIL grew through versioned releases that were not peer-reviewed but that triggered Pink Elephant recertification cycles; the Honest framework can grow through peer-reviewed versioned releases that trigger the audit partner recertification cycles. The recurring-revenue cadence is directly attached to the publication cadence, which means the academic credibility and the commercial credibility reinforce each other rather than competing.

**Operational policy for the cadence.**

- The methodology document's "Future methodological extensions" TODO section lists each candidate extension with a scope sketch.
- An extension is promoted from candidate to *active drafting* when an engagement surfaces enough validation evidence to warrant a paper.
- Active drafting follows the Paper 2 template: pre-registration first (with falsification criteria), independent validation, then peer-reviewed publication.
- After publication, the new dimension is incorporated into a v1.x release of the methodology document, with the version number bumped and a release-notes section added.
- The Honest Foundation, once established, gates incorporation: no extension enters the certified catalog without prior peer-reviewed publication.

## The Paper 2 and Paper 3 design (revised 2026-04-11)

### Design history

The original Paper 2 design (within-subject longitudinal replication across IAM, nexus-go, and idd with Shawna Staff as her own control) was abandoned on 2026-04-10 after analysis revealed that all three codebases score Present on nearly all 18 dimensions — a ceiling effect that produces trivially confirmable predictions with zero scientific interest. All three codebases were under a structured SDLC before the Honest Code book was published (March 31, 2026), so the contrast between "no methodology" and "methodology" was not present in the data.

The redesigned approach splits the work into two papers with distinct contributions:

### Paper 2: Independent third-party instrument validation

**What it tests.** Can an independent assessor, working from the methodology document alone, reproduce the original Wasserman 2026 findings on the same codebases? The question is about the *instrument's* reliability and transferability, not about the Honest Code methodology's effect.

**Design.** 2–3 independent academic assessors (ideally from Jeremy Bradbury's SEER Lab at Ontario Tech, or from the AI-SQE workshop community) run the formal v0 slop-audit methodology against Application A (structured, 18/18 in Paper 1) and Application B (unstructured, 2/18 in Paper 1), plus 2–3 open-source codebases the assessors select independently that Adam has never seen. The assessors work from the methodology document alone with no coaching. Inter-rater reliability is measured between assessors. Transferability is measured by recording where the document was insufficient.

**Predictions.** Aggregate, not per-dimension: Application A ≥16/18, Application B ≤4/18, gap ≥10 dimensions. Layer 1 indicators must match exactly (mechanical, deterministic).

**Falsification criteria.** Reproduction (±2 from self-audit), discrimination (gap ≥10), transferability (fewer than 3 dimensions needing clarification), Layer 1 exactness.

**Pre-registration.** The pre-registration document at `paper-3-instrument-validation-preregistration.md` is ready to timestamp once the independent assessors are confirmed. The pre-registration cannot be finalized until the assessor identity is known.

**Target venue.** EMSE (Registered Reports if assessors are confirmed before submission) or IEEE Software.

### Paper 3: Pre-honest vs post-honest idd on rework and bug fixes

**What it tests.** Does the Honest Code methodology reduce rework and bug-fix frequency when applied on top of an already-structured SDLC? The question is about the *methodology's* marginal effect on maintenance cost.

**Design.** Within-codebase comparison of the idd repository (`github.com/TraileAI/idd`) before and after the honest-conversion. Same developer (Shawna Staff), same repository, same tools. Shawna autonomously adopted Honest Code practices on or shortly after the March 31, 2026 publication date. The `honest-conversion` branch is the treatment; the prior branches are the baseline.

**Metrics.** Continuous, not binary: rework rate (how often a file is touched again within 30 days), bug-fix commit frequency, regression count, delete/add ratio, LOC delta (including the 300k-line net-negative delete), time-to-fix. These metrics avoid the ceiling effect because they are continuous — two codebases that both score "Present" on dimension 4.17 can still differ dramatically on the underlying continuous indicators.

**Additional within-subject data.** Shawna has a separate non-Buckler, non-Wasserman repository started pre-Honest that she is willing to submit to analysis and to continue working on under Honest practices. This provides a second within-codebase pre/post comparison with zero Adam involvement, which dissolves the CTO-relationship confound entirely.

**Co-authors.** Adam Wasserman and Shawna Staff. Shawna writes the first-person section describing her practice. The consent brief is at `paper-2-coauthor-brief-shawna.md` (needs updating to reflect that Shawna's role is now Paper 3, not Paper 2).

**Target venue.** EMSE or IEEE Software. Paper 3 is submitted after Paper 2 validates the instrument.

**[SUPERSEDED 2026-04-11 — the content below is from the abandoned within-subject design. See §"The Paper 2 and Paper 3 design (revised 2026-04-11)" above for the current design.]**

~~**The new Paper 2 in one paragraph.** Three codebases written by the same developer (Shawna Staff) across three different methodology-exposure conditions and three different supervisory contexts: IAM (joint Adam/Shawna IP, no methodology exposure), IAM Go v2 (Shawna's fully independent extra-organizational work, no methodology exposure, no CTO relationship), and `idd honest-conversion` (Buckler-context work with full Honest Code methodology exposure). The within-subject design holds developer identity constant while varying both methodology exposure and supervisory context. IAM Go v2 is the genuine independence control: a codebase Shawna built completely outside Adam's chain of command, which a reviewer can compare against `idd honest-conversion` to test whether the CTO relationship is biasing the in-context measurement.

**Author-observer confound mitigation.** Three layered protections:

1. **Pre-registration.** Predictions for all 18 dimensions × 3 codebases are locked tonight (2026-04-09) via a Zenodo-timestamped document. The pre-registration includes six explicit falsification criteria so the integrity of the predictions can be verified after measurement.
2. **Independent measurement.** The audit is performed by an independent assessor who is neither Adam nor Shawna, who has no involvement in any of the three codebases, and who has no commercial interest in the methodology validating well at the time the audit is performed. Current candidates: the audit partner's principals (in their currently-unaffiliated window, before any commercial license discussion advances), with Daniel Beauchemin (QFrBLiMP author) as procedural witness on the timestamping and chain of custody.
3. **Co-authorship of the developer.** Shawna Staff is named as co-author candidate in the pre-registration. Co-authorship reframes the paper from "the CTO ran an experiment using his employee's work" to "two collaborators with different roles published a study together," and Shawna's first-person account of how she actually works (especially her independence on IAM Go v2, which Adam had no involvement in) is the load-bearing source of the design's credibility. The consent brief is at `paper-2-coauthor-brief-shawna.md`.

**Disclosure of financial interest.** Adam and Shawna jointly hold a 2025 patent on key aspects of IAM. Buckler licenses; Buckler does not own. The shared financial interest is disclosed at the top of the pre-registration document and will be disclosed in the manuscript. The protection is that IAM is in the *baseline* condition (no methodology exposure), so the paper's claim is that the methodology *adds something on top of* whatever IAM already scores — not that IAM is good. Falsification criterion 3 in the pre-registration specifically tests whether IAM's pre-Honest baseline already produces near-Structured outcomes (which would indicate the methodology's marginal effect is small).

**The recommended venue path: EMSE Registered Reports.** The new design changes the venue calculus that the original strategy contemplated. EMSE has a formal Registered Reports track, which is the right format for a pre-registered study. Under Registered Reports the submission flow is two stages:

- **Stage 1: protocol manuscript.** Submit the pre-registration document (formatted as an EMSE manuscript with introduction, motivation, design, and analysis plan, but no results) for editorial review. The reviewers evaluate whether the study question is sound, whether the design adequately tests the question, whether the analysis plan is appropriate, and whether the falsification criteria are well-formed. If the Stage 1 manuscript is accepted, the editor issues an **in-principle acceptance (IPA)**, which is a binding commitment to publish the Stage 2 results regardless of whether they confirm or falsify the predictions. Typical Stage 1 review at EMSE: 2–3 months.
- **Stage 2: results manuscript.** After the audit runs and the data is collected, the authors submit the results paper. Stage 2 review focuses on whether the study followed the IPA-approved protocol; it does not re-litigate the design choices or push back on the predictions. Typical Stage 2 review at EMSE: 1–3 months.

The two-stage process is what makes Registered Reports the strongest format for an integrity-protected paper: the editorial commitment to publish is made *before* the results are known, which removes the publication-bias incentive to soften or hide unfavorable findings. For a paper whose central claim is "we ran an experiment without rigging it," the editorial commitment to publish whatever we find is the most defensible move available.

**Timing constraint that EMSE Registered Reports introduces.** The Stage 1 submission can happen any time after the pre-registration is timestamped — the Zenodo DOI is independent of the EMSE submission. But the Stage 1 manuscript is a *fuller* document than the bare pre-registration: it needs an introduction, motivation, related work, threats-to-validity discussion, and EMSE-formatted bibliography. Drafting the Stage 1 manuscript is roughly two weeks of focused work on top of the pre-registration. The Stage 1 submission can land in May or June 2026, which is before the audit runs (the audit waits for `idd honest-conversion` validation-readiness on 2026-04-30 plus the IPA from EMSE Stage 1 review). Stage 2 results submission would land in late 2026 after the audit completes.

**Fallback venues if EMSE Registered Reports is unavailable or unsuitable.** ACM TOSEM accepts Registered Reports but has a longer review cycle (~12 months Stage 1). IEEE Software does not offer Registered Reports but accepts pre-registered work as a normal submission with the pre-registration cited in the methods section; faster review (~3–6 months) but no editorial commitment to publish in advance of results. The decision between EMSE and IEEE Software is a rigor/speed trade and can be made in May 2026 after the Stage 1 manuscript is drafted.

**The pre-registration is independent of any venue choice.** Tonight's Zenodo timestamp on `paper-3-instrument-validation-preregistration.md` is the integrity anchor. It works at any venue, including ones that do not have a formal Registered Reports track. The Zenodo DOI gets cited in whatever manuscript is eventually submitted, and reviewers at any venue can verify that the predictions were locked before the audit was run.~~

**[END SUPERSEDED SECTION]**

## Target citation chain by mid-2027

Wasserman 2026 (Zenodo preprint) → Wasserman 2027a (IEEE Software, 18-dimension framework) → Wasserman 2027b (EMSE, slop audit methodology) → Wasserman 2027c (workshop or TSE, four-layer model).

## Why the citation chain matters

- Standards bodies (ISO, NIST, OWASP, OSFI) cite peer-reviewed work preferentially over preprints when drafting or updating guidance
- Canadian regulators (OSFI, AMF, Régie de l'énergie) use peer-reviewed software engineering literature as the basis for technology-risk guidance
- The Certified Honest Practitioner credential becomes more defensible to enterprise procurement and audit committees if its methodology has been cleared through peer review
- The Pink Elephant model (the audit partner as commercial certification administrator) depends on the underlying framework being academically anchored, not just a consultancy white paper

## Why this is a low-cost project

The raw material for all three follow-on papers already exists in the 125KB working analysis document (`iridescent-moseying-pie.md`) plus the slop audit methodology document in this repo. Writing the follow-on papers is primarily repackaging, not fresh research.

## Standing directives

- The follow-on paper project is blessed regardless of whether the audit partner commercializes the certification
- Preprint stays as a preprint forever; the follow-on papers carry the academic citation weight
- The brand is "Honest," not "Wasserman"
- the audit partner is the first commercial administrator but not the exclusive one; retain the right to license other organizations with time-bounded territorial exclusivity
- When drafting content that cites the papers (track-c credibility memo, CIO pitch deck, Foundation Charter, certification marketing material), frame the current state as "peer-reviewed follow-on papers in progress" rather than as "peer-reviewed work already published." Do not overstate the review status.

---

## Action plan

The plan sequences Paper 1 first (highest leverage, fastest repackaging), Paper 2 second (depends on methodology v1), and Paper 3 as optional once Papers 1 and 2 are in review. Each paper has a Prepare → Draft → Review → Submit cycle. Dates are anchored to *submission*, not publication; publication follows ~12 months later per venue norms.

### Phase 0 — Shared preparation (before any paper is drafted)

- [ ] **P0.1** Pick the target venue for Paper 1 between *IEEE Software* and *ACM Computing Surveys*. Decision criterion: IEEE Software is faster and friendlier to practitioner-oriented synthesis work; CSUR has higher citation weight but longer review cycles and stricter survey-methodology expectations. Default: IEEE Software unless specified otherwise.
- [ ] **P0.2** ~~Pick the target venue for Paper 2 between *Empirical Software Engineering* and *Journal of Systems and Software*.~~ **Superseded 2026-04-09 by the pre-registration design.** Paper 2 now targets **EMSE Registered Reports** as the primary path, with ACM TOSEM Registered Reports as the rigor fallback and IEEE Software (non-Registered-Reports) as the speed fallback. The decision can be revisited in May 2026 after the Stage 1 manuscript is drafted, when the trade between Stage 1 review time and editorial commitment to publish becomes concrete. See "The pre-registration design for Paper 2" section above.
- [ ] **P0.3** Confirm ORCID, institutional affiliation line, and acknowledgements boilerplate for all three papers. If no current institutional affiliation, use "Independent researcher" and list prior affiliations in the bio.
- [ ] **P0.4** Set up a BibTeX master file that merges the citations already in the 2026 Zenodo preprint with new citations added during the Open Honest methodology drafting.
- [ ] **P0.5** Draft a standard conflict-of-interest disclosure paragraph and a standard author-contribution statement to reuse across all three papers.
- [ ] **P0.6** Decide the preprint posture: arXiv (cs.SE), Zenodo (update the existing DOI with new versions), or both. Default: arXiv cs.SE for new papers; keep the original preprint on Zenodo as-is.

### Phase 1 — Paper 1: the 18-dimension framework

**Working title:** "An 18-Dimension Audit Framework for Enterprise Software Maturity"
**Target venue:** IEEE Software (default) or ACM Computing Surveys
**Source material:** `the methodology documents (see ../README.md)` Section 4 (all 18 dimension entries), plus the `iridescent-moseying-pie.md` working analysis

Tasks:

- [ ] **1.1** Produce a compact outline (target 6–8 pages for IEEE Software, 25–40 pages for CSUR) from the Section 4 catalog. Each dimension gets 1 paragraph describing what it measures, 1 paragraph citing its compliance-framework mapping, and 1 sentence on the discriminating marker.
- [ ] **1.2** Write the introduction that positions the 18 dimensions as a synthesis of NIST 800-53, OWASP ASVS, DORA, OSFI B-13, FFIEC, SIG, AICPA, CISA, CNCF, and Gartner. The synthesis framing is the novel contribution; the dimensions themselves are the sum of prior art that no other document has gathered into one set.
- [ ] **1.3** Write the related work section. Map the 18 dimensions to the source frameworks cell by cell. A table showing which source contributes which dimension is the load-bearing figure of the paper.
- [ ] **1.4** Write the method section explaining how the dimensions were selected and why the list is closed at 18 (not 17, not 20). Reference the slop audit methodology document as the operational companion.
- [ ] **1.5** Write the evaluation section. Cite Wasserman 2026 as the natural experiment that validates the framework's discriminating power. Do not re-run experiments; the paper is a synthesis, not an empirical study.
- [ ] **1.6** Write a discussion section covering the framework's limits (applicability to AI-assisted development specifically, not traditional waterfall SDLC contexts) and its relationship to certification (referencing the Honest Foundation and Certified Honest Practitioner without making the paper a marketing document).
- [ ] **1.7** Cold-read pass. Adam reviews the full draft.
- [ ] **1.8** Pre-submission peer read. Send to 2 or 3 friendly readers (candidates: Christian Lavoie, David Norfolk, one additional senior SE academic) for informal review. Incorporate feedback.
- [ ] **1.9** Format to target venue's template. IEEE Software uses a specific LaTeX class and has a 6–8 page limit including figures; CSUR has no hard page limit but expects depth. Format work is easier to do late than early.
- [ ] **1.10** Submit. Record submission date, venue, reviewer form fields, and any nominated reviewers in `submissions.md` (to be created in this directory).
- [ ] **1.11** Preprint: post to arXiv cs.SE on the same day as submission, with a note linking to the Zenodo preprint as the empirical foundation.
- [ ] **1.12** Track the review cycle. Expected first decision: 3–5 months for IEEE Software, 6–9 months for CSUR.

### Phase 2 — Paper 2: independent third-party instrument validation (revised 2026-04-11)

**[This section supersedes the within-subject design below. The old task list is preserved for audit history but is no longer active.]**

**Working title:** "A Pre-Registered Within-Subject Longitudinal Replication of the Slop-Audit Methodology Across Three Methodology-Exposure Conditions"
**Target venue:** EMSE Registered Reports (primary), ACM TOSEM Registered Reports (rigor fallback), IEEE Software (speed fallback). See "The pre-registration design for Paper 2" section above for the venue rationale.
**Authors (planned):** Adam Z. Wasserman, Shawna Staff. Co-author consent process documented in `paper-2-coauthor-brief-shawna.md`. Joint Adam/Shawna patent on IAM disclosed up front per the pre-registration document.
**Source material:** `paper-3-instrument-validation-preregistration.md` (the locked pre-registration), `the methodology documents (see ../README.md)` (the methodology under test, frozen at the version pinned in the pre-registration), `../validation/protocol.md`, the audit results once produced
**Prerequisites:**

1. The pre-registration document must be timestamped via Zenodo before any audit data is collected. Target: 2026-04-09 (tonight).
2. Shawna Staff's consent to co-authorship and to authorizing IAM Go (v2) for use as study material. Without Shawna's IP authorization for IAM Go (v2), the design's main protection against the author-observer confound is lost and the paper falls back to a much weaker single-codebase format. Target: tonight or within a few days.
3. The independent auditor must be identified and committed before the audit runs. Current candidates: the audit partner's principals (in their currently-unaffiliated window), with Daniel Beauchemin as procedural witness. Target: confirmed by 2026-04-30.
4. The `idd honest-conversion` branch must reach validation-readiness. Target: 2026-04-30 per `methodology/validation/protocol.md`.
5. NDAs in place between the auditor and the IP owners: Buckler for `idd honest-conversion`, Shawna for IAM Go (v2), Adam and Shawna jointly for IAM. Target: by audit start date.

Tasks (rewritten 2026-04-09 to reflect the pre-registration design):

**2.1 Pre-registration phase (April 2026)**

- [ ] **2.1.1** Adam fills in the predicted dimension scores in `paper-3-instrument-validation-preregistration.md` §3.1 (54 predictions: 18 dimensions × 3 codebases). Approximately 30–60 minutes of focused work. Once filled in, the predictions are locked and cannot be edited.
- [ ] **2.1.2** Adam fills in the predicted Layer 1 indicator outcomes in §3.2 (51 predictions: 17 indicators × 3 codebases). Approximately 20–30 minutes.
- [ ] **2.1.3** Adam writes the one-sentence overall pattern prediction in §3.3.
- [ ] **2.1.4** Adam sets the numeric thresholds in §4 falsification criteria (suggested defaults: 14/18 for the intervention effect-size, 12/18 for the baseline-floor, 4/18 for the auditor-agreement criterion).
- [ ] **2.1.5** Shawna reviews the consent brief at `paper-2-coauthor-brief-shawna.md`, makes a yes/no decision on co-authorship, and (if yes) authorizes IAM Go (v2) for use as study material.
- [ ] **2.1.6** Adam sends the predictions to Shawna privately before posting (per the consent brief commitment that Shawna sees the predictions before her name is attached to them).
- [ ] **2.1.7** Adam timestamps the finalized pre-registration via Zenodo, mints the DOI, and adds the DOI to §8 of the pre-registration document.
- [ ] **2.1.8** Adam commits and pushes the timestamped pre-registration to the Open Honest repository.
- [ ] **2.1.9** Adam sends the Zenodo DOI to the audit partner's principals with the audit ask (explicitly *before* any commercial license discussion advances), and to Daniel Beauchemin with the procedural witness ask.

**2.2 Stage 1 manuscript phase (April–May 2026, in parallel with audit preparation)**

- [ ] **2.2.1** Draft the Stage 1 manuscript by expanding the pre-registration document into a full EMSE-formatted protocol paper. Add: introduction, related work (citing Paper 1 as the natural experiment whose author-observer confound this paper addresses), motivation (why a within-subject longitudinal design is methodologically stronger than the original between-subjects natural experiment), threats-to-validity discussion, and the EMSE Springer bibliography format. The pre-registration's predictions, falsification criteria, and analysis plan transfer directly into the Stage 1 manuscript without modification.
- [ ] **2.2.2** Pre-submission peer read of the Stage 1 manuscript. Same friendly readers as Paper 1 (Christian Lavoie, David Norfolk, plus one additional senior SE academic). Focus on whether the design holds up under sympathetic scrutiny before facing real reviewers.
- [ ] **2.2.3** Format to EMSE's Springer template (`sn-jnl` LaTeX class).
- [ ] **2.2.4** Submit Stage 1 manuscript to EMSE Registered Reports track. Cover letter explicitly cites the Zenodo pre-registration DOI, explains that this is a pre-registered replication addressing the Paper 1 author-observer confound, and discloses the joint Adam/Shawna patent on IAM as a financial interest.
- [ ] **2.2.5** Wait for editorial decision on Stage 1 (typical: 2–3 months for EMSE). Possible outcomes: in-principle acceptance (IPA), revise and resubmit, reject. IPA is the binding commitment to publish Stage 2 results regardless of outcome.

**2.3 Audit phase (May–June 2026, gated on IPA and validation-readiness)**

- [ ] **2.3.1** Independent auditor receives the methodology document at the version pinned in the pre-registration, the three codebases under the appropriate NDAs, and the Section 5 walkthrough. Auditor does NOT receive the pre-registration's predictions (the audit must be blind to the predictions).
- [ ] **2.3.2** Auditor performs the audit on each of the three codebases per the Section 5 walkthrough (~5 days per codebase, ~15 working days total).
- [ ] **2.3.3** Auditor produces the dimension scorecard for each codebase plus the Slop Report per Section 6.
- [ ] **2.3.4** Daniel Beauchemin (procedural witness) signs the chain-of-custody attestation: confirms that the predictions were locked before the audit was run, that the methodology version was pinned, and that the audit followed the documented procedure.
- [ ] **2.3.5** Adam and Shawna receive the audit results. Apply falsification criteria to the predictions vs results comparison. Determine which (if any) of the six pre-registered hypotheses were falsified.

**2.4 Stage 2 manuscript phase (June–August 2026)**

- [ ] **2.4.1** Draft the Stage 2 manuscript by extending the Stage 1 manuscript with the results section, the analysis section (predictions vs results, including any falsifications), the discussion section, and the conclusions. The introduction and methods sections from Stage 1 transfer with minor edits.
- [ ] **2.4.2** Shawna writes the section describing her own development practice across the three codebases (her independence on IAM Go v2, her role in the joint IAM patent collaboration, her ~98% autonomy on `idd honest-conversion` with the 2% non-autonomous portion characterized explicitly). This is the load-bearing first-person account that the design's credibility depends on.
- [ ] **2.4.3** Apply the redaction protocol to any code excerpts before they appear in the manuscript: Shawna sees and approves every excerpt; patent-protected portions are excluded entirely; anything either author wants withheld is replaced with a description.
- [ ] **2.4.4** Pre-submission peer read of the Stage 2 manuscript. Same friendly readers.
- [ ] **2.4.5** Submit Stage 2 manuscript to EMSE per the IPA terms. Stage 2 review focuses on whether the study followed the protocol; it does not re-litigate the design.
- [ ] **2.4.6** Post Stage 2 manuscript to arXiv cs.SE on the same day as the EMSE Stage 2 submission.
- [ ] **2.4.7** Track the Stage 2 review cycle. Expected first decision: 1–3 months at EMSE under IPA terms.

**2.5 Negative-result protocol (executed only if a falsification criterion is met)**

If any of the pre-registered falsification criteria is tripped by the audit results:

- [ ] **2.5.1** Do not edit the predictions or the falsification criteria. The pre-registration is a public commitment.
- [ ] **2.5.2** Report the falsification in the Stage 2 manuscript as the primary finding. A negative result is a publishable finding under Registered Reports because the IPA commits the editor to publish regardless of outcome.
- [ ] **2.5.3** Discuss what the falsification implies for the methodology. Possible interpretations: the methodology has a smaller effect than claimed (criterion 2 falsified); the baseline practice is already strong enough that the methodology's marginal value is low (criterion 3 falsified); the supervisory context has a measurable independent effect (criterion 4 falsified); the methodology's scoring criteria are not yet reliably transferable to independent assessors (criterion 5 falsified); the in-context measurement is biased relative to the independent measurement (criterion 6 falsified). Each interpretation has different implications for subsequent papers and for the certification commercial model.
- [ ] **2.5.4** Adjust the Honest Foundation governance and the the audit partner licensing pitch to reflect the negative finding. The certification model can survive a negative result on Paper 2 if the discussion section is honest about the implications and proposes the methodology refinements that would address the failure.

**2.6 Independent of EMSE: the Zenodo preprint of the pre-registration is its own deliverable**

The Zenodo-timestamped pre-registration document is independently citable from the moment the DOI is minted. Even if the EMSE Registered Reports submission is rejected, delayed, or withdrawn, the Zenodo DOI carries integrity-protection value at any future venue submission and in the Honest Foundation governance documents. The pre-registration is an asset on its own.

### Phase 3 — Paper 3 (optional): the four-layer model as a theoretical contribution

**Working title:** "A Four-Layer Model for Software Architecture Assessment under AI-Assisted Development"
**Target venue:** IEEE Transactions on Software Engineering (high impact, slow) OR a workshop at ICSE / FSE / ASE (faster, lower impact)
**Decision point:** after Papers 1 and 2 are in review. If they land well, Paper 3 is a citation-chain completion worth writing. If reviewers on Paper 2 already absorb the four-layer contribution, Paper 3 may be redundant and can be dropped.

Tasks deferred until the Paper 2 first-round reviews return.

### Phase 4 — Citation chain maintenance

- [ ] **4.1** Once Paper 1 is accepted, update `../../administrator/enablement/04-methodology-author-credibility.md` to reference the acceptance with the real DOI.
- [ ] **4.2** Once Paper 2 is accepted, update the Certified Honest Practitioner marketing materials and the Foundation Charter references.
- [ ] **4.3** At each acceptance, notify standards bodies (NIST, OWASP, OSFI, AMF) informally that the peer-reviewed citation is available for their consideration when drafting guidance.
- [ ] **4.4** Add the accepted papers to the `../../governance/` reading list as the formal academic anchors of the framework.

### Cadence and priority (updated 2026-04-09)

The original cadence ranked Paper 1 first because it was the shortest and the highest-hit-rate. The pre-registration design changes this. **Paper 2's pre-registration has a hard tonight deadline that Paper 1 does not have**, because the integrity of the pre-registration depends on the predictions being timestamped before any audit data is collected, and the audit becomes possible on 2026-04-30. If the pre-registration is not posted before the audit runs, the design's main protection is forfeited and Paper 2 collapses to a much weaker single-codebase format.

The revised priority order:

- **Paper 2 pre-registration: tonight (2026-04-09).** Hard deadline. The Zenodo timestamp must precede any audit. This is the highest-priority single action item in the entire publication program.
- **Paper 2 Stage 1 manuscript drafting: April–May 2026, in parallel with Paper 1.** The Stage 1 manuscript expands the pre-registration into a full EMSE-formatted protocol paper. Roughly two weeks of focused drafting effort.
- **Paper 1 drafting: April–June 2026.** Still high priority, still uses the most complete source material, still targets a high-hit-rate venue. The reframe is that Paper 1 is no longer the schedule-driver because Paper 2's pre-registration is. Paper 1 drafting proceeds in parallel with Paper 2 Stage 1 drafting and should still be the first paper *submitted* if drafting completes faster than Paper 2 Stage 1.
- **Paper 2 audit: May or June 2026, gated on EMSE IPA and on `idd honest-conversion` validation-readiness.** Cannot begin until both gates open. Run the audit promptly when both are open; do not wait.
- **Paper 2 Stage 2 manuscript: June–August 2026.**
- **Paper 3 (optional, the four-layer model paper): gated on Paper 2 Stage 2 review feedback.** Do not draft until Stage 2 reviews land.
- **Framework extension papers (Paper 4 onward): gated on real engagement-driven gaps.** See "The framework extension paper cadence" section above for the operational policy.

**All papers share the same working analysis file and the same friendly-reader network.** The marginal cost of each subsequent paper is significantly lower than the cost of the first one from scratch. The first paper submitted (probably Paper 1 if drafting goes well) absorbs most of the friendly-reader feedback cycle's overhead; Papers 2 and 3 inherit a calibrated reader network.

**The publication-program critical path** is now:

```
Tonight 2026-04-09:    Pre-registration timestamped via Zenodo
April–May 2026:        Stage 1 manuscript drafting (Paper 2) + Paper 1 drafting in parallel
2026-04-30 onward:     idd honest-conversion validation-ready
May–June 2026:         Submit Paper 1 to IEEE Software; submit Paper 2 Stage 1 to EMSE
June–August 2026:      EMSE Stage 1 review; Paper 1 review; Paper 2 audit (after IPA)
August–October 2026:   Paper 2 Stage 2 manuscript drafting and submission
Late 2026 / early 2027: Paper 1 acceptance, Paper 2 Stage 2 acceptance
2027:                   Paper 3 drafting (if Stage 2 reviews indicate a four-layer model paper would add value)
2027–2028:              First framework extension paper (4.19 Operational handoff readiness)
```

This is a 12–18 month schedule for the first wave of credibility material to be in print. The pre-registration timestamp tonight is the cheapest single action in the schedule and the one with the highest leverage on the entire program: it converts Paper 2 from "another natural-experiment-style paper that reviewers will discount because of the author-observer confound" into "a pre-registered replication study that explicitly addresses the confound." That conversion is what makes the citation chain credible to enterprise procurement and audit committees in 2027 and beyond.

### Where operational tracking lives

This file is the **strategy + action plan**. Once drafting begins, per-paper operational tracking (submission dates, reviewer feedback, revision cycles, reviewer form responses) goes into sibling files in this directory:

- `submissions.md` — one entry per submission, with venue, date, status, and tracking ID
- `paper-1-18-dimensions/` — drafts, figures, friendly-reader feedback
- `paper-2-methodology/` — same structure
- `paper-3-four-layer-model/` — created only if Phase 3 is activated
