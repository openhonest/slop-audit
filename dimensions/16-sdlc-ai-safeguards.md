### 4.16 SDLC with AI safeguards

**Lifecycle category.** Process engineering.

**Drafted under the four-layer model.**

**Definition.** An SDLC with AI safeguards is the discipline of writing the *specification before the code*, of expressing the specification in *executable form* (BDD scenarios, acceptance tests, contract tests) so that the AI agent has an unambiguous target, of placing *automated quality gates* between the AI's output and the main branch (pre-commit hooks, CI checks, mandatory review), and of treating AI-generated code as untrusted input that must clear the same gates as any other contribution. The opposite is the team that types a prompt, accepts the diff, runs the program once to see if it starts, and merges. The Wasserman 2026 paper documents this dimension as the single most consequential discriminator: of the 18 dimensions, this is the one whose absence most reliably predicts that all the others will also be absent.

**Industry threshold.** Spec-before-code on every non-trivial change (new endpoint, new workflow, new data model); BDD or acceptance tests written before implementation, not after; pre-commit hooks running formatter, linter, and type checker on every commit; CI gates that block merge on test failure, lint failure, type failure, or coverage drop; AI-generated code subject to the same review gates as human-written code with no carve-outs. Drawn from the Wasserman 2026 natural-experiment results, GitClear 2024 (which documented an 8x increase in copy-pasted blocks in AI-assisted code without safeguards), and the GitHub Copilot field studies (Ziegler et al., 2024) showing that productivity gains evaporate when downstream defect cost is included.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Wasserman 2026: natural experiment, structured-process arm 9–11x elite benchmark — Tier 1
- GitClear 2024: 8x copy-paste increase under AI assistance without safeguards — Tier 2
- Ziegler et al. (2024): Copilot productivity field study — Tier 2
- DORA 2024: deployment-frequency outcomes vs process discipline — Tier 1

**Compliance framework mappings.**
- **NIST SP 800-53:** SA-3 (System Development Life Cycle), SA-8 (Security Engineering Principles), SA-11 (Developer Testing and Evaluation)
- **SOC 2 Trust Services Criteria:** CC8.1 (Change Management)
- **OSFI B-13 (Canada):** Section 4.1.3 (Technology project lifecycle controls)
- **ISO/IEC 12207:2017:** Software life cycle processes

---

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Spec artifact existence.** Look for `.feature` files (Gherkin / Cucumber), `specs/` directories, ADR directories, or equivalent. If none exist, the dimension cannot score above *Partial* on Layer 2.
2. **Spec-before-code timing check.** Pick 5 recent feature commits (commits whose message implies new functionality). For each, use `git log --follow` to determine whether a corresponding spec, scenario, or acceptance test was committed *before* or *in the same commit as* the implementation. Record the result. Spec-after-code is the failure mode.
3. **Pre-commit hook inspection.** Read `.pre-commit-config.yaml`, `husky/`, `lefthook.yml`, or equivalent. Confirm that hooks run a formatter, a linter, and a type checker on commit. Run `git log` on the hook configuration file to confirm the hooks are not disabled or recently weakened.
4. **CI gate inspection.** Read the CI pipeline definitions identified in dimension 4.10. Confirm that test failure, lint failure, and type-check failure all block merge. Confirm that coverage thresholds (if used) are enforced as gates and not as informational reporting.
5. **Gate uniformity across AI and human commits.** Inspect recent merged PRs for evidence that AI-generated commits clear the same gates as human commits. The two recognizable failure modes are (a) AI PRs receiving lighter review ("the AI wrote it, the tests pass, ship it") and (b) AI PRs receiving heavier or entirely separate review that effectively forbids AI contribution in practice. Either is a Layer 2 signal worth recording because both produce the same end state: a gate regime that is inconsistent across contributors and therefore not actually a gate regime. A project-level convention that distinguishes AI commits (co-author lines, dedicated branches, mandatory reviewer rules) is a positive signal when it is used to *apply the same gates*, and a warning signal when it is used to apply *different* gates.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Five markers, each scored present / partial / absent.

**Marker 1: Specs are written before code, not retrofitted after.** For 5 recent features, read the spec or acceptance test alongside the implementation. A spec that was written first reads as a *description of intent*: it names behaviors the code does not yet exhibit, it covers edge cases the implementer would not have thought of unprompted, and it constrains the design space rather than describing the result. A spec that was retrofitted reads as a *transcription of code*: each test mirrors the structure of the function it tests, no edge case is covered that the function does not already handle, and the spec adds no information beyond what `git diff` already shows. Score: present if 4 or 5 of 5 specs read as descriptions of intent, partial if 2 or 3, absent if 0 or 1.

**Marker 2: Quality gates actually block.** Read the CI configuration and the pre-commit configuration. Then read recent merged PRs and check whether any merged with failing gates, with overridden gates, or with skipped gates. A team whose gates exist on paper but whose merges routinely bypass them does not have quality gates; they have quality theater. Score: present if no merged PRs in the last 30 days bypassed gates, partial if 1 or 2 bypasses (with documented justification), absent if bypasses are routine or undocumented.

**Marker 3: AI-generated code is reviewed with the same rigor as human code.** Talk to the team or read PR comments. Determine whether AI-generated PRs receive the same level of review scrutiny as human-written PRs. The failure mode is the team that says "the AI wrote it, the tests pass, ship it" while human PRs get line-by-line review. The opposite failure mode (also a failure) is the team that requires AI PRs to be entirely rewritten by humans before merge, which means they have not actually integrated AI into their SDLC at all. Score: present if AI and human code clear the same review gate at the same level of scrutiny, partial if AI gets lighter or heavier review than human, absent if AI code merges without review or if AI code is forbidden from merging at all.

**Marker 4: The specification is the source of truth, not the code.** When a discrepancy is found between what the spec says and what the code does, the team's default response should be *fix the code, not the spec*. The failure mode is the team that updates the spec to match the (incorrect) code because that is the path of least resistance. Sample 5 recent commits whose message or PR description mentions a spec or test change. Determine whether the change tightened the spec to match correct new behavior, or loosened the spec to accommodate code that drifted. Score: present if 4 or 5 of 5 are tightening, partial if 2 or 3, absent if 0 or 1.

**Marker 5: The team can name what the AI is bad at.** Ask the technical lead (or read team documentation) for the list of things the team has explicitly decided *not* to use AI for, and the reasons. A mature team has a list: "we don't use AI for the payment ledger because it generates plausible-looking arithmetic that doesn't reconcile," "we don't use AI for migrations because it forgets backfill order," "we don't use AI for cross-cutting refactors because it loses track of the call graph past 3 hops." A team that says "we use AI for everything, it's fine" has not yet done the failure analysis that a real safeguard process requires. Score: present if the team can name 3 or more concrete AI-exclusion zones with reasons, partial if 1 or 2, absent if none.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 4 or 5 markers score Present. *Partial* if 2 or 3 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the SDLC *appropriate to the risk class* of the system being built? (A payment ledger needs more gates than an internal dashboard.)
- Does the team's *culture* support the gates, or do the gates exist only because nobody has yet built up the political capital to remove them?
- Is the AI tooling itself *current and well-configured*, or is the team using a 2-year-old model with default settings?
- Is the *prompt library* (if one exists) maintained, versioned, and reviewed?
- Are *post-incident reviews* feeding back into the safeguard set, or are incidents treated as one-offs?

---

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (specs exist, written before code, pre-commit hooks active, CI gates blocking) AND Layer 3 form scores Present (4–5 of 5 markers).
- ***Partial.*** Layer 2 passes but Layer 3 has gaps (2–3 markers Present); OR Layer 2 is mixed (specs exist but timing is inconsistent, gates exist but some are advisory) but Layer 3 scores Present.
- ***Absent.*** Layer 2 fails (no spec artifacts, no pre-commit hooks, no blocking CI gates); OR Layer 2 passes but Layer 3 scores Absent (0–1 markers Present, indicating gates exist on paper but are routinely bypassed).

**Common failure modes.**

- **The retrofitted test suite.** The team writes tests after the code is merged, to claim coverage. The tests pass on the first run because they were written from the implementation. Layer 3 fails Marker 1.
- **The advisory CI gate.** The CI runs lint and type checks but reports them as warnings, not failures. Merges proceed with hundreds of warnings. Layer 3 fails Marker 2.
- **The two-tier review process.** Human PRs get reviewed line by line; AI PRs get a thumbs-up because "the AI wrote it." Layer 3 fails Marker 3.
- **The drifting spec.** The acceptance test for the checkout flow was written 2 years ago. The checkout flow has changed 14 times since. Each time, the test was modified to match the new code. The spec no longer describes intended behavior; it describes whatever the code happens to do this week. Layer 3 fails Marker 4.
- **The "AI does everything" team.** The team uses AI for every task with no exclusion zones. They have not yet experienced a serious AI-generated incident, and so they have no list of things AI is bad at. Layer 3 fails Marker 5. (This is a leading indicator: the absence of an exclusion list almost always precedes the incident that produces one.)
- **The disabled pre-commit hook.** The pre-commit configuration exists but most developers have run `git commit --no-verify` enough times that the hooks have effectively been deactivated. Layer 2 fails on the inspection.
- **The spec directory full of historical artifacts.** The `specs/` directory has 200 files. 150 of them describe features that no longer exist or were never built. Layer 2 finds the directory; Layer 3 reveals that none of it is current.

**Example presence (TypeScript / disciplined Node.js team).** A TypeScript Node.js service with a `features/` directory containing 47 `.feature` files (Gherkin), each tied to a step-definition file under `tests/steps/`. Recent feature commits show the `.feature` file added in the same commit as (or one commit before) the implementation. The repository has `.pre-commit-config.yaml` running Prettier, ESLint, and `tsc --noEmit` on every commit; the configuration has not been modified in 6 months. The CI pipeline blocks merge on test failure, lint failure, type failure, and coverage drop below 80%. The team's `CONTRIBUTING.md` lists four AI-exclusion zones with reasons: payment math (AI hallucinates plausible-but-wrong arithmetic), database migrations (AI forgets backfill ordering), cross-service refactors (AI loses track past 3 hops), and security-sensitive parsing (AI generates regex that passes tests but fails on adversarial input). Recent merged PRs show no gate bypasses. Layer 2 passes; all 5 Layer 3 markers score Present.

**Example absence (Python / undisciplined Flask team).** A Python Flask service with no `specs/` directory and no `features/` directory. Tests live in `tests/` but were committed *after* the corresponding implementation in every sampled case. The repository has no `.pre-commit-config.yaml`. The CI pipeline runs `pytest` and reports the result, but the GitHub branch protection rule does not require the pipeline to pass before merge; 4 of the last 30 merged PRs merged with failing tests. The team has no documented AI-exclusion zones. Asked what the AI is bad at, the technical lead says "nothing really, it's pretty good." Six weeks later the team will discover that the AI has been generating SQL queries with subtle injection vulnerabilities for the last 4 months, but the audit happens before that discovery. Layer 2 fails on three checks; Layer 3 fails on every marker. The dimension scores Absent.

**Time budget.** Approximately 75 to 105 minutes for an experienced assessor: 30 to 45 minutes for the Layer 2 mechanical inspection, 45 to 60 minutes for the Layer 3 marker assessment (Marker 5 may require a brief conversation with the technical lead, which should be scheduled in advance).

---

