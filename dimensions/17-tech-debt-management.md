### 4.17 Tech debt management

**Lifecycle category.** Lifecycle management.

**Drafted under the four-layer model.**

**Definition.** Tech debt management is the discipline of *deleting code that no longer serves the system*, of *refactoring before adding* when the existing structure cannot cleanly accommodate the new requirement, and of treating *net-negative commits* (commits that remove more lines than they add) as a normal and frequent event rather than a rare occasion. The opposite is pure accumulation: every commit adds lines, no commit removes lines, dead code accumulates indefinitely, parallel implementations of the same logic proliferate, and the codebase grows monotonically until nobody can find anything. Pure accumulation is the single most reliable visual signature of unsupervised AI-assisted development, because the AI is rewarded for *producing output*, not for *reducing the system's surface area*.

**Industry threshold.** Delete-to-add ratio of at least 60% over a representative window (per Layer 1 indicator L1.5); net-negative commits routine (≥10% of commits per L1.6); refactor-only commits visible in the history (per L1.7); dead-code analyzers run periodically and their findings acted on; parallel implementations of the same logic actively consolidated rather than allowed to coexist. Drawn from Wasserman 2026 (which used the delete/add ratio as one of the eleven Layer 1 indicators precisely because it discriminates so reliably), Tornhill (2018) on hotspot analysis, and the SonarSource technical-debt research on cost-of-delay.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Wasserman 2026: delete/add ratio as Layer 1 discriminator — Tier 1
- Tornhill (2018): *Software Design X-Rays* (hotspot and code-age analysis) — Tier 2
- SonarSource technical debt research — Tier 3
- Lehman's Laws of Software Evolution (continuing growth and declining quality) — Tier 3

**Compliance framework mappings.**
- **NIST SP 800-53:** CM-8 (System Component Inventory), SA-15 (Development Process, Standards, and Tools)
- **SOC 2 Trust Services Criteria:** CC7.1 (System Operations — detection of changes)
- **ISO/IEC 25010:2011:** Maintainability quality characteristic (modularity, reusability, analyzability, modifiability, testability)

---

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Run Layer 1 indicators L1.5, L1.6, L1.7, and L1.12.** These already measure delete/add ratio, net-negative commit frequency, refactor commit frequency, and unreachable code ratio. If three or more are in the slop range, this dimension cannot score above *Absent* on the Layer 2 form regardless of any other inspection. This is the fastest disqualifier in the entire 18-dimension catalog: L1.12 in particular (unreachable code above 5%) is the direct static signature of the pure-accumulation failure mode that L1.5, L1.6, and L1.7 detect from the commit history, and the four indicators triangulate the same pattern from four angles. **If L1.5/L1.6/L1.7 cannot be computed** (shallow clone, rewritten history, or other cases flagged under Section 5.7), the assessor falls back to L1.12 alone plus the Layer 2 steps 2 through 5 below, and records the missing indicators as an explicit limitation in the Slop Report. The dimension can still be scored, but the *Absent* disqualifier shortcut is not available and the time budget increases to approximately 60 minutes.
2. **Dead code symbol count.** L1.12 has already produced the unreachable-code ratio as a percentage. For the Layer 2 form, re-read the analyzer output and record the *absolute* count of unreferenced functions, classes, modules, and exports (not just the ratio). A codebase with hundreds of dead exports is a codebase that has never been pruned, even if the ratio happens to be low because the codebase is enormous.
3. **Parallel-implementation scan.** Use `grep` and structural search to find duplicate or near-duplicate utility functions. Common patterns: multiple `format_date` implementations in different modules, multiple HTTP client wrappers, multiple validation helpers that do approximately the same thing differently. Record the count.
4. **TODO / FIXME / HACK density.** Count `TODO`, `FIXME`, `XXX`, and `HACK` comments in the production codebase. Compare against the size of the codebase. A density above one marker per 200 lines of production code is a signal of accumulated unaddressed debt.
5. **File and module age check.** For the 10 largest files in the codebase, check the age of the file (first commit) and the cadence of recent changes. A 4,000-line file that was created 5 years ago and that gets touched in 60% of feature PRs is a debt hotspot regardless of any other consideration.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Five markers, each scored present / partial / absent.

**Marker 1: Deletion is a normal verb in the team's vocabulary.** Read the last 30 days of commit messages and PR titles. Count how many use words like "remove," "delete," "drop," "retire," "decommission," "consolidate," "collapse," or "simplify." A team that deletes routinely has these words in their daily vocabulary. A team that only adds has commit messages that are uniformly "add," "implement," "introduce," "create." Score: present if ≥15% of recent commits use deletion vocabulary, partial if 5–15%, absent if <5%.

**Marker 2: Refactor commits are first-class citizens.** Look for commits whose stated purpose is *only* to improve the structure of existing code without changing behavior. These commits add no features, fix no bugs, and (ideally) leave the test suite unchanged. A team that does this has a working culture in which "I want to merge a refactor" is a normal request that does not require special justification. A team that does not do this treats every refactor as a guilty side-effect of some other change, which means refactors only happen when the team can hide them inside feature work, which means they happen rarely. Score: present if at least 5 refactor-only commits in the last 90 days, partial if 1–4, absent if 0.

**Marker 3: The team can name the worst part of the codebase and what they are doing about it.** Ask the technical lead. A mature team has a clear answer: "the user-import flow is the worst, it's been on the refactor list for two quarters, the plan is to extract the file-parsing into a separate module first, then replace the in-memory deduplication with a database-backed approach." A team without debt management has either no answer, a fatalistic answer ("the whole thing is bad"), or a denial ("we don't really have any tech debt"). Score: present if the lead names a specific module and a specific plan, partial if names a module but no plan, absent if no answer or denial.

**Marker 4: Dead code is removed when noticed, not preserved "in case."** When a developer notices that a function is unused, the team's default response should be to delete it. The failure mode is the team that comments out the function "in case we need it later," or moves it to a `legacy/` directory, or wraps it in an if-false branch. Dead code preserved "in case" is dead code that will never be revived because nobody will remember it exists; meanwhile it consumes attention from every reader who wonders if it is still wired up. Sample 5 recent PRs that touch large modules; check whether they removed any unreferenced code, whether they preserved any unreferenced code, or whether they did neither. Score: present if removal is the default, partial if mixed, absent if preservation is the default or if PRs systematically avoid the question.

**Marker 5: The codebase has gotten *smaller* in some recent month.** Look at the LOC trend over the last 12 months. A healthy codebase under active development does not grow monotonically; it grows during feature pushes and shrinks during cleanup pushes, producing a sawtooth pattern. A codebase that has only grown for 12 consecutive months has not had a real cleanup push in a year. Score: present if at least 2 of the last 12 months show net-negative LOC change, partial if 1 month, absent if 0.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 4 or 5 markers score Present. *Partial* if 2 or 3 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the team's debt management *proportionate* to the system's risk class and lifespan? (A 3-month prototype should not have the same debt discipline as a 10-year platform.)
- Does the *organization above the team* support debt work, or does management treat it as "not real work"?
- Is the team's debt understanding *shared* across the team, or held only by one or two senior people whose departure would erase it?
- Are there *load-bearing hacks* (the kind of debt that, if removed, would cause incidents) and does the team know which they are?
- Is the technical debt *strategically chosen* (deliberate trade-offs documented in ADRs) or *accidentally accumulated*?

---

**Combined scoring rubric.**

- ***Present.*** Layer 1 indicators healthy (delete/add ≥60%, net-negatives ≥10%, refactor commits visible) AND Layer 2 form passes (low dead-code count, few parallel implementations, TODO density acceptable) AND Layer 3 form scores Present (4–5 of 5 markers).
- ***Partial.*** Layer 1 indicators mixed (delete/add 30–60%) OR Layer 2 has gaps (some dead code, some parallel implementations) but Layer 3 scores Present or Partial.
- ***Absent.*** Layer 1 indicators in slop range (delete/add <30%, near-zero net-negatives, no refactor commits) — this alone is sufficient to score *Absent* regardless of Layer 2 or Layer 3, and is the cleanest single-indicator disqualification in the entire methodology.

**Common failure modes.**

- **Pure accumulation.** Every commit adds, no commit removes. L1.5 is below 15%. The codebase has grown for 18 consecutive months. This is the canonical AI-assisted slop signature.
- **The legacy directory.** Dead code is moved to `legacy/` or `deprecated/` or `old/` rather than deleted. Years pass. The legacy directory becomes 30% of the codebase. New developers spend half their first week figuring out which parts of `legacy/` are still wired up.
- **Comment-out-in-case.** Functions are commented out rather than deleted. `git history` would have preserved them anyway, but the team does not trust `git history`, so they keep the commented-out version in the file forever.
- **The 4,000-line god file.** A single file holds 60% of the application logic. Every feature touches it. Every merge produces a conflict in it. Nobody will refactor it because the cost of breaking it outweighs the benefit of any partial improvement, so it gets bigger every month.
- **Parallel utility libraries.** The codebase has 4 different `format_currency` functions in 4 different modules, written by 4 different developers (or AI sessions), each with slightly different rounding rules. Bugs are introduced when one is fixed and the others are not.
- **The "we don't have tech debt" denial.** The team's stated position is that they manage debt as they go. The Layer 1 indicators reveal that they have not deleted anything in 8 months.

**Example presence (Go / mature Kubernetes operator team).** A Go-based Kubernetes operator with 12 months of git history showing L1.5 = 71%, L1.6 = 14%, L1.7 = 9%. Recent commit messages include "remove deprecated v1 reconciliation loop," "consolidate retry logic," "delete unused metric exporters," "drop support for the legacy CRD." `staticcheck` and `unused` report fewer than 10 unreferenced exports across the entire codebase. There are no `legacy/` or `deprecated/` directories. The technical lead, when asked, identifies the worst module (the resource-validation pipeline), the reason it is the worst (3 layers of nested switch statements that grew during a rushed feature), and the planned approach (extract validation to a registry, replace switches with dispatch table, delete the switch code). The LOC trend over the last 12 months shows 3 months of net-negative change. Layer 1 passes; Layer 2 passes; all 5 Layer 3 markers score Present.

**Example absence (Ruby / pure-accumulation Rails monolith).** A Ruby on Rails monolith with 36 months of git history showing L1.5 = 8%, L1.6 = 1%, L1.7 = 0%. Recent commit messages are uniformly "add," "implement," "create," "introduce." There are no commits in the last 90 days whose primary purpose is deletion. `app/legacy/` contains 11,000 lines of code; no developer can confidently say which parts are still wired up. `grep -r "format_money" app/` returns 7 distinct implementations. The largest file is `app/models/order.rb` at 4,800 lines, touched in every other PR. The technical lead says "we know there's debt but we don't really have time to clean it up, the business keeps adding features." The LOC trend over the last 12 months shows monotonic growth with no net-negative months. Layer 1 fails on all three indicators; the dimension scores Absent in approximately 5 minutes of inspection.

**Time budget.** Approximately 30 to 45 minutes for an experienced assessor, mostly because the Layer 1 indicators do most of the work and produce a defensible *Absent* score quickly when present in the slop range. When Layer 1 is healthy, Layer 2 and Layer 3 add 30 minutes of additional work for the dead-code scan, parallel-implementation scan, and Layer 3 marker assessment.

---

