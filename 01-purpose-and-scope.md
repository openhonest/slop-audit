## 1. Purpose and scope

### 1.1 What the slop audit produces

A **Slop Report**: a structured technical assessment of one client codebase against the 18 enterprise audit dimensions, with quantified findings and per-dimension evidence citations. The Slop Report is the central deliverable of Phase 0 of an Open Honest engagement. It serves three downstream purposes:

1. **Internal evidence for the client's CIO.** The findings come from the client's own repository. They are not disputable as "vendor narrative" because they are produced from material the client themselves provided. This is what makes the Slop Report politically actionable inside the client organization.
2. **Input to the Self-Service Gap Analysis** (the second Phase 0 deliverable). The audit identifies which architectural conditions are absent in the client's existing codebase, which in turn constrains what business-user self-service can be safely supported on the existing substrate.
3. **Input to the Escape Pod Proposal** (the third Phase 0 deliverable). The audit findings determine which greenfield candidate modules are most defensible as the first Phase 1 build target, by showing which audit dimensions are most catastrophically absent in the existing landscape.

### 1.2 What the slop audit does not produce

The slop audit is **not** a deep architectural review. It is **not** a complete remediation plan. It is **not** a recommendation about which AI tools to use or stop using. It overlaps with automated code-quality tools (SonarSource, CodeScene) on some mechanical indicators (dead code, duplication) but goes substantially further in two directions those tools do not cover: compliance-framework mapping (SOC 2, NIST 800-53, OSFI B-13, OWASP ASVS) and finite testability measurement (mutable state ratio, decision-space coverage, test determinism). It also includes human-judgment layers (Layer 3 specified markers and Layer 4 architectural synthesis) that no automated tool can provide.

In particular, the slop audit deliberately does not include the per-function pattern review that characterizes Phase 1 architectural oversight. That work uses different inputs, requires different skills, and produces different outputs (qualitative findings with concrete recommendations rather than quantified dimension scores). Section 2 of this document defines the boundary explicitly so that trained assessors do not accidentally try to do Phase 1 work during Phase 0.

### 1.3 Who runs it

A trained assessor working alone or in pairs. Training requirements are defined in Section 8 of this document. The methodology is designed so that an experienced senior developer with one to two weeks of targeted training can run it consistently. It does not require the elite architectural judgment that Phase 1 oversight requires. This is the central design property of the methodology: it is the part of the engagement that can be executed by anyone trained on this document, not only by the original architect.

### 1.4 Scope of one audit

One audit assesses **one codebase**. A "codebase" is a single git repository, a single deployable application, or a single bounded service. Multi-repository platforms require either multiple audits or a scope decision about which repository carries the most diagnostic weight for the assessment. The default scope choice is the repository the client identifies as most representative of their current AI-assisted development practice.

One audit takes approximately **3 to 5 working days** for a single trained assessor on a codebase of 50,000 to 250,000 lines of code. Larger codebases scale roughly linearly. Smaller codebases (under 20,000 LOC) can be audited in 1 to 2 days. The walkthrough timing is detailed in Section 5.

---

