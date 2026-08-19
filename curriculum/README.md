# Open Honest Curriculum and Methodology Suite

**Status:** v0 master plan. Most artifacts not yet drafted. This document is the canonical reference for what the curriculum is, what it teaches, who it teaches, where its components live, and the order in which they should be drafted.

## What this is

A two-track training and certification suite for the Open Honest engagement model. The curriculum produces certified practitioners at four levels per track. It is designed to be sold to the audit partner as a delivery enablement asset and used internally by Buckler to scale the methodology beyond the original architect.

## Why it exists

The Open Honest engagement depends on two distinct skills: the **slop audit** (Phase 0, post-hoc, transferable through training) and the **live code audit** (Phase 1, real-time, partially apprenticeship-based). Without trained practitioners, the engagement only runs at the speed of the original architect's personal calendar. The curriculum is what converts the methodology from a one-person practice into a transferable discipline.

This is the load-bearing scaling artifact for the entire Open Honest business model. Without it, the audit partner cannot deliver Phase 0 and Phase 1 engagements at the rate the redirection-of-existing-AI-spend pitch implies. With it, every certified practitioner adds throughput.

## How the curriculum relates to the rest of the package

```
open-honest/
├── README.md                              ← top-level project overview
├── methodology/
│   └── methodology/ (see methodology/README.md for reading guide)          ← the methodology document Track 1 teaches
├── governance/                            ← Honest Foundation (Constitution, Charter, CoC, Mission)
├── administrator/                         ← first commercial administrator (the audit partner)
│   ├── delivery-kit/                      ← what the commercial administrator delivers
│   ├── cpc-package/                       ← CPC go-to-market kit
│   └── enablement/                        ← BD/sales internal materials
├── analyst-relations/                     ← category positioning with Gartner, Forrester, IDC
└── curriculum/                            ← THIS DIRECTORY
    ├── README.md                          ← this file (master plan)
    ├── track-1-slop-audit/                ← TBD (the four levels of slop audit certification)
    ├── track-2-live-code-audit/           ← TBD (the four levels of live code audit certification)
    ├── shared/                            ← TBD (calibration codebases, exercises, assessments)
    └── trainer-guide/                     ← TBD (how to teach this)
```

The methodology document (`methodology/methodology/ (see methodology/README.md for reading guide)`) is the *content* the curriculum teaches for Track 1. The Honest Code book, the contract testing methodology, and the honest-code-principles are the *content* the curriculum teaches for Track 2. The curriculum itself is the training scaffold, the assessment instruments, the exercises, and the certification criteria.

## The two tracks

### Track 1. Slop Audit Competency

Phase 0 work. The first three layers of the four-layer methodology model: mechanical git-history indicators (Layer 1), mechanical per-dimension artifact inspection (Layer 2), and per-dimension qualitative specified judgment (Layer 3). Achievable in weeks to months depending on level. Transferable through structured training because each layer's assessment instruments are well-defined and the inter-rater reliability test gives a measurable certification criterion.

### Track 2. Live Code Audit Competency

Phase 1 work. Layer 4 of the four-layer model: architectural synthesis and real-time architectural review during AI generation. Months to years to reach competence. The published research describes this as requiring "elite-level architectural expertise" — experience building, shipping, and maintaining enterprise systems applied to a new failure mode. The curriculum cannot teach this from scratch; it can only train candidates who already have most of the prerequisites.

### How the four layers map to curriculum levels

The four-layer methodology model (see `methodology/methodology/ (see methodology/README.md for reading guide)` Section 2) maps cleanly onto the curriculum levels. The mapping is the source of the prerequisite structure:

| Methodology layer | What it requires | Track 1 level that teaches it | Track 2 level that teaches it |
|---|---|---|---|
| **Layer 1** — quantitative git-history indicators (mechanical, scriptable) | Git literacy + ability to interpret threshold bands | **L1 Apprentice** (full coverage) | not applicable (Track 1 prerequisite) |
| **Layer 2** — quantitative artifact-based dimension inspection (mechanical per-dimension procedures) | Familiarity with compliance frameworks + working knowledge of how the 18 dimensions are implemented in real systems | **L2 Practitioner** (full coverage) | not applicable (Track 1 prerequisite) |
| **Layer 3** — qualitative specified judgment via per-dimension markers (5 markers per dimension, scored present/partial/absent) | Domain experience to recognize when a marker is genuinely present versus performatively present | **L2 Practitioner** (introduced) → **L3 Lead** (mastery + cross-rater calibration) | LV1 Trainee builds on Track 1 L2 |
| **Layer 4** — architectural synthesis (deferred to Phase 1, requires real-time review during AI generation) | Elite architectural judgment built over years of shipping and maintaining enterprise systems | not in Track 1 (Track 1 explicitly stops at Layer 3) | **LV1 → LV4** (the entire Track 2 ladder) |

**The curriculum boundary is the layer boundary.** Track 1 teaches the mechanical and the qualitative-but-specified work of Layers 1, 2, and 3. Track 2 teaches the architectural-synthesis work of Layer 4. The two tracks meet at the Phase 0 / Phase 1 handoff, which is the same boundary as the Layer 3 / Layer 4 handoff in the methodology document. A practitioner who has completed Track 1 L3 can lead a Phase 0 audit; a practitioner who has reached Track 2 LV3 can lead a Phase 1 escape pod build. Together they cover the full engagement.

**Why this mapping matters for drafting.** Each curriculum level has a single methodology layer it is *responsible for teaching*. This eliminates ambiguity about what a level's exercises and assessments should cover. L1 exercises cover Layer 1 only. L2 exercises cover Layer 2 with introductory exposure to Layer 3. L3 exercises cover Layer 3 mastery and the inter-rater reliability test on Layer 3 markers. LV1 exercises cover the recognition vocabulary for Layer 4 patterns. LV4 exercises *are* Layer 4 review work conducted under supervision. The four-layer mapping is the source of truth for what each level teaches and where the boundaries are.

The two tracks are independent. A practitioner can be certified at any level of Track 1 without touching Track 2. Track 2 has Track 1 as a prerequisite at certain levels (LV2 requires Slop Audit L2) because the slop audit teaches the recognition vocabulary that the live code audit builds on, but the tracks otherwise progress separately.

## Levels and prerequisites

### Track 1. Slop Audit Competency

| Level | Title | Curriculum teaches | Curriculum requires (knowledge) | Curriculum requires (experience) | Activity prerequisites | Measurable outcome | Estimated time to reach |
|---|---|---|---|---|---|---|---|
| **L1** | Slop Audit Apprentice | Layer 1 mechanical assessment, the eleven indicators, the threshold bands, how to run the reference script and interpret the panel | Working knowledge of git internals (commits, branches, history rewriting, the difference between a shallow clone and a full clone). Familiarity with at least 2 production CI/CD systems. Basic understanding of what audit and compliance mean in a regulated context. | Has shipped at least one production system to a real user, in any environment. Has read at least one published incident post-mortem and understands why the incident happened. | Senior developer, 5+ years; reading the methodology document Sections 1–3. | Produces a Layer 1 panel that matches a reference assessor's panel exactly on the same repo. | 1–2 days of training + 2 supervised runs |
| **L2** | Slop Audit Practitioner | Layer 2 per-dimension scorecard methodology, the 18 dimensions, the evidence inspection procedures, how to write a defensible Slop Report | Familiarity with at least 3 of SOC 2, NIST 800-53, OWASP ASVS, OSFI B-13, FFIEC IT Examination Handbook, SIG at a what-it-tries-to-do level. Working knowledge of how authentication, authorization, audit logging, and rate limiting are implemented in real systems. Operational understanding of containerization. | Has been through at least one external audit of a system they were responsible for, OR has built a system that was later audited and remembers the findings. Has refactored code that was inherited from someone else. Has deleted code in production. | L1 + reading the methodology document in full + reading Wasserman 2026. | Cross-rater test: agrees with a reference assessor on ≥16 of 18 dimensions on a known calibration codebase. | 1 week of training + 3 supervised runs |
| **L3** | Slop Audit Lead | How to lead a complete Phase 0 engagement, scope an audit, debrief a client, draft the three Phase 0 deliverables (Slop Report, Self-Service Gap Analysis, Escape Pod Proposal) | Deep familiarity with at least one regulated industry's technology requirements (financial services, healthcare, energy, telecommunications, government). Understands the difference between "audit-ready" and "audited." Can articulate why a single missing control disqualifies a vendor. | Has presented technical findings to non-technical stakeholders (CFO, board, audit committee, regulator) at least 3 times. Has been challenged on findings and successfully defended them with evidence. Has chosen to *not* report something that turned out to be unimportant, and explained the choice. | L2 + completed validation cycle on positive and negative controls. | Independent audit of a real client codebase passes peer review by another L3 or higher. | 2–3 weeks training + 5 supervised audits |
| **L4** | Slop Audit Trainer | How to train new L1–L3 assessors, how to run the inter-rater reliability test, how to handle calibration drift, how to certify candidates | Working knowledge of how adults learn technical material (cognitive load, scaffolding, expert blind spots, transfer-of-learning failure modes). Understands why the inter-rater reliability test is the certification mechanism, and can explain it in their own words. | Has trained at least one other developer in any structured technical skill (mentorship, pair programming over months, formal instruction). Has had a trainee fail the certification and been responsible for diagnosing why. | L3 + delivered ≥10 client engagements. | Has trained ≥3 assessors to L2 with ≥90% inter-rater agreement on calibration codebase. | 6–12 months active practice as L3 |

### Track 2. Live Code Audit Competency

| Level | Title | Curriculum teaches | Curriculum requires (knowledge) | Curriculum requires (experience) | Activity prerequisites | Measurable outcome | Estimated time to reach |
|---|---|---|---|---|---|---|---|
| **LV1** | Live Code Audit Trainee | Honest Code pattern catalog (the 19 principles), the contract testing methodology, recognition exercises on seeded antipatterns, the gradient-mean drift mechanism in plain language | Understands the difference between pure functions and stateful methods, and can articulate why the difference matters for testability. Has read the Honest Code book in full. Has read the contract testing methodology document. Working knowledge of at least one statically-typed language and one dynamically-typed language. | Has written production code in at least 2 languages. Has written tests that caught a real bug in production code. Has experienced at least one bug that was caused by hidden state, even if they didn't recognize it as such at the time. | Slop Audit L2 + read Honest Code book + read honest-code-principles.md | Identifies ≥80% of seeded antipatterns in a calibration codebase containing known violations. | 2–4 weeks of guided reading + practice |
| **LV2** | Live Code Audit Pair | How to pair with a senior reviewer during real-time AI generation, how to surface observations productively, how to receive correction without ego | Recognizes inheritance hierarchies, dependency injection containers, mock-heavy test suites, framework lifecycle hooks, and application-level caches when they appear in code. Can name at least 3 categories of bug that come from each. Understands what gradient descent does to AI output mathematically (not the calculus, the *implication*). | Has refactored an inheritance hierarchy into composition at least once. Has replaced a mock-heavy test with a pure-function test and observed the test become smaller and more reliable. Has deleted a cache in favor of a query and measured the result. Has been on-call for a production system for at least 6 months. | LV1 + 6+ months of enterprise development experience | Pairs effectively with an LV4 reviewer for ≥40 hours, with ≥70% of LV2 observations rated valuable by the LV4. | 2–3 months of guided pairing |
| **LV3** | Live Code Audit Reviewer | How to lead live review of AI generation on bounded modules, how to interrupt drift mid-generation, how to question and sample, how to draft Phase 1 architectural review reports | Deep operational fluency with at least one full enterprise stack (web framework, ORM, message queue, observability layer, deployment pipeline, secret management). Understands the Honest Framework architecture in enough detail to explain it unprompted to a senior developer who has never seen it. Can recognize the *style* of AI-generated code that has not been reviewed (the gradient-mean signature). | Has shipped at least one greenfield module under a structured AI SDLC, even if not formally named that way. Has been the architect of record for at least one system that survived an external audit. Has interrupted an AI mid-generation and redirected it, and remembers what specifically caused the redirect. Has made a hiring or firing decision based on architectural judgment. | LV2 + has shipped at least one greenfield module under Honest Code discipline. | Leads ≥10 hours of live review per week with weekly check-ins. Reviewed work passes Layer 2 audit on delivery. | 6–12 months active practice |
| **LV4** | Live Code Audit Architect | How to lead unsupervised live review on production engagements. How to train LV1–LV3. How to articulate the methodology to skeptical senior architects. How to refuse engagements that would compromise the methodology. | Has the credentials of a working enterprise architect who has been held accountable for the systems they built. Understands the audit process from the buyer side. Can articulate the full Honest Framework methodology unprompted, including the parts that are not in any document. Understands why the methodology cannot be transferred through documentation alone. | Has built, shipped, and maintained at least one enterprise system over 100,000 lines of code, ideally under regulatory scrutiny. Has trained at least one LV3 candidate from LV1 or LV2. Has been responsible for the contribution margin of a software-producing organization OR has equivalent accountability in a non-commercial context (academic research lab director, open-source maintainer of a widely-used project, technical fellow). Has fired or terminated a working relationship over slop. | LV3 + delivered ≥3 escape pod builds + can articulate the full Honest Framework methodology unprompted. | Leads a full Phase 1 escape pod build that passes 18-of-18 audit dimensions on delivery. | 18+ months active practice |

### Notes on the prerequisite structure

1. **Knowledge prerequisites are what the candidate must already understand.** They cannot be acquired through the curriculum's coursework. They must be present before the curriculum can teach anything.
2. **Experience prerequisites are what the candidate must have already done.** Some of these are diagnostic-style ("has experienced a bug caused by hidden state, even if they didn't recognize it at the time") and surface during a 30-minute prerequisites interview rather than via a CV checkbox.
3. **The L4/LV4 levels are partly admissions filters, not training programs.** A candidate at L4 or LV4 already has most of what the level requires. The "training" at the top of each track is mostly recognition that the candidate already brings the capability, plus a structured framework for using it inside the methodology. The honest framing is: *we are not making you a Slop Audit Trainer. You are already most of the way there. We are giving you the methodology, the assessment instruments, and the calibration codebases so that what you already know becomes transferable to others.*
4. **The LV4 path is intentionally pluralistic.** The original draft had P&L accountability as a hard prerequisite. The current draft admits multiple paths (commercial CTO, academic research lab director, open-source maintainer of a widely-used project, technical fellow at a large org). The common thread is *accountability for outcomes*, not the specific organizational form of the accountability.
5. **Temperament is not in the prerequisite tables.** Adam decided that temperament considerations belong in the trainer's guide rather than in the formal prerequisites, because temperament is hard to test in 30 minutes and it can drift into "we don't hire people like that" if not handled carefully. The trainer's guide will include trainer-only notes on temperament patterns to watch for and how to work with them.

## The diagnostic interview

Each level has a 30-minute prerequisites interview that the trainer conducts before admitting the candidate. The interview is structured to surface the experience prerequisites that don't appear on a CV. Sample diagnostic questions for L2:

- "Tell me about a bug you fixed in code you didn't write. What did the bug turn out to be?"
- "Walk me through the most embarrassing thing you've shipped to production. What did you learn from it?"
- "When was the last time you deleted a substantial amount of working code? Why?"
- "Describe the most frustrating audit or compliance review you've been through. What did the auditor catch?"

The candidate's answers are not graded for correctness; they are listened to for the *level of mechanism* the candidate operates at. A candidate who describes a bug in terms of symptoms ("the page didn't load") is not yet at L2. A candidate who describes the bug in terms of mechanism ("we were caching a stale value because the invalidation was on a different code path") is.

The diagnostic interviews are documented per level in `curriculum/track-1-slop-audit/diagnostic-interviews.md` (TBD) and `curriculum/track-2-live-code-audit/diagnostic-interviews.md` (TBD).

## The four-lens self-assessment exercise

Every level above L1/LV1 includes a self-assessment exercise where the trainee submits a recent Claude Code conversation transcript and analyzes their own prompting patterns against four lenses:

1. **Prompt-craft patterns** — how the trainee frames requests, corrects mistakes, manages context
2. **Cognitive workflow patterns** — how the trainee balances depth and breadth, validates alignment, asks for opinions versus execution
3. **Domain expertise expressed as prompting** — where the trainee's knowledge surfaces in their prompts and where it's missing
4. **Anti-patterns and unforced errors** — where the trainee accepts output that wasn't quite right, where they let sessions run too long, where they fail to disambiguate

The trainer reviews the self-assessment. Improvement on this exercise over time is one of the certification criteria for L3/LV3 and L4/LV4.

The reference prompt for the self-assessment exercise is at `outreach/03-shawna-self-analysis-prompt.md`. It will be promoted into the curriculum directory once the curriculum drafting begins, with an updated header for general use rather than the personal framing it currently has for Shawna specifically.

The four-lens framework itself is documented at length in the conversation history that produced this curriculum design. It will be extracted into a standalone curriculum document at `curriculum/shared/four-lens-analytical-framework.md` (TBD) when the curriculum drafting begins.

## Course materials needed (the deliverables)

For each level, per track, the curriculum requires the following artifacts:

| # | Artifact | Purpose | Audience |
|---|---|---|---|
| 1 | **Reading list** | Required and optional sources, with annotations on what each source contributes | Trainee |
| 2 | **Practical exercises** | Calibration codebases with expected outcomes, hands-on tasks the trainee performs | Trainee |
| 3 | **Assessment instrument** | The certification test matching the measurable outcome for the level | Trainer |
| 4 | **Diagnostic interview script** | The 30-minute prerequisites interview with sample questions and listening criteria | Trainer |
| 5 | **Sign-off criteria and submission artifact** | What the candidate produces to demonstrate they have reached the level, and how the trainer evaluates it | Trainer + trainee |
| 6 | **Trainer notes** | How the trainer for level N should think about training a candidate from level N-1 to level N. Includes temperament observations and common failure modes. | Trainer (level above) |

That is 6 artifacts × 8 levels = **48 documents** for a complete curriculum. Plus shared infrastructure:

- Calibration codebases (positive control = idd honest-conversion branch; negative control = TBD pre-conversion branch; possibly additional codebases representing different points on the slop spectrum)
- The four-lens self-assessment template (extracted from the Shawna prompt with personal framing removed)
- The trainer certification process (how a candidate becomes L4 or LV4)
- The cross-rater test protocol (how Layer 2 inter-rater agreement is measured)
- The trainer's guide (the meta-document that explains how to teach this curriculum, including temperament notes that don't belong in formal prerequisites)

Total estimated artifact count for a complete v1 curriculum: **~60 documents**, of which **0 are currently drafted**. Drafting all of them is multi-month work, and the right approach is incremental — draft the highest-leverage levels first, validate them by training one or two real candidates, refine, then expand.

## Drafting priority

The curriculum should be drafted in this order:

### Phase 1. Foundation (essential before any candidate is trained)

1. `methodology/methodology/ (see methodology/README.md for reading guide)` Section 4 (the 18-dimension catalog) — load-bearing for L2 and above. Currently a stub; the highest-priority drafting work in the entire package.
2. `curriculum/track-1-slop-audit/L1-apprentice/` — the easiest level to draft because Layer 1 is mechanical and the assessment criterion (exact match on a calibration repo) is unambiguous.
3. `curriculum/shared/four-lens-analytical-framework.md` — extract the framework from the conversation history into a standalone document, generalize the Shawna prompt for trainee use.
4. `curriculum/shared/calibration-codebases.md` — identify the positive control (idd honest-conversion), choose a negative control branch, document why each was chosen, define how trainees access them.

### Phase 2. First trainable level (sufficient to certify the first L1 practitioner)

5. `curriculum/track-1-slop-audit/L1-apprentice/reading-list.md`
6. `curriculum/track-1-slop-audit/L1-apprentice/exercises.md`
7. `curriculum/track-1-slop-audit/L1-apprentice/assessment.md`
8. `curriculum/track-1-slop-audit/L1-apprentice/diagnostic-interview.md`
9. `curriculum/track-1-slop-audit/L1-apprentice/signoff.md`

After Phase 2 is complete, the curriculum can certify its first L1 practitioner. This is the minimum viable curriculum.

### Phase 3. Second trainable level (sufficient to certify a Phase 0 practitioner)

10. `curriculum/track-1-slop-audit/L2-practitioner/` (5 artifacts) — depends on Section 4 of the methodology document being complete.

After Phase 3, the curriculum can certify L2 Slop Audit Practitioners, who can run a complete Phase 0 audit under supervision. **This is the minimum the Open Honest engagement actually needs to operate at scale.** Phases 1, 2, and 3 together are the critical path for the business.

### Phase 4. Track 1 completion

11. `curriculum/track-1-slop-audit/L3-lead/` (5 artifacts)
12. `curriculum/track-1-slop-audit/L4-trainer/` (5 artifacts)
13. `curriculum/trainer-guide/track-1.md` — how to teach Track 1, including temperament notes

### Phase 5. Track 2 foundation (the harder track)

14. `curriculum/track-2-live-code-audit/LV1-trainee/` (5 artifacts)
15. `curriculum/track-2-live-code-audit/LV2-pair/` (5 artifacts)

### Phase 6. Track 2 completion

16. `curriculum/track-2-live-code-audit/LV3-reviewer/` (5 artifacts)
17. `curriculum/track-2-live-code-audit/LV4-architect/` (5 artifacts)
18. `curriculum/trainer-guide/track-2.md`

### Phase 7. Cross-track integration

19. `curriculum/trainer-guide/master.md` — the trainer's guide for the entire curriculum
20. Updates to `methodology/methodology/ (see methodology/README.md for reading guide)` Section 8 (training pathway), now that the curriculum exists

The current state is **Phase 1 partially started** (the methodology document frame is drafted, Section 4 catalog is stubbed). Everything else is unstarted.

## How the curriculum gets validated

Two validation cycles, parallel to the methodology document's own validation cycle:

1. **Internal validation.** Adam trains one or two candidates from L1 to L2 personally, using the v0 curriculum, and revises based on what fails. This takes approximately 2 months and uses the Buckler internal team (Shawna is a candidate). The output is a v1 curriculum that has been used at least once.

2. **External validation.** the audit partner trains one or two of their senior developers from L1 to L2 using the v1 curriculum, with Adam as remote trainer. This takes approximately 3 months and produces the first batch of certified the audit partner Slop Audit Practitioners. The output is a v2 curriculum that has been used by people other than Adam.

After v2, the curriculum is considered production-ready for the audit partner's commercial Phase 0 engagements.

## Licensing and IP

The curriculum is the most heavily IP-encumbered part of the Open Honest project. It contains:

- The 18-dimension methodology operationalized for transfer (which is the load-bearing intellectual property)
- The Honest Code patterns and antipatterns (currently public via the book, but the curriculum's pedagogical structuring is novel)
- The diagnostic interview questions and listening criteria (novel)
- The cross-rater test protocol (novel application of standard inter-rater reliability methodology)
- The four-lens self-assessment framework (novel)
- Calibration codebase selections and annotations (novel)

Per Adam's earlier decision, the entire Open Honest project (including the curriculum) will be licensed to the audit partner. The licensing terms are still TBD. Whether the audit partner is charged for the license is an open question that Adam is considering.

The curriculum is **not** open-source. Even after Honest Framework becomes FOSS, the curriculum that teaches enterprise consultants how to deliver the methodology is a separate commercial asset that may be licensed differently.

## What this curriculum is not

A few things worth naming explicitly to prevent scope creep:

1. **It is not a generic "AI-assisted development" course.** It is specifically about the structured AI SDLC documented in Wasserman 2026 and the Honest Framework patterns that operationalize it. Other AI development methodologies exist; this curriculum does not teach them, and it does not pretend to be neutral about which methodology is correct.
2. **It is not a Honest Framework introduction.** The Honest Code book is the introduction. The curriculum assumes the trainee has read the book and is ready to apply it in an audit and assessment context. Reading the book is an LV1 prerequisite, not curriculum content.
3. **It is not a software architecture course.** Software architecture experience is a prerequisite at L2 and above. The curriculum teaches the trainee how to use their existing architectural judgment inside the methodology, not how to acquire architectural judgment in the first place.
4. **It is not certification for Honest Framework adoption inside a client.** That is what Phase 1 of the engagement does. The curriculum trains the practitioners who run engagements; the engagements then transfer the framework to the client's developers.

## Open questions for the next planning round

These were surfaced during the curriculum design and need decisions before drafting begins in earnest:

1. **Should curriculum drafting begin before or after the methodology document Section 4 (18-dimension catalog) is complete?** My recommendation is *after*, because L2 depends on the catalog and drafting L2 against a stub would mean rewriting it once the catalog lands. Drafting L1 in parallel with Section 4 is fine because L1 only depends on Sections 1–3 of the methodology document, which are already drafted.
2. **How is the curriculum priced?** Per-trainee certification fee? Per-engagement annual license? Bundled with the Open Honest project? This decision affects how the audit partner sells it and how it shows up in their P&L.
3. **Where do calibration codebases come from beyond idd?** The honest-conversion branch is the canonical positive control, but training scale will require additional codebases representing different points on the slop spectrum. Sources: client engagements (with permission), open-source repositories (with public-domain calibration), purpose-built training repositories.
4. **Does the curriculum produce a credential the trainee can put on a CV?** "Certified Slop Audit Practitioner" or "Certified Live Code Audit Architect" — the credential model affects how the curriculum is marketed and how trainees value it. Decision not yet made.
5. **What is the cohort size for the first trainee batch?** A 1:1 trainer-to-trainee ratio for L3 and LV3 is realistic; for L1 and L2 the ratio can be higher. The first cohort decision affects the v0 → v1 timeline.
6. **Is the Shawna self-analysis exercise the right starting point for Buckler-internal validation?** Adam and Shawna already have a trust relationship and a working pattern, which makes Shawna an ideal first trainee. The exercise scheduled for her will produce the first cross-validation of the four-lens framework against a real practitioner who is not Adam.

## Where this fits in the next two weeks of work

The curriculum is the long arc. The immediate next two weeks are still about drafting `methodology/methodology/ (see methodology/README.md for reading guide)` Section 4 (the 18-dimension catalog) because that artifact gates everything else in Track 1. Curriculum drafting begins in earnest after the catalog is complete and after Shawna's self-analysis result is returned and triangulated against Adam's.

The one thing that should happen *now*, in parallel with the catalog drafting, is the creation of `curriculum/shared/four-lens-analytical-framework.md` — extracting the framework from the conversation history into a standalone document. Without that extraction, the four-lens framework lives only in conversation memory and risks being lost when the conversation ends.

That extraction is the next curriculum-side artifact to draft. Everything else in the curriculum directory waits for the methodology catalog and the first cross-validation.

---

## Drafting status

### Drafted
- This master plan (`curriculum/README.md`)
- The Shawna self-analysis prompt (`outreach/03-shawna-self-analysis-prompt.md`) — to be promoted to `curriculum/shared/four-lens-self-assessment-prompt.md` after generalization

### Stubbed
- Nothing in the curriculum directory beyond this README

### Not yet started
- Everything else listed in the drafting priority sequence above
