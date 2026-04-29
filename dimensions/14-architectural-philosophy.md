### 4.14 Architectural philosophy

**Lifecycle category.** Software architecture.

**Drafted under the four-layer model.** This is the dimension where the four-layer model adds the most value, because the meaningful assessment of architectural coherence is qualitative-but-trainable rather than purely mechanical.

**Definition.** Architectural philosophy is the codebase's coherent, articulated, and consistently applied set of architectural commitments. A mature codebase has a *stated* philosophy (written down somewhere a new developer can read it), the philosophy is *prescriptive* (it tells the developer what to do, not just what currently exists), the philosophy *covers the standard architectural decisions* (data, auth, deployment, errors, scaling, observability, change management), and the modules in the codebase *implement* the philosophy when read with the philosophy in hand. The opposite is the codebase that is the accumulated result of many uncoordinated decisions, where every module reflects whoever wrote it that week, and where there is no answer to the question "what is this team's architectural style?"

**Industry threshold.** A coherent articulated philosophy that the modules implement consistently. Drawn from Brooks's *The Mythical Man-Month* Chapter 4 ("Aristocracy, Democracy, and System Design," which argues that conceptual integrity is the most important consideration in system design), Iaakov Exman's 2017–2018 work on conceptual integrity via linear algebra, Ford / Parsons / Kua's *Building Evolutionary Architectures*, Baldwin & Clark's *Design Rules: The Power of Modularity*, ArchUnit (the runtime tool that enforces architectural rules in JVM codebases), the SEI ATAM (Architecture Tradeoff Analysis Method), and ISO/IEC 25010:2023 quality characteristics.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Brooks, *The Mythical Man-Month* Ch. 4 (1975/1995) — Tier 1 (foundational)
- Iaakov Exman (2017–2018): conceptual integrity via linear algebra — Tier 3
- Ford, Parsons, Kua: *Building Evolutionary Architectures* (O'Reilly, 2017/2023) — Tier 2
- Baldwin & Clark: *Design Rules: The Power of Modularity* (MIT Press, 2000) — Tier 1
- ArchUnit, SEI ATAM, ISO/IEC 25010:2023 — Tier 1
- Colfer & Baldwin: *The Mirroring Hypothesis* (Harvard, 2016) — Tier 3

**Compliance framework mappings.**
- **ISO/IEC 25010:** All quality characteristics (architectural philosophy is the prerequisite for satisfying any of them coherently)
- **NIST SP 800-160:** Systems Security Engineering — architectural coherence as a security property

---

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Locate the architecture document.** Look for `ARCHITECTURE.md`, `docs/architecture/`, `docs/adr/`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md` (if it has an architecture section), or a wiki link that the README points to. Record what exists and what does not.
2. **Locate ADRs (Architecture Decision Records).** Count the number of ADRs and read the most recent 5. ADRs are the most defensible evidence that the team thinks about architectural decisions deliberately.
3. **Sample for structural consistency.** Pick 5 random modules from different parts of the codebase. For each, record: the file structure (which files exist, in what arrangement), the naming convention (camelCase, snake_case, PascalCase, mixed), the error handling pattern (exceptions, result types, null returns, mixed), the import organization (alphabetized, grouped, ad hoc), and the test file location (alongside source, in a parallel tree, separate repo).
4. **Quantify the structural consistency.** For each of the five attributes above, count how many of the 5 sampled modules use the same convention. Total uniformity = 5/5 on every attribute; total drift = 1/5 on every attribute. Record the score per attribute.
5. **Check for an enforcement mechanism.** Look for ArchUnit tests (Java), `import-linter` (Python), `eslint-plugin-boundaries` (TypeScript), `dependency-cruiser` (any), or other tools that enforce architectural rules at build time. Their presence is positive evidence that the team believes the philosophy enough to enforce it; their absence is not necessarily disqualifying but is a missed opportunity.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Five markers, each scored present / partial / absent.

**Marker 1: Prescriptive vs descriptive language.** Read the architecture document. Determine whether the language is *prescriptive* ("we always X, never Y", "all new modules must X", "the convention is X", "the boundary between A and B is sacred") or *descriptive* ("we have controllers and services", "the data layer is separate from the business layer", "errors are handled in the controller"). Prescriptive language is evidence that the document is a *commitment*; descriptive language is evidence that the document is *just an enumeration of what currently exists*. Score: present if the document is predominantly prescriptive, partial if it is mixed, absent if it is purely descriptive (or if no document exists).

**Marker 2: Coverage of the standard architectural decisions.** A mature philosophy covers seven specific architectural areas: (a) data architecture (how the database is structured and accessed), (b) authentication/authorization model, (c) deployment topology, (d) error handling strategy, (e) scaling story, (f) observability strategy, (g) change management / versioning. Read the architecture document and ADRs and check which of these seven are addressed prescriptively. Score: present if 6 or 7 are covered, partial if 4 or 5 are covered, absent if 3 or fewer.

**Marker 3: Module-philosophy alignment.** Pick 3 random modules from different parts of the codebase. Read each *with the philosophy document open*. For each module, ask: *which prescriptive statements in the philosophy is this module implementing?* If the assessor can identify specific philosophy statements being implemented, the module is aligned. If the assessor can read the entire module without finding any philosophy statement that the module implements, the module is detached from the philosophy. Score: present if 3 of 3 modules are aligned, partial if 2 of 3, absent if 0 or 1.

**Marker 4: Convergent solutions to similar problems.** Pick 2 modules from different parts of the codebase that solve similar problems. Common candidates: two different services that both handle pagination, two controllers that both validate input, two background jobs that both retry on failure, two feature modules that both expose a CRUD interface. Read both implementations. Determine whether they solve the problem the same way (convergent, evidence of philosophical commitment) or differently (divergent, evidence that the philosophy is not applied consistently). Score: present if the implementations are convergent on the problem-solving approach, partial if they are partially convergent (same general shape, different details), absent if they are clearly divergent.

**Marker 5: Decisions reference the philosophy.** Read the most recent 5 ADRs (if they exist) or the commit messages of the 5 most recent significant architectural changes. Determine whether they reference the philosophy document or its concepts. ADRs that reference the philosophy ("per ADR-007 we do not introduce new singletons") are evidence that the philosophy is alive in the team's daily work. ADRs that make decisions in isolation, with no reference to broader principles, are evidence that the philosophy is a document the team wrote once and never returned to. Score: present if ≥4 of 5 reference the philosophy, partial if 2 or 3, absent if 0 or 1.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 4 or 5 markers score Present. *Partial* if 2 or 3 markers score Present. *Absent* if 0 or 1 markers score Present.

**Note on the inter-rater reliability of this dimension.** This is the dimension whose Layer 3 markers are hardest to apply consistently. Two assessors may legitimately disagree on whether a piece of language is "prescriptive" or "descriptive," whether a module is "aligned" with a philosophy or "incidentally similar." The inter-rater calibration target for this dimension is therefore lower than other dimensions: trained assessors should agree on at least 3 of 5 markers (instead of 4 of 5). If agreement drops below this on a calibration codebase, the markers need revision.

#### Layer 4 questions (deferred to Phase 1)

- Is the philosophy actually a *good* philosophy for this organization's domain? A philosophy can be coherent and consistently applied but still be the wrong philosophy for the problem.
- Are there hidden inconsistencies between the philosophy and the code that only an architect would notice? (For example, the philosophy says "we use event sourcing for all state changes" but in fact the inventory subsystem mutates state directly because event sourcing was inconvenient for that case.)
- Is the philosophy retrofitted to the code (justification of past decisions) or is the code built from the philosophy (commitment to a vision)?
- Would the philosophy survive contact with a serious scaling problem, a serious security incident, or a major regulatory change?
- Is the team's actual decision-making consistent with the documented philosophy, or does the team make decisions one way and document them another?

---

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (architecture document exists, ADRs exist, structural consistency on at least 4 of 5 attributes) AND Layer 3 form scores Present (4–5 of 5 markers).
- ***Partial.*** Layer 2 passes but Layer 3 has gaps (2–3 markers Present); OR Layer 2 is Partial (architecture document exists but is descriptive only, or structural consistency is on 2–3 of 5 attributes) but Layer 3 scores Present.
- ***Absent.*** Layer 2 fails (no architecture document at all, no ADRs, low structural consistency); OR Layer 2 passes but Layer 3 scores Absent (0–1 markers Present).

**Common failure modes.**

- **The README that is not a philosophy.** A `README.md` exists but it is purely setup instructions and a list of features. There is no architectural content. Layer 2 partial; Layer 3 absent on Marker 1 (no document means no prescriptive language).
- **The descriptive architecture document.** An `ARCHITECTURE.md` exists and runs to 800 words but the entire document is "we have controllers and services and repositories" with no prescriptive statements. Layer 3 fails Marker 1.
- **The aspirational document.** An architecture document exists and is fully prescriptive, but no module in the codebase actually implements any of its prescriptions. The document is the team's wish list, not their commitment. Layer 3 fails Marker 3.
- **Convergent on style, divergent on substance.** All modules use the same naming conventions and file structure but solve the same problems in different ways. Layer 2 passes the structural consistency check; Layer 3 fails Marker 4.
- **The dead document.** An architecture document exists, was written 4 years ago, and has not been touched since. The code has moved past it. ADRs reference the philosophy but the philosophy describes a system that no longer exists. Layer 3 partial on Marker 5.
- **Multiple architects, multiple philosophies.** The codebase has clear sub-regions, each with internal consistency but with different conventions across regions. The team's "philosophy" is actually the union of three or four separate philosophies that never reconciled. Layer 3 fails Marker 4 (divergent solutions to similar problems across the regions).
- **The "we believe in code, not documentation" team.** The team explicitly rejects written architecture documents as "premature codification." There is no document. Layer 2 fails immediately. Layer 3 fails on every marker.
- **Architecture by retrospective.** ADRs exist but they are written *after* decisions are implemented, to justify what was already done. The decision process did not actually involve consulting a philosophy; the philosophy was inferred backwards. Layer 3 partial on Marker 5 (ADRs reference the philosophy but the references are post-hoc).

**Example presence (Go / opinionated philosophy).** A Go application with an `ARCHITECTURE.md` at the repo root, 4,200 words, prescriptive throughout. Sample sentences: "We never return `nil, error` in pairs from constructors; constructors must produce a valid object or panic." "Every package exports at most one type; helpers stay private." "We do not use struct embedding for code reuse; embedding is reserved for interface composition only." "All errors at the package boundary are wrapped with `fmt.Errorf("packagename.FunctionName: %w", err)` so that error chains can be parsed by the observability layer." The document covers all 7 standard areas: data (PostgreSQL with `sqlc`-generated query code), auth (zero-trust per request, no sessions), deployment (single binary, no sidecars), errors (wrapping convention above), scaling (horizontal, no shared state), observability (OpenTelemetry, structured logs as JSON), versioning (semver on the binary, additive-only API changes).

There are 47 ADRs in `docs/adr/`, each ~300 words, each titled `ADR-NNN-decision-summary.md`. The most recent 5 ADRs each reference earlier ADRs by number. Sampled modules implement the philosophy: the user package exports one type, returns wrapped errors, has no struct embedding for reuse. Two modules that handle pagination both use a shared `pagination` package with the same `(items, nextCursor, error)` return signature. ArchUnit-equivalent enforcement is provided by a custom `make verify-architecture` script that runs `go-arch-lint` to enforce the package boundary rules. Layer 2 passes; Layer 3 markers all score Present.

**Example absence (C# / no philosophy).** A C# .NET 6 application that has been worked on by 14 different developers over 4 years. There is no `ARCHITECTURE.md`. The `README.md` is 80 words and contains only the setup steps. There are no ADRs. Sampled modules show every kind of inconsistency: three different naming conventions for service classes (`UserService`, `IUserManager`, `User_Handler`), four different error handling patterns (exceptions, `Result<T>`, `null` returns, `out` parameters), three different file structures (`Models/Controllers/Services`, `Features/User/UserController.cs`, `Domain/Application/Infrastructure`). Two modules that both handle pagination implement it differently: one uses LINQ `.Skip().Take()` with manual count, one uses a `PaginatedResult<T>` wrapper class with a `TotalPages` property. The team's stated philosophy when interviewed is "we go with whatever works for the feature." Layer 2 fails on every check; Layer 3 fails on every marker. The dimension scores Absent.

**Time budget.** Approximately 90 to 120 minutes for an experienced assessor: 30 to 45 minutes for the Layer 2 mechanical inspection, 60 to 75 minutes for the Layer 3 marker assessment. This is the longest dimension in Section 4 by time budget, reflecting the higher cognitive load of qualitative judgment.

---

