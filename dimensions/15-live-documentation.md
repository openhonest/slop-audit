### 4.15 Live documentation

**Lifecycle category.** Governance.

**Drafted under the four-layer model.**

**Definition.** Live documentation is the documentation that *stays current as the code changes*, that *describes what currently exists* (not what previously existed or what the team wishes existed), and that *answers the questions a new developer or future maintainer would actually ask*. A mature live-documentation discipline updates documentation in the same commits as the code it describes, includes sequence diagrams or state diagrams for non-linear parts of the system, and writes inline comments that explain reasoning rather than restate code. The opposite is the documentation that describes a system that no longer exists, that references functions that have been deleted, and that nobody has read in 18 months because everyone learned long ago that it's wrong.

**Industry threshold.** Documentation updated alongside code changes; architecture docs current within 90 days of related code changes; doc references to code entities (functions, classes, files) all currently exist in the code; setup instructions work end-to-end if followed literally. Drawn from DORA 2024 (which found that teams with high-quality documentation are 2x more likely to meet reliability targets), Wen et al. (ICSE 2024) which documented that 82.3% of projects have outdated code references and 40.7% of documents become outdated, Aghajani et al. (ICSE 2019)'s study of 878 documentation artifacts, and Zhi et al. (2021)'s systematic mapping of 63 documentation studies.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- DORA 2024: 2x reliability with high-quality docs — Tier 1
- Wen et al. (ICSE 2024): 82.3% outdated code references — Tier 3
- Aghajani et al. (ICSE 2019): 878 doc artifacts — Tier 3
- Zhi et al. (2021): systematic mapping of 63 studies — Tier 3

**Compliance framework mappings.**
- **NIST SP 800-53:** SA-5 (Information System Documentation), CM-3 (Configuration Change Control)
- **SOC 2 Trust Services Criteria:** CC2.1 (Communication of Information)
- **ISO/IEC 26514:2022:** Systems and software engineering — Design and development of information for users

---

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Run Layer 1 indicators L1.1, L1.3, and L1.4.** These already measure documentation volume and freshness from the git history. L1.1 (doc-only commit ratio), L1.3 (mixed doc+code commit ratio), and L1.4 (doc lines as percentage of total) collectively indicate whether documentation is being written and updated. If all three are in the slop range, this dimension scores at most *Partial* on the Layer 2 form regardless of any other inspection.
2. **Cross-reference recent commits with documentation updates.** Pick 3 commits from the last 30 days that touched code in a major module. For each commit, check whether the documentation associated with that module was updated in the same commit, in a sibling commit, or not at all. Record the result.
3. **Function/class existence check.** Pick 5 random doc references to functions, classes, or files. Use `grep` to confirm that each referenced entity still exists in the code. Record any references that point to entities that no longer exist.
4. **Setup instructions check.** Read the README's setup instructions. Identify the files, ports, services, and commands that the instructions reference. Use `grep` and `find` to confirm that each referenced thing still exists. Do not actually run the instructions (that would take longer than the time budget allows for Layer 2); just check that the things they reference are still in place.
5. **Inline comment density and currency check.** Sample 3 of the 10 most-modified files in the last 90 days. Count the inline comments in each. Determine whether comments describe the current state of the code or refer to behavior that no longer exists.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Five markers, each scored present / partial / absent.

**Marker 1: The "why does this exist?" answer.** Read the README. Determine whether the first 200 words answer the question *why does this software exist?* (what problem it solves, who it's for, what it replaces or improves on). A README that answers this question is written for a reader who has never seen the software. A README that jumps straight to "to install, run `npm install`" is written for a reader who already knows what the software is and only needs setup help. The first kind serves new developers; the second does not. Score: present if the first 200 words answer "why," partial if the question is answered later in the README, absent if it is never answered.

**Marker 2: Documentation describes current behavior, not historical behavior.** For the 5 most-modified production files in the last 90 days, find the documentation that describes them (a sibling `.md` file, a section in the architecture doc, an ADR, or a docstring at the top of the file). For each, determine whether the documentation describes what the code *currently* does. If the documentation describes a function signature that no longer exists, a behavior that has been removed, or a workflow that has been replaced, the documentation is historical, not live. Score: present if 4 or 5 of 5 are current, partial if 2 or 3, absent if 0 or 1.

**Marker 3: Setup instructions work for an outsider.** Read the README's setup instructions as if you were a new developer who has never touched the project. Ask yourself: *if I follow these literally, with no insider knowledge, will they work?* Specifically: do they assume software is installed that they don't tell you to install? Do they assume environment variables exist that they don't tell you to set? Do they assume you have credentials that they don't tell you how to obtain? Do they assume you know what `make seed` does? Score: present if a literal follow-through would work end-to-end, partial if 1 or 2 assumptions are uncovered, absent if 3 or more assumptions are uncovered or if any assumption is fundamental (e.g., the instructions assume you have a database but don't tell you how to provision one).

**Marker 4: Inline comments explain reasoning, not code.** Sample 3 of the most-modified production files in the last 90 days. Read each inline comment and categorize it as either *describing* (what the code does, restating the obvious in English) or *reasoning* (why the code was written this way, what alternative was rejected, what edge case the code handles, what surprise the next reader should know about). Reasoning comments are valuable; describing comments are noise that decays with the code. Score: present if ≥70% of comments in sampled files are reasoning, partial if 30–70%, absent if <30%.

**Marker 5: Diagrams for non-linear systems.** Identify the parts of the system that are inherently non-linear: state machines, workflows with branches, distributed systems with multiple actors, asynchronous message flows, deployment topologies. For each non-linear subsystem, check whether the documentation includes a diagram (sequence diagram, state diagram, architecture diagram, deployment diagram). Prose-only documentation of non-linear systems is documentation that the reader cannot reconstruct the actual system from. Score: present if every non-linear subsystem has at least one diagram, partial if some do, absent if no diagrams exist for any non-linear subsystem.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 4 or 5 markers score Present. *Partial* if 2 or 3 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the documentation actually *useful* in practice? (A new developer's onboarding time is the truest measure but cannot be assessed in Phase 0.)
- Is the documentation *well-organized* in the deeper sense? (Information hierarchy, navigation paths, cross-references.)
- Does the documentation have the *right level of detail* for its audience? (Too little is unhelpful; too much is unread.)
- Is the documentation written *for a future maintainer* or only *for the original author*?
- Is the documentation honest about *what the system does badly* and where the rough edges are?

---

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (Layer 1 indicators healthy, recent commits show mixed doc+code updates, doc references all exist, setup instructions reference existing artifacts) AND Layer 3 form scores Present (4–5 of 5 markers).
- ***Partial.*** Layer 2 passes but Layer 3 has gaps (2–3 markers Present); OR Layer 2 is Partial (some Layer 1 indicators not healthy, some doc references stale) but Layer 3 scores Present.
- ***Absent.*** Layer 2 fails (Layer 1 indicators in slop range, multiple stale doc references, setup instructions reference deleted artifacts); OR Layer 2 passes but Layer 3 scores Absent (0–1 markers Present).

**Common failure modes.**

- **The setup-only README.** The README is 30 lines, all of them setup instructions. There is no answer to "why does this exist?" Layer 3 fails Marker 1.
- **The historical architecture doc.** A 60-page architecture document was written 3 years ago and has not been updated since. The code has moved past it. The architecture section on the authentication subsystem describes a JWT-based system; the actual code uses session cookies. Layer 3 fails Marker 2.
- **The setup instructions that almost work.** The README says "install Postgres, then run `make migrate`." A new developer follows this and hits an error because `make migrate` requires `DATABASE_URL` to be set, which is not mentioned. Layer 3 fails Marker 3.
- **The describing-comment style.** Files are full of comments like `// loop through users` immediately above `for user in users:`. The comments add no information and rot the moment the code changes. Layer 3 fails Marker 4.
- **The prose-only state machine.** The order processing subsystem is a state machine with 11 states and 23 transitions. The documentation describes it in prose: "When an order is in PENDING state, it can transition to AWAITING_PAYMENT or CANCELLED, depending on..." Three pages of this. No diagram. Layer 3 fails Marker 5.
- **The auto-generated documentation that is also empty.** The codebase uses Sphinx, JSDoc, JavaDoc, or similar to auto-generate documentation. The generated documentation exists but is just function signatures with no docstring content. Layer 2 might pass volume checks; Layer 3 fails because the generated content has no value.
- **The wiki nobody can find.** The "real" documentation is on a Confluence wiki that is not linked from the README. New developers spend their first week reverse-engineering the codebase before discovering the wiki exists. Layer 2 fails on the README check.
- **The CHANGELOG that is also the architecture document.** The team's only architecture documentation is a chronological CHANGELOG of changes. To understand the current architecture, a reader has to read the entire CHANGELOG and mentally apply each change in order. Layer 3 fails Marker 2 (no current state description, only historical changes).

**Example presence (Java / well-documented Spring Boot).** A Java Spring Boot application with a `README.md` whose first paragraph reads: "This service handles billing for the Acme platform. It receives subscription events from the payment processor, applies them to customer accounts, generates invoices, and notifies customers via email. It exists because the previous monolith conflated billing with order management, which made changes risky and audit trails incomplete." The README then has setup instructions that work literally: install JDK 17, install Docker, clone the repo, run `make seed-test-data`, run `make run`, open `http://localhost:8080/health`. The instructions reference 5 things; all 5 exist.

The codebase has `docs/architecture.md` (1,800 words, prescriptive), 23 ADRs in `docs/adr/`, and sequence diagrams in `docs/diagrams/` for the four non-linear flows: subscription state machine, payment retry flow, dunning workflow, and refund processing. The most recent 5 ADRs all reference the architecture document. The 5 most-modified files in the last 90 days have docstrings at the top of each that describe the current behavior; one of them was updated in the same commit as a recent code change to that file (visible in `git log -p`). Inline comments in those files are predominantly reasoning ("we retry up to 5 times here because Stripe occasionally returns 429 on burst traffic; the backoff schedule is taken from their published recommendations"). The Layer 2 form passes; the Layer 3 markers all score Present.

**Example absence (Python / undocumented Flask).** A Python Flask application with a `README.md` that contains only: "# myapp\n\nTo install, see the wiki." The wiki is on Confluence and is not linked from the README. The codebase has no `docs/` directory, no ADRs, and no architecture document. Sampled docstrings on the 5 most-modified files describe behavior that no longer exists (one docstring describes a `validate_user` function that was renamed to `check_user_credentials` 4 months ago). The setup instructions in the wiki, when followed literally, fail at step 3 because they reference a `db.config.example` file that was deleted 8 months ago. Inline comments are dominated by `# loop` and `# return` (describing comments). The order processing subsystem has 14 states and 31 transitions; it is documented as a 4-paragraph prose description in the wiki with no diagram. The Layer 2 form fails on the doc-reference check and the setup-instructions check. The Layer 3 form fails on every marker. The dimension scores Absent.

**Time budget.** Approximately 60 to 90 minutes for an experienced assessor: 20 to 30 minutes for the Layer 2 mechanical inspection (Layer 1 indicators are already computed), 40 to 60 minutes for the Layer 3 marker assessment.

---

