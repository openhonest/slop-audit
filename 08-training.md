## 8. Training

This section defines the training pathway for new assessors. It is drafted in two passes. The **structural pass** (this v0) specifies the curriculum levels, prior-experience requirements, required reading, practical exercises, and sign-off criteria, all drawn from material already fixed in Sections 2, 4, and 7. The **calibration-density pass** (v1, pending) will specify which dimensions require extra practice density and will set final reliability thresholds per dimension. The calibration-density pass cannot be drafted until the Section 7 validation cycle has been run, because it depends on knowing which dimensions produce the most cross-rater disagreement in practice. Everything in the structural pass is sufficient to begin training the first cohort; the calibration-density pass refines the training rather than gating it.

**Canonical curriculum reference.** The full curriculum artifact plan — the two-track structure (Track 1 Slop Audit, Track 2 Live Code Audit), the per-level diagnostic interviews, the four-lens self-assessment exercise, the prerequisite knowledge and experience tables, the per-level measurable outcomes, and the estimated ~60 deliverable artifacts for a complete v1 curriculum — lives in `curriculum/README.md` and is authoritative for anything not explicitly restated here. Section 8 of this methodology document restates *what the methodology needs from the curriculum* (the curriculum-level assignments of the four layers, the certification criteria that bind the methodology to the curriculum, and the cross-rater calibration protocol that ties both together). The curriculum README restates *what the curriculum needs to produce* (the artifact inventory, the diagnostic interviews, the drafting priority). When the two documents disagree, the curriculum README is authoritative on training delivery and this section is authoritative on the methodology's reliability and validation properties. The two documents should converge as both mature.

### 8.1 Curriculum tracks and their relationship to the four-layer model

The methodology has four layers of judgment (Section 2). The curriculum has two tracks, with four levels each, per `curriculum/README.md`. **Track 1 (Slop Audit)** teaches Layers 1, 2, and 3 — the Phase 0 work — and produces assessors who can run a complete Phase 0 engagement. **Track 2 (Live Code Audit)** teaches Layer 4 — the Phase 1 work — and produces senior reviewers who can lead the real-time architectural review during an escape pod build. The two tracks are independent in general but linked at the prerequisite level: Track 2 LV2 requires Track 1 L2 because the slop audit teaches the recognition vocabulary that live code audit builds on.

| Track | Level | Layers taught | Typical training duration | Primary certification criterion |
|---|---|---|---|---|
| Track 1 | **L1 Apprentice** | Layer 1 only | 1–2 days + 2 supervised runs | Exact agreement on L1 indicator values with a reference assessor |
| Track 1 | **L2 Practitioner** | Layer 2 (plus L1) | ~1 week + 3 supervised audits | Agreement with a reference assessor on ≥16 of 18 dimensions at the artifact-finding level |
| Track 1 | **L3 Lead** | Layer 3 (plus L1, L2) | ~2–3 weeks + 5 supervised audits | Ability to lead a complete Phase 0 engagement independently, with peer review confirming marker-level inter-rater reliability |
| Track 1 | **L4 Trainer** | Training delivery | 6–12 months active practice as L3 + ≥10 delivered client engagements | Has trained ≥3 assessors to L2 with ≥90% inter-rater agreement on a calibration codebase |
| Track 2 | **LV1 Trainee** | Layer 4 recognition vocabulary | 2–4 weeks guided reading + practice | Identifies ≥80% of seeded antipatterns in a calibration codebase |
| Track 2 | **LV2 Pair** | Layer 4 pairing with senior reviewer | 2–3 months guided pairing | Pairs effectively with an LV4 reviewer for ≥40 hours, with ≥70% of LV2 observations rated valuable |
| Track 2 | **LV3 Reviewer** | Layer 4 supervised leadership on bounded modules | 6–12 months active practice | Leads ≥10 hours of live review per week; reviewed work passes Layer 2 audit on delivery |
| Track 2 | **LV4 Architect** | Layer 4 unsupervised leadership on production engagements | 18+ months active practice | Leads a full Phase 1 escape pod build that passes 18-of-18 audit dimensions on delivery |

The Track 1 L1 → L2 → L3 progression is the Phase 0 certification ladder. An L3 Lead can run a complete Phase 0 engagement (Layers 1+2+3) without supervision. L4 Trainer sits above L3 as a training-delivery competency rather than an additional layer of judgment: an L4 Trainer is an L3 who has also been certified to train new L1/L2/L3 assessors and who can run the cross-rater calibration exercise as its administrator. The Track 2 LV1 → LV2 → LV3 → LV4 progression is the Phase 1 senior reviewer ladder, and it is an apprenticeship model that cannot be accelerated through documentation alone because the underlying skill (elite architectural judgment, per Wasserman 2026 §5.3) does not transfer through training alone. A full LV4 takes multiple years and requires substantial prior enterprise experience as a prerequisite.

Detailed prerequisite tables (knowledge, experience, activity prerequisites, per-level diagnostic interview questions) for every level on both tracks live in `curriculum/README.md` §"Levels and prerequisites" and are not duplicated here to prevent divergence.

### 8.2 L1 Apprentice (Layer 1 only)

**Goal.** The trainee can run the twenty Layer 1 indicators against an arbitrary git repository and produce the quantitative panel from Section 3.3 without assistance.

**Prior experience required.** Professional familiarity with git, basic shell scripting (enough to run a script and interpret its output), and one mainstream programming language well enough to identify dead code with help from a static analyzer. No enterprise software background required. This is the lowest-barrier certification level and is explicitly designed so that a junior developer can earn it.

**Required reading.** Section 1 (Purpose and scope), Section 2 (four-layer model, through Section 2.5 composition), Section 3 (Layer 1 quantitative git-history assessment, all subsections), the Wasserman 2026 paper §4.7 and §4.8 (the indicator definitions), and the `research/slop-audit-layer1.sh` reference script (when it exists; currently pending per the tooling layer of the TODO list below).

**Practical exercises.**

1. **Indicator walkthrough on a synthetic repository.** The trainee runs each of the twenty indicators manually on a small purpose-built repository where the expected values are known. This exercise surfaces misunderstandings about what each indicator measures before the trainee touches a real codebase.
2. **Positive control run.** The trainee runs the full Layer 1 panel against the `idd honest-conversion` branch (the validation positive control, per Section 7.1) and compares the output against the reference panel. The expected result is a high-confidence Structured classification.
3. **Negative control run.** The trainee runs the full Layer 1 panel against the validation negative control branch and compares against the reference panel. The expected result is an Unstructured or Mixed classification.
4. **Unknown codebase run.** The trainee runs the full Layer 1 panel against an unknown codebase (one the reference assessor has scored but the trainee has not seen) and produces the panel independently. This is the certification exercise.

**Certification criterion.** Exact agreement on all twenty indicator values with the reference assessor on the unknown codebase. Layer 1 is mechanical; any disagreement is either a methodology bug or a trainee error, and both must be resolved before certification is granted. A Layer 1 disagreement on a calibration codebase triggers a methodology review of the affected indicator.

**Time to competency.** 1–2 days of directed study plus 2 supervised runs. The L1 certification is the shortest of the four tracks and is designed to be earnable in a week of part-time effort.

### 8.3 L2 Practitioner (Layers 1 + 2)

**Goal.** The trainee can run a complete Layer 2 artifact inspection across all 18 dimensions, score each dimension present / partial / absent / not applicable based on cited evidence, and produce the per-dimension scorecard portion of a Slop Report without assistance.

**Prior experience required.** At least 3 years of professional software development experience across at least two of the six target languages (Python, TypeScript, Java, C#, Go, Ruby). The assessor must be able to read code in the target codebase well enough to locate the relevant files and recognize the artifacts described in each dimension's Layer 2 inspection procedure. Familiarity with common enterprise architectures (multi-tier web applications, API-plus-database, multi-tenant SaaS) is required because the Layer 2 evidence is distributed throughout these architectures. No prior audit or compliance experience is required.

**Required reading.** Everything in the L1 reading list, plus Section 4 in full (all 18 dimensions), Section 5 (the operational walkthrough), Section 6 (the Slop Report template), the Honest Code principles document (for context on what the dimensions are protecting against), and the compliance framework mappings cited in each Section 4 dimension header (SOC 2, NIST 800-53, OSFI B-13, OWASP ASVS, ISO/IEC 25010 — the trainee does not need to memorize these but must recognize the terms and know where in the dimension entries to find them).

**Practical exercises.**

1. **Dimension walkthrough on a synthetic repository.** For each of the 18 dimensions, the trainee runs the Layer 2 inspection procedure against a small purpose-built repository where the expected score is known. This exercise uses eighteen small repositories, not one large one, so that the trainee practices recognizing each dimension's artifacts without interference from unrelated code.
2. **Quick-reference table drill.** The trainee completes the Section 4 quick-reference table from memory (threshold, fastest kill check, disqualifier, time budget per dimension). This exercise is timed: the L2 Practitioner should be able to complete all 18 rows in under 30 minutes. The purpose is to make the quick reference a working mental model, not a document the trainee must consult during an audit.
3. **Three supervised audits.** The trainee runs three complete Layer 2 audits on real codebases (not synthetic), under the direct supervision of an L3 Lead or higher. The supervisor reviews every dimension score before the report is finalized. Discrepancies are debriefed immediately so the trainee learns from each one.
4. **Certification audit.** The trainee runs a complete Layer 2 audit on an unknown codebase that the reference assessor has independently scored. This is the certification exercise. The trainee's scorecard is compared against the reference scorecard at the artifact-finding level.

**Certification criterion.** Agreement with the reference assessor on at least 16 of 18 dimensions on the certification audit, measured at the artifact-finding level (meaning: the trainee cites the same evidence and reaches the same score, not merely agrees on the score by coincidence). Disagreements on 3 or more dimensions require a calibration revision and a second certification attempt.

**Time to competency.** Approximately one week of directed study plus three supervised audits plus the certification audit. Total elapsed time varies by audit availability; the didactic material itself fits in one working week.

### 8.4 L3 Lead (Layers 1 + 2 + 3)

**Goal.** The trainee can lead a complete Phase 0 engagement independently, including the Layer 3 marker assessment, and can produce a full Slop Report with executive summary, per-dimension scorecard, flagged-for-Phase-1 section, and Escape Pod Proposal draft. The L3 Lead can also run the Day 5 debrief with the client's technical lead and CIO without requiring a more senior assessor in the room.

**Prior experience required.** L2 Practitioner certification plus at least 5 years of professional software development experience with meaningful exposure to at least three architectural patterns from the Layer 4 vocabulary (dependency injection, event sourcing, state machines, circuit breakers, pattern combinations). The additional experience is needed because Layer 3 markers require the trainee to recognize qualitative properties (pattern fitness, architectural coherence, prescriptive versus descriptive language) that a junior assessor cannot reliably recognize even with the markers in hand.

**Required reading.** Everything in the L2 reading list, plus the full Honest Code book (not just the principles document), the contract testing methodology document (`contract-testing-methodology.md`), and Wasserman 2026 §5.3 (the definition of elite architectural judgment, which is what Layer 3 must *not* cross over into). The L3 Lead must understand the Layer 3 / Layer 4 boundary well enough to refuse to cross it during an audit.

**Practical exercises.**

1. **Layer 3 marker drill.** For each of the 18 dimensions, the trainee scores each Layer 3 marker present / partial / absent on a set of calibration codebases chosen to exercise the markers. This is the highest-density exercise in the curriculum and will receive extra attention in the v1 calibration-density pass of this section.
2. **The Layer 3 / Layer 4 boundary exercise.** The trainee is shown 10 qualitative observations drawn from real audits and must categorize each as "scoreable by Layer 3 markers" or "Layer 4 only, flag for Phase 1." The purpose is to train the reflex of *stopping* at the Layer 3 boundary rather than drifting into Layer 4 judgment. Drifting across this boundary is the single largest methodology violation at this level and is the most important behavior to train.
3. **Five supervised audits.** The trainee leads five complete Phase 0 audits (Layers 1+2+3) under the direct supervision of another L3 Lead or higher. The supervisor reviews the full Slop Report before it is delivered to the client. The supervisor attends the Day 5 debrief for the first three of these audits; the trainee runs the debrief alone for audits 4 and 5 (with the supervisor reviewing the debrief recording or notes afterwards).
4. **Certification audit.** The trainee runs a complete Phase 0 audit on an unknown codebase that another L3 Lead has independently scored. The trainee produces the full Slop Report including the Layer 3 marker scores.

**Certification criterion.** The trainee's Slop Report must (a) agree with the reference Slop Report on at least 16 of 18 dimension overall scores, (b) agree on at least 80% of Layer 3 marker scores across the dimension catalog, (c) not misclassify any observation as Layer 3 when it belongs to Layer 4 (the boundary-crossing test), and (d) produce an executive summary and Escape Pod Proposal that the reference assessor judges "deliverable to a client without revision." Failing any of these criteria triggers a re-test after additional supervised audits.

**Time to competency.** Approximately 2–3 weeks of directed study plus five supervised audits plus the certification audit. The long end of the range reflects the additional Honest Code reading and the boundary-training exercise, both of which take longer to internalize than the L1 and L2 material.

### 8.5 Track 1 L4 Trainer (training delivery certification)

**Goal.** The L4 Trainer can train new L1, L2, and L3 assessors end to end; can run cross-rater calibration exercises as their administrator; can diagnose trainee failures and apply remedial exercises; and can certify candidates at L1, L2, and L3 without escalation to the methodology author.

**Why this level exists.** The L3 Lead can run an audit but cannot necessarily *teach* another person to run an audit. Teaching a mechanical-plus-qualitative skill requires understanding how adults learn technical material, understanding the most common trainee error patterns, and knowing how to give corrective feedback that improves the trainee's mental model rather than just correcting the immediate mistake. L4 is the training-delivery competency on top of the audit competency. Without L4 Trainers, the curriculum cannot scale past the number of assessors the methodology author can personally supervise, which is the exact scaling bottleneck the methodology is designed to relieve.

**Prior experience required.** L3 Lead certification plus at least 10 delivered client Phase 0 engagements plus demonstrable experience training another developer in any structured technical skill (formal mentorship over months, structured onboarding of a new hire, or equivalent). The training-experience requirement is not optional: a candidate who has audited extensively but has never taught another person to audit is an L3 Lead, not an L4 Trainer.

**Required reading.** Everything in the L3 reading list plus at least one book on adult technical learning (recommended: Ericsson's *Peak* on deliberate practice, Willingham's *Why Don't Students Like School?* on cognitive load, or equivalent peer-reviewed material). The specific book is less important than the candidate understanding the underlying concepts: cognitive load, scaffolding, expert blind spots, the transfer-of-learning problem, and the difference between "I can do this" and "I can teach this."

**Practical exercises.**

1. **Training-shadowing exercise.** The candidate shadows an existing L4 Trainer (or the methodology author) through a complete L2 training cycle for a real trainee, including the diagnostic interview, the didactic delivery, the supervised audits, and the certification exercise. The candidate observes, takes notes, and debriefs the trainer after each session.
2. **Training-leading exercise.** The candidate leads a complete L1 Apprentice training cycle for a real trainee, with an existing L4 Trainer (or the methodology author) providing oversight but not delivering the material. The candidate runs the diagnostic interview, delivers the didactic material, supervises the practice runs, and conducts the certification exercise. The oversight L4 reviews the candidate's work after the certification.
3. **Cross-rater exercise administration.** The candidate administers a full cross-rater calibration exercise against a known calibration codebase, coordinates the two assessors (the trainee and the reference), adjudicates disagreements, classifies each disagreement as trainee error / reference error / genuine ambiguity / boundary drift, and produces the calibration report.
4. **Remedial exercise design.** The candidate is given a synthetic trainee error log (a sequence of dimension scoring errors with cited evidence) and must design a remedial exercise targeted at the underlying mental-model gap rather than at the surface error. The exercise is reviewed by an L4 Trainer for pedagogical soundness.

**Certification criterion.** The candidate has trained at least three assessors to L2 Practitioner certification with ≥90% inter-rater agreement on their certification exercises. This is the canonical L4 measurable outcome per `curriculum/README.md`.

**Time to competency.** 6–12 months of active practice as L3 Lead with directed training delivery experience. L4 is partly an admissions filter rather than a training program per se: the candidate arrives at L4 already doing most of what L4 requires, and the curriculum provides the structured framework for what they already know.

### 8.6 Track 2 Live Code Audit (LV1 Trainee → LV4 Architect)

**Goal.** The senior reviewer can perform the elite architectural judgment work that Layer 4 requires: recognizing hidden couplings, pattern grime, misapplied patterns, subtle anti-patterns, and the architectural decisions whose consequences only manifest under operational stress. LV4 reviewers are the only assessors who can sustain the full Phase 1 architectural review during an escape pod build.

**Prior experience required.** L3 Lead certification plus at least 8 years of professional software development experience including at least one year in a senior architect or tech lead role, ideally on a system that has gone through at least one major scaling event or security incident. The experience requirement is the bottleneck of the entire curriculum: the LV progression cannot be accelerated past the underlying experience, which is why LV certification is gated on years of practice rather than weeks of study.

**Required reading.** Everything in the L3 reading list, plus the original sources cited in the Layer 4 questions of each Section 4 dimension (especially Brooks *The Mythical Man-Month* Ch. 4 for architectural philosophy, Baldwin & Clark *Design Rules* for modularity, Ford/Parsons/Kua *Building Evolutionary Architectures* for fitness functions, Feitosa & Avgeriou on Pattern Grime, and Tornhill *Software Design X-Rays* for hotspot analysis).

**The LV progression.** The four levels of Track 2 per `curriculum/README.md`:

- **LV1 Trainee** is the prerequisite-knowledge level. The trainee has read the Honest Code book, the contract testing methodology, the honest-code-principles document, and the Layer 4 question sets in Section 4; can recognize the Honest Code patterns and anti-patterns in static review; and can articulate why each Layer 4 question requires elite judgment rather than specified markers. The LV1 certification measurable outcome (per curriculum README) is identifying ≥80% of seeded antipatterns in a calibration codebase containing known violations. LV1 is the *entrance* to the apprenticeship, not a certification to run live reviews on production code.
- **LV2 Pair** is the pairing level. The trainee pairs with an LV4 reviewer during real-time AI-assisted development on a production engagement. The trainee observes the senior reviewer catching issues in live code review, asks questions about why each issue matters, and builds the pattern-recognition vocabulary through repeated exposure. Per curriculum README the LV2 measurable outcome is ≥40 hours of effective pairing with an LV4 with ≥70% of LV2 observations rated valuable by the LV4. Typical duration: 2–3 months of active pairing.
- **LV3 Reviewer** is the supervised-leadership level. The trainee leads the Layer 4 review on bounded modules during a Phase 1 engagement, with an LV4 reviewer available for escalation but not in the room for every review session. The trainee's reviews are audited weekly by the LV4 reviewer. Per curriculum README the LV3 measurable outcome is leading ≥10 hours of live review per week with the reviewed work passing Layer 2 audit on delivery. Typical duration: 6–12 months.
- **LV4 Architect** is the unsupervised-leadership level. The reviewer leads the full Layer 4 review on a production Phase 1 engagement without supervision. Per curriculum README the LV4 measurable outcome is leading a full Phase 1 escape pod build that passes 18-of-18 audit dimensions on delivery. LV4 certification is attested by two other LV4 reviewers who have worked with the trainee on at least one completed engagement each. Typical duration: 18+ months of active practice.

**Certification criterion.** Each LV level has its own certification criterion, attested by a reviewer one level above, with the measurable outcomes as stated in the curriculum README's Track 2 table. LV4 certification specifically requires (a) completion of at least three Phase 1 engagements as the sole Layer 4 reviewer, (b) attestation from two other LV4 reviewers who have directly observed the trainee's work, and (c) no major architectural regressions in the trainee's work on those engagements (as measured by the Section 7 "would the auditor agree" test applied retrospectively).

**Why Track 2 exists separately from Track 1.** Track 2 is not a continuation of the Track 1 curriculum; it is a parallel track that happens to require Track 1 L2 as a prerequisite. Track 1 is designed for the Phase 0 engagement model: trained assessors running repeatable audits at scale. Track 2 is designed for the Phase 1 engagement model: senior architects running non-repeatable deep review on production builds. The two tracks exist separately because their economic models, delivery models, and certification rigor are different. Conflating them collapses the distinction between trainable judgment and elite judgment, which is the structural reason the four-layer model exists (Section 2.6).

### 8.7 Prior experience requirements summarized

| Track | Level | Years of dev experience | Audit/reviewer prerequisite | Architectural seniority |
|---|---|---|---|---|
| 1 | L1 Apprentice | 0+ | None | None |
| 1 | L2 Practitioner | 3+ | None | None |
| 1 | L3 Lead | 5+ | L2 Practitioner certification | Exposure to 3+ Layer 4 patterns |
| 1 | L4 Trainer | 5+ | L3 + 10 delivered engagements | Experience training another developer in a structured technical skill |
| 2 | LV1 Trainee | 5+ | Track 1 L2 Practitioner certification | Background architectural reading |
| 2 | LV2 Pair | 6+ | LV1 + active pairing | Pairing on production engagements |
| 2 | LV3 Reviewer | 7+ | LV2 + leadership on bounded modules | Sole reviewer on bounded modules |
| 2 | LV4 Architect | 8+ | LV3 + 3 completed Phase 1 engagements | Sole reviewer on production builds |

These are minimums. In practice, most L3 Leads will have 7–10 years of experience, most L4 Trainers will have 10+ years with demonstrable training-delivery experience, and most LV4 Architects will have 12+ years including a senior architect role. The detailed knowledge and experience prerequisites (diagnostic interview questions, specific activity prerequisites) live in `curriculum/README.md` §"Levels and prerequisites" and are authoritative on the per-level prerequisite structure.

### 8.8 Required reading (consolidated)

The full required reading list across all certification levels:

- **This methodology document** (Sections 1 through 8 and Annex B when it exists).
- **Wasserman, A. Z. (2026)**, *Process Discipline as the Key Variable in AI-Assisted Enterprise Software Development: A Natural Experiment.* Zenodo. (The published natural experiment from which this methodology is operationalized.)
- **Wasserman, A. Z.**, *Honest Code: Keep Your State Out of My Code.* (The canonical pattern catalog and the source of the Layer 3 pattern recognition vocabulary.)
- **Wasserman, A. Z.**, *Honest Code Principles* (`honest-code-principles.md`). (The compact working reference for the principles the book develops.)
- **Wasserman, A. Z.**, *Contract Testing Methodology* (`contract-testing-methodology.md`). (The verification approach for honest code; required for L3 and above.)
- **Brooks, F. P.** *The Mythical Man-Month*, 20th Anniversary Edition, Chapter 4 "Aristocracy, Democracy, and System Design." (Required for LV1 and above.)
- **Baldwin, C. Y. & Clark, K. B.** *Design Rules: The Power of Modularity* (MIT Press, 2000). (Required for LV2 and above.)
- **Ford, Parsons, Kua**, *Building Evolutionary Architectures* (O'Reilly, 2017/2023). (Required for LV2 and above.)
- **Tornhill, A.**, *Software Design X-Rays* (2018). (Required for LV2 and above.)
- **Feitosa, D. & Avgeriou, P.** Research on Pattern Grime. (Required for LV3 and above.)

The compliance framework references cited throughout Section 4 (SOC 2 TSC, NIST SP 800-53, OSFI B-13, OWASP ASVS, ISO/IEC 25010, Section 508, WCAG 2.2) are not required reading in full but the trainee must recognize the terms and know which dimensions map to which frameworks at the level of detail cited in each dimension header block.

### 8.9 Cross-rater calibration protocol

Every certification level above L1 includes a cross-rater calibration exercise. The protocol is:

1. Two assessors run the methodology independently on the same codebase, starting from the same raw repository clone.
2. Neither assessor sees the other's work until both are complete.
3. Scores are compared at the finest available grain: L1 indicator values (exact), Layer 2 dimension scores (per dimension), Layer 3 marker scores (per marker within each dimension).
4. Disagreements are classified as (a) trainee error, (b) reference error, (c) genuine ambiguity requiring methodology revision, or (d) boundary drift (trainee crossed the Layer 3 / Layer 4 boundary).
5. Trainee errors trigger remedial review of the affected dimension. Reference errors trigger correction of the reference scorecard. Genuine ambiguity triggers a methodology revision request. Boundary drift triggers remedial review of Section 2.4 and the Layer 3 / Layer 4 boundary exercise from the L3 curriculum.

The cross-rater exercise runs at certification time for each level, and thereafter at six-month intervals as drift detection. Assessors whose drift-detection score falls below the certification threshold for their level are required to complete a remedial exercise before returning to client work.

### 8.10 Recertification and drift detection

Certification is not permanent. Every L2, L3, and LV-level assessor re-runs the cross-rater calibration exercise every six months against a reference codebase. If the assessor's agreement rate drops below the certification threshold for their level, they are placed on remedial status until a second cross-rater exercise confirms recovery. The intent is not gatekeeping but quality control: methodology drift is inevitable in any human-interpretive instrument, and the drift must be detected before it shows up in client deliverables.

Recertification exercises are run on *new* reference codebases (not the same one used for initial certification) so that assessors cannot rehearse the specific codebase. The reference codebases come from the validation set (Section 7) rotated on a schedule.

### 8.11 Training material ownership

Training materials (slide decks, exercise repositories, reference scorecards, calibration codebases, certification audit scripts) are developed and owned by the Honest Foundation once the Foundation is established. In the interim, they are developed by the methodology author and licensed to the audit partner under the commercial administrator agreement; see `outreach/01-audit-partner-discussion.md` and the governance documents for the structural relationship. The Honest Foundation retains the right to withdraw the license from any commercial administrator whose training drift-detection results fall below the threshold for three consecutive six-month cycles, which is the structural protection against the commercial administrator slowly lowering training standards to sell more seats. This is the key Pink-Elephant-era mistake the governance is designed to prevent.

### 8.12 Calibration-density pass (v1, pending validation)

The v1 calibration-density pass will add, for each dimension in Section 4: the density of the exercise pool (how many calibration codebases practice this dimension specifically), the expected cross-rater agreement rate after training (which may be higher or lower than the default 4 of 5 markers depending on how the dimension behaves in practice), the specific trainee errors most commonly observed on this dimension, and the remedial exercises for each common error. The v1 pass is blocked on the Section 7 validation cycle producing real inter-rater data from multiple trained assessors on real codebases. It cannot be drafted before then without speculating about error patterns that have not yet been observed, which would embed speculation into the training material and create drift before the first cohort has been trained.

---

