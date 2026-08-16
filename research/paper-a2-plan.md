# Paper A2 Plan: Distribution Readiness

Narrative companion to the beads epic tracking this workstream. The beads graph is authoritative for task state; this doc captures phase framing, rationale, and the critical-path reasoning behind the step order.

## Why Paper A2

The Honest audit framework's current Layer 1 indicators measure finite testability (Paper A: L1.18-20), but code that is pure and decision-bounded can still be unshippable to distributed runtimes when it reaches into globals, singletons, or stateful imports. Enterprises reach for pub-sub, message queues, and event-driven systems when they need durable audit logs for compliance, asynchronous or batch workflows, broker-mediated integration between independently deployed teams, or failure isolation at scale. Code not shaped for those systems requires surgery at the moment of need, often under deadline pressure. Distribution readiness is the latent property that determines whether code ships or gets rewritten.

Paper A2 introduces **L1.21 Parameter Closure Ratio**, pairs it with L1.18 to operationalize a new **Distribution Readiness** dimension (dimension 19), and surveys the same 200-repo corpus as Paper A. Zero LLM budget required; pure static analysis.

## Relationship to Paper A

Paper A stays locked at its pre-registered 20-indicator set. Paper A2 introduces L1.21 as a new indicator, validated on Paper A's corpus, published standalone. After A2 ships, framework v2 promotes L1.21 into the canonical indicator set (20 → 21).

## Phases

### Phase 1 — Framework groundwork (no dependencies)

- **1.1** Write `methodology/dimensions/19-distribution-readiness.md`. Latent-property framing. Pub-sub/MQ as enterprise table stakes when reached for, not deployed for every operation. Names L1.18 (retryable) and L1.21 (relocatable) as the two operationalizing indicators.
- **1.2** Write L1.21 specification. Parameter-closed vs. leakage definitions, per-language rules for Python/Java/TypeScript/C#, edge cases (constants vs. stateful imports, DI frameworks, `self`-reached state).
- **1.3** Update `methodology/03-layer1-indicators.md` with L1.21 entry, provenance note = "introduced in Paper A2."

### Phase 2 — Pre-registration (depends on 1.1, 1.2)

- **2.1** Draft `methodology/papers/paper-a2-distribution-readiness-preregistration.md`. Mirror Paper A structure. Corpus reuse, seven-pilot calibration plan, orthogonality hypothesis (L1.18 vs. L1.21 correlation < 0.5), locked band definitions set after Phase 3.3.
- **2.2** OSF registration, timestamp before any 200-repo analysis begins.

### Phase 3 — Instrument build (depends on 1.2)

- **3.1** `research/paper-a2-distribution-readiness/l1_21.py`. Unified tree-sitter, four languages, mirror `l1_18.py` architecture. Honest Code compliant (pure, dict dispatch, TypedDicts). Call-stack docstring.
- **3.2** Self-test: Honest Code's own scripts must score ≤ 5% on L1.21. If not, fix the scripts — not the indicator.
- **3.3** Seven-pilot validation. Run on Saleor, PostHog, NetBox, our tools, Spring PetClinic, Cal.com, eShopOnWeb. Calibrate Healthy/Not Healthy/Slop bands on observed distribution. Lock bands into pre-registration before Phase 4.

### Phase 4 — Experiment (depends on 3.3 and Paper A experiment completion)

- **4.1** Run L1.21 on 200-repo corpus. Reuse `run_experiment.sh` pattern.
- **4.2** Analysis: per-language and per-sector L1.21 distributions; bivariate L1.18 × L1.21 scatter defining Distribution Readiness quadrants; correlation test for orthogonality hypothesis.
- **4.3** Figures following Paper A conventions.

### Phase 5 — Manuscript (depends on 4.2)

- **5.1** Draft `research/paper-a2-distribution-readiness/manuscript.md`. Paper A as structural template. Lead finding: Distribution Readiness as two-axis measurement; pub-sub fit as the explanatory frame.
- **5.2** Zenodo preprint submission, DOI linked to Paper A.

### Phase 6 — Downstream updates (after A2 ships)

- **6.1** Update Paper B pre-registration: cite A2 as the established instrument for L1.21, remove any coupling-introduction language. Keeps Paper B tighter.
- **6.2** Framework v2: promote L1.21 into the canonical indicator set. Update `../spec/03-layer1-indicators.md` from 20 → 21 indicators.

## Critical path

Phase 1 (days) → Phase 2 (day) → Phase 3 (days, with pilot validation blocking) → Phase 4 (hours, compute-bound) → Phase 5 (days).

**Rate-limiting step:** Phase 3.1 (L1.21 script). Everything downstream waits on instrument validation.

## Beads epic

Run `bd ready --json` for unblocked tasks. Run `bd dep tree <epic-id>` for the full workstream graph.
