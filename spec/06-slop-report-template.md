## 6. Slop Report template

The Slop Report is the central Phase 0 deliverable. Its structure is fixed so that any audit of any codebase produces a recognizably similar document. This consistency matters: the CIO carrying the Slop Report into a CPC needs the document to look like a standard audit instrument, not like a bespoke vendor narrative.

### 6.1 Document structure

```
SLOP REPORT
[Client name]: [Codebase name]
Date: [YYYY-MM-DD]
Assessor: [name, organization]
Methodology version: [v0]
Source paper: Wasserman 2026 (https://doi.org/10.5281/zenodo.19355460)

== EXECUTIVE SUMMARY (1 page) ==
- The slop signal count from Layer 1: X of 17 (or X of 16 if L1.15 is n/a)
- The Layer 2 pattern classification: [Structured / Mixed / Unstructured]
- Dimensions present: X of N
- Dimensions partial: X of N
- Dimensions absent: X of N
- Dimensions not applicable: X of 18 (N = 18 minus the not-applicable count)
- The three most consequential absences (one sentence each)
- The single recommended next step (one sentence)

Note on *not applicable* scores. Dimension 4.18 (UX from code) scores *Not applicable* on systems with no user-facing interface (pure backend services, batch jobs, library code). Future dimensions may also introduce *Not applicable* for similar reasons. When a dimension is *Not applicable*, it is recorded distinctly in Part II with a one-sentence justification and is removed from the denominator of the dimension counts above (so that a backend-only codebase is not penalized for having no UI to score). The total dimension count N is therefore 18 minus the *Not applicable* count.

== PART I. QUANTITATIVE PANEL (1 page) ==
[The Layer 1 panel from Section 3.3]

== PART II. PER-DIMENSION SCORECARD (12-18 pages) ==
For each of the 18 dimensions:
  - Dimension name and lifecycle category
  - Score: ABSENT / PARTIAL / PRESENT / NOT APPLICABLE
  - Industry threshold (one sentence, with citation)
  - Evidence cited (specific files and line numbers)
  - Qualitative assessment (1-3 sentences)
  - Failure mode observed (if absent or partial, drawn from the recognition vocabulary)
  - Justification (if not applicable, one sentence explaining why the dimension does not apply to this codebase)

== PART III. FLAGGED FOR PHASE 1 FOLLOW-UP (1-3 pages) ==
Architectural pattern observations that warrant deeper Layer 3 review during a Phase 1 engagement. Recorded as observations only; not scored, not used to influence Layer 2 dimension scores. Each observation includes:
  - Pattern observed
  - Files where observed
  - Why it warrants Phase 1 attention
  - Honest Code principle (or contract testing principle) it implicates

== PART IV. METHODOLOGY NOTES (1 page) ==
- Date range assessed
- Branch assessed
- Total LOC in scope
- Total commits in date range
- Limitations encountered (if any)
- Methodology version and document reference

== APPENDIX. EVIDENCE EXCERPTS (variable) ==
Per-dimension evidence files quoted in full, with file paths, line numbers, and one-sentence captions. This appendix is what makes the report non-disputable: every score is backed by code the client can inspect themselves.
```

### 6.2 Length and tone

A typical Slop Report runs **20 to 30 pages** including the appendix. The tone is technical, evidence-driven, and explicitly non-recommendatory. The Slop Report does not say "you should do X." It says "dimension Y is absent in this codebase, the published threshold is Z, the cited evidence is at file:line." Recommendations live in the Escape Pod Proposal, not in the Slop Report. This separation matters: it lets the client engage with the findings as facts before the engagement asks them to act on them.

### 6.3 SOC 2 deliverable extraction (optional, when the client has SOC 2 in scope)

When the client has SOC 2 Type I or Type II as a stated compliance goal, the assessor produces a *secondary deliverable* alongside the Slop Report: a SOC 2-mapped summary of the audit findings, organized by Trust Services Criteria control reference, suitable for inclusion in the client's SOC 2 evidence package as the technical-controls portion of their compliance trail. This deliverable is not a new audit. It is a *re-organization* of the Slop Report's existing findings into a structure that a SOC 2 auditor recognizes, with the per-dimension scores re-keyed to the per-control TSC vocabulary the auditor uses.

The methodology already contains the technical work. Every dimension in Section 4 maps to one or more SOC 2 TSC controls in its header block. The SOC 2 deliverable is the inverse mapping: instead of presenting findings by dimension number, it presents findings by control reference. The transformation is mechanical and adds approximately 2 hours to Day 5 of the audit walkthrough. The CIO carrying the Slop Report into a CPC meeting can also carry the SOC 2 deliverable into the next conversation with their SOC 2 auditor, which is asymmetric value: the engagement pays for itself twice from a single body of audit work.

#### 6.3.1 Structure of the SOC 2 deliverable

The deliverable is a standalone document approximately 6–10 pages plus appendix, with the following structure:

```
SOC 2 TECHNICAL-CONTROLS EVIDENCE EXTRACT
[Client name]: [Codebase name]
Source: Slop Report dated [YYYY-MM-DD] (referenced)
Methodology: Open Honest methodology v[VERSION] (referenced)
Methodology version: commit [HASH]

== SCOPE STATEMENT (½ page) ==
This deliverable covers the technical controls visible in the codebase. It does not
cover SOC 2 in-scope items that lie outside the codebase: organizational policy
documentation, personnel security and background checks, vendor management
procedures, physical and environmental security, business continuity planning,
or risk assessment processes. The CIO must obtain coverage of those items
through other evidence sources before submission to a SOC 2 auditor.

The technical-controls subset covered here is the portion that derives from
inspection of the production codebase, configuration files, deployment
artifacts, and git history of [Codebase name] over the period [date range].

== EXECUTIVE SUMMARY (½ page) ==
- Total SOC 2 Common Criteria evaluated: N
- Substantially compliant: X
- Partially compliant: Y
- Non-compliant: Z
- Single recommended next step (one sentence)

== PART I. PER-CONTROL FINDINGS (4-6 pages) ==
A table or sequence of entries, one per SOC 2 TSC control reference. Each entry
contains:

  Control reference: [e.g., CC6.1]
  Control name: [Logical and Physical Access Controls]
  Trust Services Criterion: [Security / Availability / Confidentiality / Processing Integrity / Privacy]
  Source dimensions in the Slop Report: [4.1 Entitlement system, 4.2 Authentication]
  Per-dimension scores from the Slop Report:
    - 4.1 Entitlement system: [PRESENT / PARTIAL / ABSENT], evidence at [files:lines]
    - 4.2 Authentication: [PRESENT / PARTIAL / ABSENT], evidence at [files:lines]
  Bottom-line per-control finding:
    SUBSTANTIALLY COMPLIANT / PARTIALLY COMPLIANT / NON-COMPLIANT
  Reasoning: One paragraph explaining how the dimension scores roll up to the
    per-control finding, citing the published threshold for the control.

== PART II. CONTROLS NOT EVALUATED BY THIS METHODOLOGY (½ page) ==
Explicit list of SOC 2 controls that are *not* in scope for the slop audit
methodology, with one sentence per control explaining why and pointing the
client to alternative evidence sources. This section is load-bearing: a SOC 2
auditor receiving this deliverable must be able to see exactly which controls
the deliverable does and does not cover, with no ambiguity.

== APPENDIX. CONTROL-TO-DIMENSION MAPPING (1-2 pages) ==
The full mapping table: every SOC 2 TSC control reference covered by Section 4
of the methodology, with the dimensions that bear on it. This appendix is
reused across engagements (it is a property of the methodology, not of the
specific client), so the assessor can copy it from a template rather than
re-deriving it each time.
```

#### 6.3.2 Per-control roll-up rules

The roll-up from per-dimension scores to a per-control finding follows fixed rules so that the deliverable's bottom-line findings are reproducible. The rules:

- **Substantially compliant.** All dimensions bearing on the control score *Present*, AND the cited evidence in the Slop Report supports the published threshold for the control as written by AICPA TSC documentation. A control with one bearing dimension that scores *Present* is *Substantially compliant* on this control alone; a control with three bearing dimensions all of which score *Present* is *Substantially compliant* on all three.
- **Partially compliant.** At least one bearing dimension scores *Partial*, OR one dimension scores *Absent* while others score *Present* and the *Absent* dimension is not the control's primary driver. The deliverable's reasoning paragraph must name which dimension scored *Partial* or *Absent* and explain why the control is still partially supportable.
- **Non-compliant.** The control's primary driver dimension scores *Absent*, OR all bearing dimensions score *Absent* or *Partial* with no *Present* among them. *Non-compliant* findings require the most careful reasoning paragraph because the SOC 2 auditor will read it most closely.

The "primary driver" of each control is identified once in the appendix mapping table and is reused across engagements. For example, the primary driver of CC6.1 (Logical and Physical Access Controls) is dimension 4.1 (Entitlement system); CC6.3 (Authorization) is also primarily driven by 4.1; CC8.1 (Change Management) is primarily driven by 4.10 (CI/CD) and 4.16 (SDLC with AI safeguards).

#### 6.3.3 Worked example: CC6.1 entry

```
Control reference: CC6.1
Control name: Logical and Physical Access Controls
Trust Services Criterion: Security
Source dimensions in the Slop Report: 4.1 Entitlement system (primary), 4.2 Authentication (primary)
Per-dimension scores:
  - 4.1 Entitlement system: PRESENT
    Evidence: src/middleware/authz.py:14-87, db/migrations/V003__permissions.sql:1-42,
              tests/integration/test_authz.py:1-180. The application enforces
              per-endpoint authorization via a structured permission model with
              deny-by-default behavior, audited at every grant and denial.
  - 4.2 Authentication: PRESENT
    Evidence: src/auth/passwords.py:1-65, src/auth/sessions.py:1-120,
              docs/security/authentication.md:1-45. The application uses bcrypt
              for password storage, server-side session token revocation, and
              second-factor enforcement on the admin role.

Bottom-line per-control finding: SUBSTANTIALLY COMPLIANT

Reasoning: Both primary-driver dimensions for CC6.1 score Present in the
underlying audit. The published threshold for CC6.1 (per AICPA TSC 2017 with the
2022 points of focus) requires that "the entity implements logical access
security software, infrastructure, and architectures over protected information
assets to protect them from security events to meet the entity's objectives."
The audited codebase implements logical access via per-endpoint authorization
backed by a structured permission model and authentication via industry-standard
hashing and session management, with cited evidence supporting both. A SOC 2
Type II auditor reviewing this evidence would record CC6.1 as a passing control
contingent on the operational evidence (continuous monitoring and incident
response over the audit period) which is outside the scope of this technical-
controls extract — see Part II.
```

#### 6.3.4 Time budget and assessor effort

Approximately 2 hours on Day 5 for an experienced assessor who has already produced the Slop Report. The work is mostly mechanical re-keying:

1. Walk the SOC 2 control list (the TSC Common Criteria, plus any of the supplementary categories — Availability, Confidentiality, Processing Integrity, Privacy — that the client has in scope)
2. For each control, look up the bearing dimensions from the appendix mapping table
3. Pull the per-dimension scores from the Slop Report and copy them into the per-control entry
4. Apply the roll-up rule to determine the bottom-line finding
5. Write the reasoning paragraph using the published threshold for the control as the comparison point
6. Verify Part II (controls not evaluated) covers everything the client's SOC 2 scope includes that the methodology cannot inspect

**The 2-hour budget assumes the appendix mapping table already exists.** Building the mapping table the first time takes longer (approximately 4–6 hours for an L3 assessor working through Section 4 dimension by dimension and matching each to the relevant TSC control references). Once built, the mapping table is reused across all subsequent engagements with no re-derivation.

#### 6.3.5 What the SOC 2 deliverable does NOT do

This deliverable is technical-controls evidence, not SOC 2 certification. The CIO must understand and the deliverable's scope statement must make explicit:

- **It does not cover non-technical SOC 2 controls.** Personnel security, vendor management, physical security, organizational policies, business continuity planning, risk assessment — all of these are SOC 2 in-scope and *none* are in the slop audit's instrument. The CIO must obtain those from other sources.
- **It does not produce a SOC 2 certificate.** Only an AICPA-licensed CPA firm can issue a SOC 2 Type I or Type II report. This deliverable is *evidence the CPA firm can use*, not a substitute for the CPA's audit work.
- **It does not cover the operational evidence period.** SOC 2 Type II requires evidence of *continuous operation* of the controls over a defined period (typically 6–12 months). The slop audit is a point-in-time snapshot of the codebase. The CIO needs operational logs, change records, and incident reports from the period to complete the Type II evidence — the deliverable can identify which controls are technically supportable but not which controls have been continuously operated.
- **It does not address controls that rely on observation of human behavior.** Several SOC 2 controls (e.g., CC1.1 on integrity and ethical values, CC1.4 on commitment to competence) require auditing organizational behavior, not technical artifacts. The deliverable does not pretend to cover those controls.

The scope statement at the top of the deliverable enumerates exactly what is and is not covered, in language a SOC 2 auditor will recognize. Overstating the scope is the failure mode that destroys this deliverable's value: an auditor receiving an evidence package that overstates its coverage will reject it and discount everything else the engagement produced.

#### 6.3.6 Pricing and bundling

The SOC 2 deliverable is bundled into the Phase 0 engagement at no separate charge. The marginal effort is small (~2 hours on Day 5), the value to the CIO is large (a SOC 2-ready evidence trail that competitors cannot match without doing the underlying audit work), and the bundled inclusion creates a structural moat for the engagement: any competing Phase 0 audit instrument that does not produce a SOC 2 deliverable looks half-finished by comparison. Charging separately for the deliverable would convert this moat into a line item, which is the wrong trade.

The exception is if the client wants the full SOC 2 evidence package across all controls including the non-technical ones (organizational, personnel, vendor, physical). That is a different engagement model — closer to a traditional SOC 2 readiness assessment — and is out of scope for the slop audit Phase 0. If the client asks for it, refer them to a CPA firm or a dedicated SOC 2 readiness consultancy. The slop audit's competitive position is "we deliver the technical-controls portion as a free byproduct of Phase 0," not "we are a SOC 2 readiness shop."

### 6.4 The single most important sentence

Every Slop Report contains, somewhere in the executive summary, the sentence:

> "These findings are produced from [Client]'s own repository. They are not vendor analysis; they are observations about code [Client] owns and operates."

This sentence does more work than any other in the document. It is the line the CIO will quote in the CPC meeting. It is the line that converts the Slop Report from "consultant pitch" into "internal evidence."

---

