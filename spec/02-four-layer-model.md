## 2. The four-layer model

The slop audit is not a single methodology. It is **four nested methodologies that compose**, each operating at a different cognitive level and each producing a different kind of evidence. Phase 0 of the Open Honest engagement runs Layers 1, 2, and 3. Layer 4 is part of Phase 1 and is named here to establish the boundary precisely, since the boundary between Phase 0 and Phase 1 is the load-bearing decision of the entire methodology.

The four layers, in order of increasing cognitive demand:

| Layer | Name | Cognitive demand | Phase | Curriculum level |
|---|---|---|---|---|
| **1** | Quantitative git-history assessment | Mechanical (no judgment) | Phase 0 | L1 Apprentice |
| **2** | Quantitative artifact assessment | Mechanical (no judgment) | Phase 0 | L2 Practitioner |
| **3** | Qualitative specified judgment | Trainable judgment with specified markers | Phase 0 | L3 Lead |
| **4** | Architectural synthesis | Elite judgment, requires apprenticeship | Phase 1 | LV3 / LV4 Reviewer / Architect |

The four layers separate two fundamentally different kinds of judgment. Layers 1 and 2 are mechanical: any trained assessor following the documented procedures will produce the same scores. Layer 3 is qualitative but specified: it requires informed judgment, but the judgment criteria are defined precisely enough that trained assessors produce consistent scores (inter-rater reliability targets are specified per dimension). Layer 4 is elite judgment that requires years of architectural experience and cannot be reduced to specified markers. The Phase 0 / Phase 1 boundary sits between Layer 3 and Layer 4: Phase 0 delivers Layers 1, 2, and 3; Phase 1 adds Layer 4.

### 2.1 Layer 1. Quantitative git-history assessment

**What it is.** A mechanical analysis of the codebase's git commit history and static artifacts that produces twenty numerical indicators. Inputs are a git repository and a date range. Outputs are a panel of ratios and counts that signal whether the codebase exhibits the patterns associated with structured or unstructured AI-assisted development.

**What it requires.** A working clone of the repository, read access to the full commit history, and a script (or a trained assessor running git commands manually). It requires no architectural judgment. The same indicators applied to the same repository by two different assessors will produce identical numbers.

**What it produces.** The first page of the Slop Report: a numerical panel that is reproducible, citable, and verifiable by anyone who can read git log. The panel does not by itself produce findings; it produces signals that justify the deeper Layer 2 and Layer 3 work and that constrain how that work is presented.

**Why it matters strategically.** Layer 1 is the cheapest, fastest, most reproducible signal available, and it produces numbers a CPC member can verify themselves if challenged. Numbers that come from running git commands are harder to dispute than numbers that come from architectural judgment.

**Curriculum level.** L1 Apprentice. A trained assessor can run the Layer 1 indicators after 1–2 days of training and 2 supervised practice runs. Inter-rater reliability is essentially perfect for this layer because the indicators are mechanical.

**Source.** Layer 1 is operationalized from Sections 4.7 and 4.8 of Wasserman 2026. The paper documents the indicators on the structured and unstructured natural-experiment conditions; this methodology generalizes them into a per-codebase assessment instrument.

### 2.2 Layer 2. Quantitative artifact assessment

**What it is.** A mechanical inspection of the codebase's structural artifacts (configuration files, dependency declarations, file structures, naming conventions, presence and absence of specific kinds of files) for each of the 18 enterprise audit dimensions. The inspection produces an *artifact-based score* per dimension: present, partial, or absent, based on what can be observed without exercising judgment.

**What it requires.** A trained assessor with the methodology document open. The training equips the assessor to know which artifacts to look for in each dimension and how to recognize them. It does not require architectural judgment beyond recognition. The same Layer 2 inspection applied to the same repository by two different trained assessors should produce nearly identical artifact findings.

**What it produces.** The artifact-based portion of the 18-dimension scorecard. For each dimension, the assessor records what artifacts were found (or not found), with file paths and line numbers cited as evidence. The artifact findings constrain but do not by themselves determine the dimension's overall score; the qualitative Layer 3 assessment may add nuance.

**Why it matters strategically.** Layer 2 is the load-bearing mechanical defense of the methodology's defensibility. Every artifact-based finding can be reproduced by any other trained assessor in minutes. The CPC is not asked to trust judgment; the CPC is asked to look at the client's own files and confirm what is or is not there. The mechanical reproducibility is what makes the Slop Report non-disputable.

**Curriculum level.** L2 Practitioner. A trained assessor can run Layers 1 and 2 after approximately one week of training and three supervised audits. The L2 certification criterion is inter-rater reliability: agreement with a reference assessor on at least 16 of 18 dimensions on a calibration codebase, where the agreement is measured at the artifact-finding level.

**Source.** Layer 2 is operationalized from Section 3.4 of Wasserman 2026 (which defines the 18 dimensions and their compliance framework mappings) and from Chapter 2 plus Appendix C of the working analysis document (which expands those mappings with per-dimension industry sources and threshold definitions). The 18-dimension catalog in Section 4 of this document is the operational instrument.

### 2.3 Layer 3. Qualitative specified judgment

**What it is.** A structured exercise of qualitative judgment, applied through specified markers, on aspects of each dimension that cannot be reduced to mechanical artifact inspection. For each of the 18 dimensions (where applicable), the assessor applies between three and five specified markers, each scored present / partial / absent according to defined criteria. The combination of marker scores produces the dimension's Layer 3 assessment, which combines with the Layer 2 artifact assessment to produce the dimension's overall score.

The Layer 3 markers are not arbitrary. They are designed to be applied consistently by trained assessors, with each marker specifying:

- What the assessor inspects (specific file types, specific code patterns, specific commits in the git history, specific documentation passages)
- What evidence supports each scoring level (present / partial / absent)
- What inter-rater reliability target applies. The default targets scale with the number of markers: **3 of 3** for dimensions with 3 markers (4.7 Configuration and secrets), **3 of 4** for dimensions with 4 markers (most of 4.1 through 4.11), and **4 of 5** for dimensions with 5 markers (4.12 and 4.13 through 4.18). Dimensions where the markers are inherently fuzzier may declare a lower target explicitly in their Layer 3 form (4.14 Architectural philosophy declares **3 of 5** for this reason). If a dimension does not declare an explicit target, the default for its marker count applies.

**What it requires.** A trained assessor who has internalized the marker definitions and who has practiced applying them to calibration codebases under supervision. The training is more substantial than Layer 2 (more cognitive load, more case-by-case judgment) but the criteria are still specified and the inter-rater reliability target is still measurable. **It does not require elite architectural judgment.** What it requires is training in the markers, not years of enterprise architecture experience.

**What it produces.** The qualitative portion of the 18-dimension scorecard, combined with the Layer 2 artifact findings into an overall dimension score. Each Layer 3 marker is recorded with its evidence citation and its score. The combined Layer 2 + Layer 3 score is what appears in the Slop Report's Part II per-dimension scorecard.

**Why it matters strategically.** Layer 3 is what allows Phase 0 to produce *meaningful* scores for dimensions where the meaningful question requires judgment, not just artifact recognition. Without Layer 3, dimensions like Pattern Sophistication, Architectural Philosophy, and Live Documentation would be either thin (Layer 2 mechanical only, missing the meaningful question) or out of scope for Phase 0 (deferred to elite judgment in Phase 1). With Layer 3, the meaningful question is answerable in Phase 0 by a trained assessor using specified markers, which is the key property that makes the methodology transferable beyond the original architect.

**Curriculum level.** L3 Lead. A trained assessor can run Layers 1, 2, and 3 after approximately 2–3 weeks of training and 5 supervised audits. The L3 certification criterion is the ability to lead a complete Phase 0 engagement independently, including the Layer 3 marker assessment, with peer review confirming inter-rater reliability against another L3 or higher.

**Source.** Layer 3 is the part of the methodology that is *not* directly operationalized from Wasserman 2026, because the paper does not document the layered model. Layer 3 is the operational instrument added by this methodology document to make qualitative-but-trainable judgment a transferable skill rather than an apprenticeship-only skill. The specific markers per dimension are documented in Section 4 of this methodology document.

### 2.4 Layer 4. Architectural synthesis

**What it is.** The qualitative judgment that *cannot* be reduced to specified markers, that *cannot* be exercised consistently by trained assessors without years of underlying experience, and that requires the assessor to compare what they observe in the client codebase against patterns from many other codebases they have built, shipped, and maintained at scale. This is the work that Wasserman 2026 Section 5.3 (requirement 2) describes as "elite-level architectural expertise" and that the published natural experiment identifies as the bottleneck of structured AI-assisted development.

Examples of Layer 4 questions:

- Is this codebase's architecture *the right architecture for this organization's domain*? (Requires knowing the domain and many alternative architectures.)
- Are there hidden couplings that only show up under operational stress? (Requires having seen the failure modes before.)
- Is the team's stated philosophy actually a *good* philosophy, or is it a justification for choices they were going to make anyway? (Requires distinguishing genuine architectural commitment from rationalization.)
- Would this codebase scale to 10x the current load without architectural changes? (Requires having scaled similar systems.)
- Are the patterns used *correctly* in the deepest sense, not just structurally but semantically? (Requires knowing what each pattern is meant to solve and recognizing when its use subverts its intent.)
- Are there subtle anti-patterns hidden inside ostensibly correct pattern usage? (The "Pattern Grime" failure mode in Feitosa & Avgeriou's research.)

These are all questions a trained assessor cannot answer consistently. They require the elite expertise that the published natural experiment §5.3 describes. That expertise does not transfer through documentation; it requires apprenticeship.

**What it requires.** Elite architectural judgment as defined in Wasserman 2026 §5.3: experience building, shipping, and maintaining enterprise systems applied to a new failure mode. This skill is the bottleneck of the entire methodology. The methodology cannot make Layer 4 transferable through training alone; it can only equip Layer 4 reviewers with structured tools (the Honest Code principles, the contract testing methodology, the layered framework above) that channel their existing expertise into useful outputs.

**What it produces.** Qualitative findings with concrete recommendations, structured around the Honest Code principles and the contract testing methodology. The output is not a score; it is a list of architectural improvements with reasoning, priority, and recommended sequencing. Layer 4 findings are documented separately from the Slop Report scorecard, in a Phase 1 deliverable that the engagement produces during the build phase.

**Why this is out of scope for Phase 0.** Phase 0 audits must be runnable by trained L3 Lead assessors at scale. Layer 4 cannot scale that way because the skill it requires does not transfer at training speed. Including Layer 4 in Phase 0 would either degrade the quality of the work (if L3 assessors attempted it without the underlying expertise) or limit Phase 0 to the few people who can do it (which collapses the engagement model). Layer 4 is therefore Phase 1 work, performed by senior architects during the build phase, where the cost of elite expertise is justified by the value of the build itself.

**The boundary in practice.** During a Phase 0 audit (Layers 1, 2, and 3), the L3 assessor may notice Layer 4 issues (violations of honest principles, dishonest patterns, architectural smells, deeper inconsistencies the Layer 3 markers do not catch). These are recorded as **flagged for Phase 1 follow-up** in a dedicated section of the Slop Report. They are not scored, not remediated, and not used to influence the Layer 2 + Layer 3 dimension scores. Section 6 of this document defines the format for flagged Layer 4 findings.

The boundary is structural and load-bearing. An L3 assessor who attempts to do Layer 4 work during Phase 0 has committed a methodology violation. The forbidden behavior is not "exercising judgment" — Layer 3 is judgment — but "exercising judgment beyond the specified markers." If the markers do not produce a clear answer, the answer is "this dimension scores with the Layer 2 artifact result alone, the Layer 3 question is flagged for Phase 1 follow-up," not "the assessor uses their personal judgment to extend the Layer 3 scoring."

**Curriculum level.** LV1 through LV4 in the curriculum. LV1 is the prerequisite knowledge (read the Honest Code book, recognize patterns and antipatterns in static review). LV2 is supervised pairing with a senior reviewer during real-time AI generation. LV3 is leading live review of bounded modules under remote supervision. LV4 is leading unsupervised review on production engagements. The full progression takes 18+ months and requires substantial prior enterprise experience as a prerequisite. Most of the work is apprenticeship; the curriculum can structure and accelerate the progression but cannot create the underlying expertise from scratch.

**Source.** Layer 4 is documented in this methodology only as a boundary marker. The actual Layer 4 work is supported by:

- The Honest Code book (the canonical pattern catalog, full of recognizable crime-scene-and-rescue contrasts)
- The Honest Code principles document (the working principles distilled into a compact reference)
- The contract testing methodology document (the verification approach for honest code)
- The four-lens analytical framework (the self-assessment exercise that helps reviewers calibrate their own pattern recognition)

These documents are referenced in the Layer 4 portion of the Track B delivery kit (specifically, the Honest Framework reviewer documentation, which is gated on the IP licensing structure between the original author and the audit partner).

### 2.5 Composition

The four layers compose in this order during a Phase 0 engagement:

```
Day 1: Layer 1 mechanical pass (produces the quantitative git-history panel)
Day 2: Layer 2 artifact inspection across dimensions 1–9
Day 3: Layer 2 artifact inspection across dimensions 10–18, plus Layer 3 markers for dimensions 1–9
Day 4: Layer 3 markers for dimensions 10–18, plus report writing
Day 5: Layer 4 flagged-findings section, debrief with client, Phase 1 scoping
```

A Phase 0 audit produces a Slop Report containing the Layer 1 panel, the Layer 2 + Layer 3 combined scorecard for all 18 dimensions, and the Layer 4 flagged-for-follow-up section. Phase 1 expands the Layer 4 work into ongoing architectural review during the escape pod build, performed by senior architects who can sustain the elite-judgment work that Layer 4 requires.

The 5-day budget assumes a mid-size codebase (50,000–250,000 lines of code). Larger codebases scale roughly linearly. Smaller codebases (under 20,000 LOC) can complete in 3 days. The Layer 3 work adds approximately 1 day to what was previously a 4-day Phase 0 audit, which is a real cost; the benefit is that the Phase 0 deliverable now produces meaningful scores on dimensions that would otherwise be deferred to Phase 1 or scored thinly.

### 2.6 Why four layers, not fewer

The four-layer structure exists because there are genuinely four different kinds of work, each requiring a different skill level and producing a different kind of evidence:

1. **Layer 1 is computable.** A script can produce the full panel. No human judgment required.
2. **Layer 2 is mechanical but requires domain knowledge.** A trained assessor recognizes artifacts by type (authorization middleware, rate-limiting configuration, CI/CD pipelines). The recognition is trainable in days.
3. **Layer 3 is qualitative but specified.** A trained assessor applies defined markers (pattern fitness, prescriptive vs descriptive language, convergent solutions to similar problems). The judgment criteria are explicit enough that two trained assessors produce consistent scores. This is trainable in weeks.
4. **Layer 4 is qualitative and unspecifiable.** An elite architect recognizes hidden couplings, misapplied patterns, and architectural decisions whose consequences only manifest under operational stress. This requires years of experience and cannot be reduced to markers.

Collapsing any two of these layers loses the distinction between the skills they require. The curriculum mapping is clean: each certification level adds exactly one layer. The Phase 0 / Phase 1 boundary is clean: Phase 0 covers Layers 1, 2, and 3; Phase 1 adds Layer 4. The inter-rater reliability targets are clean: each layer has its own.

### 2.7 The Phase 0 / Phase 1 boundary, restated

The boundary between Phase 0 and Phase 1 is the boundary between Layer 3 and Layer 4: between qualitative-but-trainable judgment (Phase 0, L3 Lead competency) and elite-judgment-by-apprenticeship (Phase 1, LV3+ competency). The boundary is structural and immutable within the methodology. Any attempt to move work across the boundary in either direction is a methodology violation:

- An L3 Lead who attempts Layer 4 work during a Phase 0 audit has violated the methodology by exercising judgment beyond the specified markers.
- A Phase 1 reviewer who reduces Layer 4 work to Layer 3 markers has degraded the depth of architectural review and is not delivering Phase 1 value.

The boundary is designed to keep Phase 0 transferable to trained assessors (so the engagement scales) and to keep Phase 1 valuable as the architectural review layer (so the engagement justifies its premium pricing).

---

