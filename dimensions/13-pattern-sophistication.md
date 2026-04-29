### 4.13 Pattern sophistication

**Lifecycle category.** Software architecture.

**Drafted under the four-layer model.** This dimension uses the Layer 2 (quantitative artifacts) and Layer 3 (qualitative specified judgment) forms separately, with Layer 4 questions explicitly deferred to Phase 1. See Section 2 for the layer model.

**Definition.** Pattern sophistication is the application's use of well-known software design patterns (creational, structural, behavioral, architectural) chosen deliberately to fit specific problems, in combinations that produce more value than the sum of the individual patterns. A mature pattern repertoire includes more than the basic MVC / repository / service triad; it includes battle-tested patterns from the broader literature (event sourcing, CQRS, dispatch tables, strategy, observer, decorator, state machine, saga, circuit breaker) chosen because the team recognized the underlying problem the pattern solves, not because they read about the pattern in a tutorial. The opposite is the codebase that has *one* pattern repeated everywhere regardless of context (typically MVC or service-repository), or that has many patterns applied superficially without solving any real problem (the cargo-cult failure mode).

**Industry threshold.** High pattern diversity with problem-pattern alignment, not cargo-cult application. Drawn from the OOPSLA 2009 work on Design Pattern Density (which found that expert developers correlate high DPD with codebase maturity), Feitosa & Avgeriou's research on "Pattern Grime" (which documents how rapidly accumulating misuse degrades pattern-based codebases), the ThoughtWorks Technology Radar (which has consistently flagged event sourcing and CQRS as "used much less than they should be"), and Fischer et al. (2017)'s study of 1.3 million Android applications which catalogued "Blind Pattern Following" as an antipattern at industry scale.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- ThoughtWorks Technology Radar — Tier 2
- OOPSLA 2009: Design Pattern Density — Tier 3
- Feitosa & Avgeriou: Pattern Grime research — Tier 3
- Fischer et al. (2017): Blind Pattern Following, 1.3M Android apps — Tier 3
- Prechelt & Tichy controlled experiments — Tier 3

**Compliance framework mappings.**
- **ISO/IEC 25010:** Maintainability characteristics (modularity, reusability, modifiability)
- **NIST SP 800-160:** Systems Security Engineering — pattern-based design as a maturity indicator

---

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Enumerate visible patterns.** Use `grep` to find structural markers of common patterns in the codebase. Search for: decorator definitions and applications (`@`-decorators in Python, attribute decorators in C#, method decorators in TypeScript), dispatch tables (literal `dict` or `Map` literals mapping strings or types to functions), strategy interfaces (an interface with a single method implemented by multiple classes), factory functions or classes (`create_*`, `make_*`, `*Factory`), repository pattern (`*Repository` classes that abstract data access), event sourcing (an `events` table or `event_store` class plus event types), CQRS (separate `Command` and `Query` types), state machines (explicit state enum plus transition table), observer pattern (`subscribe`, `on_*`, `emit_*`), circuit breakers (`CircuitBreaker` class or library import), saga or process manager (`Saga`, `ProcessManager`, multi-step workflow coordinators).
2. **Count distinct patterns.** A mature codebase has 5 or more distinct patterns in regular use. A codebase with 2 or fewer is *Partial* on the Layer 2 form. A codebase with only the trivial MVC / service / repository triad and nothing else is *Absent* on the Layer 2 form regardless of how well that triad is implemented.
3. **Check for ADRs or pattern documentation.** Look for `docs/adr/`, `docs/architecture/`, `decisions/`, or similar directories. Count the number of decision records that explicitly justify a pattern choice. Mature codebases have at least one ADR per significant pattern.
4. **Check for at least one non-trivial battle-tested pattern.** The codebase should use at least one pattern beyond the basic CRUD-application set: event sourcing, CQRS, saga, state machine, dispatch table, or circuit breaker. The presence of even one such pattern is a positive signal; the complete absence is a negative one.
5. **Check for uniformity vs variety.** Sample 5 random modules. Determine whether they all use the same structure or whether they use distinct structures appropriate to their problems. Total uniformity (every module is the same controller-service-repository sandwich) is a sign of pattern poverty, not pattern discipline.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** The assessor applies the following five markers, each scored present / partial / absent. Cite the specific code or document that supports each marker score.

**Marker 1: Pattern justification.** For each major pattern identified in the Layer 2 enumeration, can you find evidence (in code comments, ADRs, README, or commit messages) that explains *what problem the pattern solves*? Not "we use the repository pattern" but "we use the repository pattern because we needed to swap the SQL backend for the test backend without changing the service layer." Patterns that exist with no justification are not necessarily wrong, but they are evidence that the team may not have chosen them deliberately. Score: present if ≥80% of patterns have justification, partial if 30–80%, absent if <30%.

**Marker 2: Pattern fitness check.** Sample 3 modules that use a non-trivial pattern (one of: event sourcing, CQRS, saga, state machine, dispatch table, circuit breaker). For each, ask the question: *does the pattern fit the problem this module solves?* Specifically: an event sourcing module should be solving a problem where the *history* of state changes matters (audit trail, time-travel debugging, derived projections); if it's solving a problem where only the current state matters, the pattern is misapplied. A state machine module should be solving a problem with discrete states and constrained transitions; if every transition is allowed from every state, the state machine is decorative. Score: present if all 3 sampled modules use their pattern fitly, partial if 1–2 do, absent if none do.

**Marker 3: Pattern combinations.** Look for cases where two or more patterns work together to solve a problem more effectively than either could alone. Examples: dispatch tables + pure functions (Honest Code Chapter 4), event sourcing + CQRS, repository + factory + DI, strategy + decorator. The presence of pattern *combinations* indicates the team is thinking about patterns as a vocabulary, not as a checklist. Score: present if ≥3 distinct combinations are visible, partial if 1–2, absent if patterns are always used in isolation.

**Marker 4: Pattern evolution evidence.** Look at git history for evidence that the team has *changed* their pattern choices over time. Specifically: a commit or PR that replaces one pattern with another with a clear rationale ("replaced the singleton with dependency injection because we needed test isolation"; "extracted the dispatch table from the if/elif chain after the chain reached 14 branches"). Pattern evolution is evidence that the team treats patterns as tools to be replaced when they stop fitting, not as commitments to be defended. Score: present if ≥3 such evolutions are visible in the last 12 months of history, partial if 1–2, absent if none.

**Marker 5: Pattern naming and recognition.** Sample 5 random modules. For each, check whether the patterns in use are *named* in the code (`# event sourcing aggregate`, `// dispatch table`, `class UserStrategy implements PaymentStrategy`) or whether they are implicit (the pattern is structurally present but never named). Naming is evidence of conscious pattern use; implicit patterns are evidence of incidental structure that happens to look like a pattern. Score: present if ≥4 of 5 sampled modules have named patterns, partial if 2–3, absent if 0–1.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 4 or 5 of the markers score Present. *Partial* if 2 or 3 of the markers score Present (or if all 5 score Partial). *Absent* if 0 or 1 of the markers score Present.

**Inter-rater calibration target.** Two trained assessors should agree on the Layer 3 marker scores for at least 4 of 5 markers when scoring the same codebase. If inter-rater agreement drops below this on a calibration codebase, the markers need revision.

#### Layer 4 questions (deferred to Phase 1)

The following questions cannot be answered with specified markers and require elite architectural judgment. They are flagged in the Slop Report's Phase 1 follow-up section without influencing the Layer 2 or Layer 3 score.

- Are the patterns used *correctly* in the deepest sense (not just structurally but semantically)? A pattern can be structurally present but used in a way that subverts its intent.
- Would a senior architect at the same company in the same domain make the same pattern choices?
- Are there subtle anti-patterns hidden inside ostensibly correct pattern usage? (Pattern Grime, in Feitosa & Avgeriou's term.)
- Is the team's pattern vocabulary aligned with the team's actual problems, or are they using patterns from an unrelated domain (e.g., enterprise patterns applied to a personal-use application)?
- Are the pattern choices durable, or will they need to be replaced within 12 months as the system grows?

---

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (5 or more distinct patterns, ADRs or justification, at least one non-trivial pattern, variety not uniformity) AND Layer 3 form scores Present (4–5 of 5 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2–3 markers Present); OR Layer 2 form is Partial but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (only the trivial CRUD triad or fewer than 2 distinct patterns); OR Layer 2 form passes but Layer 3 scores Absent (0–1 markers Present).

**Common failure modes.**

- **The MVC monoculture.** Every module is a controller, a service, and a repository. There are no other patterns in use. Layer 2 fails on the variety check.
- **Pattern hoarding.** The team has used 9 distinct patterns but cannot explain why any of them were chosen. Patterns appear to have been added because the developer read a tutorial. Layer 3 fails on Marker 1 (justification).
- **Cargo-culted event sourcing.** The codebase has an `events` table and an `EventStore` class but never queries the events for anything. The current state is computed once on save and read from a `state` column thereafter. The pattern is decorative. Layer 3 fails on Marker 2 (fitness).
- **Decorative state machines.** A `State` enum and a `transition()` method exist, but `transition()` allows any state to move to any other state. The state machine encodes no constraints. Layer 3 fails on Marker 2.
- **Pattern isolation.** Each pattern is used by exactly one module. There are no combinations. The codebase reads as a tour of a patterns book. Layer 3 fails on Marker 3 (combinations).
- **Frozen patterns.** Every pattern in the codebase has been there since the first 6 months of development. No pattern has ever been replaced. The patterns are the team's first guess at how to structure the code. Layer 3 fails on Marker 4 (evolution).
- **Implicit patterns only.** The codebase uses patterns structurally but never names them. New developers cannot tell what patterns are in use until they reverse-engineer them from the code. Layer 3 fails on Marker 5 (naming).
- **The "we don't believe in patterns" anti-stance.** The team explicitly rejects design patterns as "over-engineering" and writes everything as procedural functions or as god-objects. Layer 2 fails on the variety check; Layer 3 fails on every marker.

**Example presence (Ruby / Rails, with multiple patterns in combination).** A Rails 7 application that goes well beyond the standard MVC sandwich. The codebase has:

- **Service objects** (`app/services/`) for business logic that doesn't belong in models
- **Form objects** (`app/forms/`) for complex validation across multiple models
- **Query objects** (`app/queries/`) that wrap ActiveRecord queries with named, testable scopes
- **Decorators** (`app/decorators/` using Draper) for view-layer concerns
- **An event sourcing module** for the audit subsystem (`app/events/`, with `EventStore`, `Aggregate`, and replay-based state reconstruction)
- **State machines** (`AASM` gem) on three resources (`Order`, `Subscription`, `Refund`) with explicit transitions and guards
- **A circuit breaker** (`Stoplight` gem) wrapping all calls to the external payment processor

Each pattern has an ADR in `docs/adr/` explaining when to use it and when not to. The combinations are visible: the event sourcing module uses dispatch tables for projection rebuilding; the service objects use dependency injection via constructor parameters; the state machines emit events into the event store. Five evolutions are visible in `git log`: a singleton config replaced by DI, an if/elif tax calculator replaced by a strategy registry, a 200-line controller refactored into a form object plus a service object, a custom retry loop replaced by Stoplight, and a polling worker replaced by an event subscription. Pattern names appear in comments and class names throughout. The Layer 3 markers all score Present.

**Example absence (Java / pattern monoculture).** A Java Spring Boot application that has been in production for 5 years. The codebase has approximately 240,000 lines of code organized into the standard `controllers/`, `services/`, `repositories/`, `entities/` packages. Every controller is structured identically: receive request, call service method, return response. Every service is structured identically: validate input, call one or more repository methods, return result. Every repository is a Spring Data interface. There is one dispatch table in the entire codebase, and it has been broken since 2023 (an unused `Map` declared but never read). There are no ADRs. There is no event sourcing, no CQRS, no state machines, no circuit breakers. The team's stated philosophy is "we keep things simple" and that philosophy has produced 240,000 lines of homogeneous code that no developer can navigate without grep. The Layer 2 variety check fails (only the trivial triad). The Layer 3 markers all score Absent. The dimension scores Absent.

**Time budget.** Approximately 75 to 90 minutes for an experienced assessor: 30 minutes for the Layer 2 enumeration and counting, 45 to 60 minutes for the Layer 3 marker assessment.

---

