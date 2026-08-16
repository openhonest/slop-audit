## 4. Layer 2. Per-dimension evidence-based assessment

**Status: catalog stub. The 18 dimensions will be drafted as a separate piece of work.**

This section will contain the operational version of the 18 enterprise audit dimensions. Each dimension will be presented in the same template:

```
### 4.X [Dimension name]

**Lifecycle category.** [Security architecture / Data architecture / Compliance engineering / Operational security / Performance engineering / Operations / DevOps / Infrastructure / Software architecture / Governance / Process engineering / Lifecycle management / Software development]

**Definition.** [One paragraph in plain language]

**Industry threshold.** [The minimum threshold a financial services auditor or technology risk committee would apply, drawn from named published sources]

**Source citations.** [Tier 1 / Tier 2 / Tier 3 / Tier 4 industry sources, drawn from Appendix C of the source analysis]

**Compliance framework mappings.** [SOC 2 sections, NIST 800-53 control families, OWASP ASVS controls, OSFI B-13 sections, NI 31-103 sections, FFIEC booklets, SIG question domains as applicable]

**Evidence inspection procedure.** [Specific files, configurations, patterns, and commands the assessor inspects to determine the score]

**Scoring rubric.**
- *Present:* [Concrete criteria for a "present" score, drawn from the published threshold]
- *Partial:* [Concrete criteria for a "partial" score]
- *Absent:* [Concrete criteria for an "absent" score, drawn from the unstructured-condition vocabulary in paper §4.1]

**Common failure modes.** [Patterns the assessor recognizes as evidence of absence, drawn from paper §4.1 and from contrasts between the structured and unstructured Buckler codebases]

**Examples (two per dimension, in two different languages).** Each dimension provides a *Present* example in one language and an *Absent* example in a different language. The language pairings rotate across the 18 dimensions so that the catalog as a whole exercises Python, TypeScript, Java, C#, Go, and Ruby. The purpose is to train recognition across paradigms rather than to recommend a stack.

**Time budget.** [Approximately N minutes for an experienced assessor on a typical mid-size codebase]
```

The 18 dimensions, in lifecycle category order:

| # | Dimension | Lifecycle category | Drafting status |
|---|---|---|---|
| 4.1 | Entitlement system | Security architecture | **v0 drafted (batch 1, retrofitted to four-layer model)** |
| 4.2 | Authentication | Security architecture | **v0 drafted (batch 1, retrofitted to four-layer model)** |
| 4.3 | Inter-service security | Security architecture | **v0 drafted (batch 1, retrofitted to four-layer model)** |
| 4.4 | Multi-tenancy | Data architecture | **v0 drafted (batch 2, retrofitted to four-layer model)** |
| 4.5 | Audit infrastructure | Compliance engineering | **v0 drafted (batch 2, retrofitted to four-layer model)** |
| 4.6 | Rate limiting | Operational security | **v0 drafted (batch 2, retrofitted to four-layer model)** |
| 4.7 | Configuration and secrets management | Operational security | **v0 drafted (batch 3, retrofitted to four-layer model)** |
| 4.8 | Caching | Performance engineering | **v0 drafted (batch 3, retrofitted to four-layer model)** |
| 4.9 | Notifications | Operations | **v0 drafted (batch 3, retrofitted to four-layer model)** |
| 4.10 | CI/CD | DevOps | **v0 drafted (batch 4, retrofitted to four-layer model)** |
| 4.11 | Containerization | Infrastructure | **v0 drafted (batch 4, retrofitted to four-layer model)** |
| 4.12 | Dependency injection | Software architecture | **v0 drafted (batch 4, retrofitted to four-layer model)** |
| 4.13 | Pattern sophistication | Software architecture | **v0 drafted (batch 5, four-layer model)** |
| 4.14 | Architectural philosophy | Software architecture | **v0 drafted (batch 5, four-layer model)** |
| 4.15 | Live documentation | Governance | **v0 drafted (batch 5, four-layer model)** |
| 4.16 | SDLC with AI safeguards | Process engineering | **v0 drafted (batch 6, four-layer model)** |
| 4.17 | Tech debt management | Lifecycle management | **v0 drafted (batch 6, four-layer model)** |
| 4.18 | UX from code | Software development | **v0 drafted (batch 6, four-layer model)** |

Section 4 drafting is complete in v0 form under the four-layer model across all 18 dimensions. Total length of Section 4: approximately 45,000 words. Next work items are substantive review, marker tightening, and calibration against the Section 7 validation set — not further drafting.
