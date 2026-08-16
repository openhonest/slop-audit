## TODO

### Frame layer (drafted)
- [x] Section 1: Purpose and scope
- [x] Section 2: Four-layer model (Layer 1 mechanical, Layer 2 artifact, Layer 3 specified markers, Layer 4 deferred elite judgment)
- [x] Section 3: Layer 1 quantitative git-history methodology (twenty indicators)
- [x] Section 5: Conducting an audit (walkthrough)
- [x] Section 6: Slop Report template (with *Not applicable* score handling added for dimension 4.18)
- [x] Section 7: Validation protocol

### Catalog layer (drafted)
- [x] Section 4.1–4.6: Security architecture, data architecture, compliance engineering, operational security dimensions
- [x] Section 4.7–4.12: Performance, operations, DevOps, infrastructure, software architecture dimensions
- [x] Section 4.13–4.18: Software architecture, governance, process engineering, lifecycle, software development dimensions

### Review layer (in progress)
- [ ] Substantive review of Section 4 marker wording for consistency across dimensions (marker count ranges from 3 to 5 per dimension; verify this is justified per dimension and not drift)
- [ ] Cross-check inter-rater reliability targets: which dimensions declare a target explicitly, which should but do not
- [ ] Cross-check that every dimension flags at least one Layer 1 indicator when one is relevant (4.7→L1.14, 4.10→L1.10, 4.11→L1.11, 4.15→L1.1/L1.3/L1.4, 4.17→L1.5/L1.6/L1.7/L1.12)
- [ ] Verify the cross-language example rotation across dimensions (Python, TypeScript, Java, C#, Go, Ruby) — each dimension uses two different languages; the set as a whole should exercise all six

### Tooling layer
- [ ] `research/slop-audit-layer1.sh` reference script implementing the twenty indicators (including L1.12 dead-code analyzer, L1.13 PMD CPD invocation with token normalization, L1.14 gitleaks invocation, L1.15 language-specific type-escape counts, L1.16 trailing-whitespace scan, and L1.17 god-file enumeration, L1.18 mutable-state static analysis, L1.19 decision-space enumeration, L1.20 randomized test-order runs)
- [ ] Test the script on the positive control (honest-conversion branch of buckler/idd), validation availability 2026-04-30
- [ ] Test the script on a candidate negative control branch

### Validation layer (unblocked by catalog completion)
- [ ] Identify the negative control branch from the buckler/idd history
- [ ] Run the complete methodology on positive and negative controls (positive control available 2026-04-30 per `methodology/validation/protocol.md`)
- [ ] Run the cross-rater test (Adam plus one other reviewer)
- [ ] Produce a signed validation report

### Future methodological extensions (deferred to peer-reviewed framework papers, not added to v0)

The methodology v0 catalog of 18 dimensions corresponds to the operationalization of Wasserman 2026's natural experiment. Subsequent extensions to the catalog are deferred to standalone peer-reviewed framework papers rather than being added to v0 directly. Each extension will go through its own pre-registration, its own validation cycle, and its own peer-review process before being incorporated into a future v1.x catalog release. This protects v0's coherence as the ground-truth mapping to Paper 1 and converts each extension into a publishable methodological contribution rather than an unattributed catalog change. The Honest Foundation governance (when established) accepts framework extensions only after they have completed the peer-reviewed extension protocol, which is the structural protection against drift and against commercial-administrator capture.

**Candidate Dimension 4.19: Operational handoff readiness.** Measures what the development team prepared *before handing the system off to operations*, not what operations does after handoff. Stays on the dev side of the dev/ops boundary; does not measure operational practice itself. Compliance mappings: SOC 2 CC7.1 (system operations — detection of changes, monitoring), CC7.2 (anomaly detection); NIST SP 800-53 SA-15, IR-4, IR-8; OSFI B-13 §4.4 (technology operations); ISO/IEC 25010 reliability characteristics; ITIL v4 Service Transition (Release Management, Deployment Management) — first dimension where ITIL maps cleanly, which is significant for the Pink Elephant analogy in the the audit partner licensing structure.

Sketch of in-scope artifacts (for the future framework paper to validate):
- Runbooks (`docs/runbooks/`, `ops/runbooks/`) — presence, freshness, linkage to actual alerts and incidents
- On-call playbook entries — the per-alert "if you got paged for this, here is what it means and what to do"
- Operational logging configuration distinct from security audit logging — correlation IDs, request IDs, structured logs, log level discipline, log volume management
- Alerting rules as code (Prometheus rules, Datadog monitors-as-code, CloudWatch alarms in IaC) — the alerts the dev team configured *before* handoff
- Rollback procedures documented in runbooks and reflected in deployment automation
- Service ownership documentation: CODEOWNERS, on-call rotation references, escalation contacts
- Smoke tests / production verification scripts (`scripts/smoke-test/`, post-deploy CI stages)
- Known limitations / known issues documentation that hands off honestly rather than concealing known problems

Explicitly out of scope for the new dimension (these stay in their existing dimensions and must not be duplicated): health check endpoints (4.11 Containerization), container resource limits and autoscaling (4.11), rate limiting defaults (4.6), security audit logging (4.5), CI/CD pipeline structure (4.10), architecture diagrams (4.14, 4.15).

Suggested name: **Operational handoff readiness**. Rejected alternatives: "Production readiness" (too broad), "Day 1 operations" (jargony and inaccurate to scope), "Runbook discipline" (too narrow).

Drafting status: scope sketch only, written 2026-04-09. Full per-dimension entry in the four-layer template form (header, Layer 2 procedure, Layer 3 markers, Layer 4 questions, combined rubric, failure modes, two cross-language examples, time budget) is to be drafted as part of the future framework extension paper, not as part of v0.

**Other candidate extensions (placeholders, to be developed as the engagement model surfaces additional gaps):**
- [ ] Dimension TBD: data lifecycle management (retention, deletion, GDPR/Loi 25 right-to-be-forgotten enforcement at the code level)
- [ ] Dimension TBD: third-party dependency hygiene (SBOM presence, dependency freshness, security advisory integration, dependency licensing review)
- [ ] Dimension TBD: feature flag and progressive delivery discipline (flag definitions, flag lifecycle, kill-switch readiness)
- [ ] Dimension TBD: AI prompt and context management discipline (prompt versioning, context-window economy, model-version pinning) — this would be the first dimension specifically about AI tooling rather than about code that AI happens to have produced

Each candidate becomes a separate framework extension paper if and when it surfaces enough validation evidence to warrant publication. The cadence is "one extension paper per real engagement-driven gap" rather than "many speculative extensions in one paper." This matches the Pink Elephant / ITIL versioning model where each version is a substantive evolution justified by real-world experience rather than a speculative redesign.

### Training layer (methodology-side — curriculum-side TODO lives in `curriculum/README.md`)
- [x] Section 8 structural pass (curriculum tracks, levels, prior experience, reading, exercises, sign-off criteria, cross-rater protocol, recertification)
- [x] Track 1 L1 Apprentice structural description (Layer 1 only)
- [x] Track 1 L2 Practitioner structural description (Layers 1 + 2)
- [x] Track 1 L3 Lead structural description (Layers 1 + 2 + 3)
- [x] Track 1 L4 Trainer structural description (training delivery)
- [x] Track 2 LV1 → LV4 structural description (Layer 4 apprenticeship)
- [x] Prior experience summary table aligned with curriculum README
- [ ] Section 8 calibration-density pass v1 (blocked on validation cycle producing real cross-rater data)
- [ ] Consolidated bibliography appendix with full bibliographic entries (currently citations appear only inline in Section 4 headers and Section 8 reading list)

---

## Source attribution

This methodology operationalizes material from:

- Wasserman, A. Z. (2026). *Process Discipline as the Key Variable in AI-Assisted Enterprise Software Development: A Natural Experiment.* Zenodo. https://doi.org/10.5281/zenodo.19355460
- Wasserman, A. Z. (2026). *Enterprise Architecture Analysis: IDD Codebase.* Working analysis document, internal. Source for Sections 1, 2, 3, and the Section 4 catalog.
- Wasserman, A. Z. (2026). *Honest Code: Keep Your State Out of My Code.* Self-published. Source for Layer 3 reference patterns and the Honest Code chapter mapping.
- Wasserman, A. Z. (2026). *Honest Code Principles* (`honest-code-principles.md`). Source for Layer 3 pattern recognition.
- Wasserman, A. Z. (2026). *Contract Testing Methodology* (`contract-testing-methodology.md`). Source for Layer 3 verification patterns.

The 60+ industry sources cited per dimension in Section 4 are reproduced from Appendix C of the working analysis document. A consolidated bibliography appendix with full bibliographic information is still TODO; currently citations appear only inline in each dimension's header block.

The IP-sensitive material that exists in the source documents but is **deliberately excluded from this methodology**:

- The author's biographical credibility framing (IATA, CGI)
- IDD-specific assessment scores and evidence
- Buckler salary and cost data
- Patent-pending architectural details (the Zero Trust API mechanism)
- Internal Buckler organizational context

