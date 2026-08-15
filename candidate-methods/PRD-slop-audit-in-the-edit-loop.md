# PRD: Slop Audit in the edit loop

**Status:** Draft for approval. Not approved, not scheduled, not built.
**Drafted:** 2026-08-15
**Decision owner:** Adam Zachary Wasserman
**Related:** `ai-consumer-instruction-contract.md`, `telemetry-for-threshold-calibration.md`, `layer1-longitudinal-method.md`

---

## 1. Summary

Put the Slop Audit inside the loop where code is written, so an agent gets a verdict on the file it just changed rather than after the commit.

Two delivery paths, doing different jobs. **A hook is the primary path**: it fires automatically after every write, needs no cooperation from the agent, and is silent unless something is wrong. **An MCP tool is the secondary path**: it is portable to any agent that speaks MCP, and it serves the deliberate case, "audit this before I refactor it."

## 2. Problem

The Slop Audit measures whether a codebase can be exhaustively verified. Its consumers today are an assessor in an engagement, a CI pipeline, and a developer at a terminal. The README names a fourth, an agent mid-edit, and nothing implements it.

Umbra ships an MCP server. Deslop ships one and markets this exact use. Slop Audit is the tool with a published standard behind it and no route into the loop.

**The deeper problem is that an agent has no appetite for quality.** It emits the most probable continuation. An instruction to call an audit tool is advice, and advice is the category that evaporates: it degrades over a long session, it is skipped when inconvenient, and an agent that stops calling produces no signal, so silence reads as health.

This is the jidoka asymmetry. Toyoda's loom detected its own broken thread. A model cannot detect its own fault, so the stopping mechanism has to sit outside it. **A tool the agent elects to call puts the agent in charge of noticing, which is the one thing it cannot do.**

## 3. Users

**Primary: an AI coding agent** on a repository. It does not choose to be audited; the hook fires. It needs an answer it can act on within one turn, about one file.

**Secondary: the developer who installed it.** They never call it. They decide whether it stays installed, which makes them the only user whose opinion can end the product.

**Not a user: the assessor.** Layer 2 and above need human judgment and stay out of scope.

## 4. Goals

- A verdict on every written file, automatically, without depending on the agent's cooperation.
- Silence when nothing is wrong, so the signal means something when it fires.
- "I cannot judge this" said in a form no agent can mistake for approval.
- Route work needing a person to a person.
- Collect, with consent, the distribution data that replaces the panel's provisional thresholds.

## 5. Non-goals

- **Not a grade.** A grade is a property of a repository; the agent holds a file.
- **Not a score, delta, or any number that moves with quality.** See §8.1.
- **Not Layer 2, 3 or 4.**
- **Not a replacement for the pre-commit hook or CI.** Different question, different scope, both stay.
- **Not a replacement for the corpus study.** Telemetry is a convenience sample; the corpus is a drawn one.

## 6. Scope: what the tool can actually answer

Measured 2026-08-15 by running the full twenty-indicator panel against a directory containing one Python file.

| | Indicators | Note |
|---|---|---|
| **Works at file scope** | L1.14 secrets, L1.16 trailing whitespace, L1.17 file size, L1.18 mutable-state ratio | Plus L1.18b and the absolute-paths check |
| **Meaningless on one file** | L1.1 – L1.11 | All eleven reported Slop. A single file has no commit history and no CI. |
| **Actively wrong on one file** | L1.12 unreachable code, L1.15 type-escape density | L1.12 called 80% of the file dead because cross-file references are invisible. L1.15 reported 0.0 Healthy on a file with two escape hatches, because of a 1000-line floor. |
| **Cannot compute** | L1.13, L1.19, L1.20 | Need a corpus or a test run |

**The surface is four indicators and two checks.** Shipping the full panel would mean thirteen of twenty verdicts being artefacts or false.

L1.17 needs restating for this context: the canon expresses it as a percentage of files, which is meaningless for one file, but "is this file over a thousand lines" is exactly file-scoped.

## 7. Delivery and distribution

### 7.1 The hook

A `PostToolUse` hook on Write and Edit. It fires whether or not the agent wants it, which is the entire point: it converts the audit from advice into a step.

**Silent on pass.** No output at all when the verdict is `IN_SPEC`. A hook that prints on every write is noise, and noise gets uninstalled. This is the andon cord: it does not display a score to the worker, it is quiet and then it is not.

### 7.2 How the hook reaches a machine

Claude Code plugins can ship hooks, and **the marketplace already exists**: `openhonest/honest-skills` carries `.claude-plugin/marketplace.json`, currently publishing three skills at v0.3.0. Adding a hook to that plugin means one command installs the skills and the audit together:

```
/plugin marketplace add openhonest/honest-skills
/plugin install honest-skills
```

The alternative, asking a user to hand-edit `settings.json`, is friction that costs most of the installs.

**Open question, and it needs checking rather than assuming:** whether the current plugin manifest schema accepts a `hooks` key. The manifest in that repo does not use one today.

### 7.3 The MCP tool, and why it still exists

The hook is Claude Code specific. Cursor, Codex and anything else speaking MCP cannot use it. So the MCP server is the portability path, and it also serves the deliberate case where a developer or agent wants an audit at a moment of its choosing rather than after a write.

Different jobs: the hook is reliable and narrow, the MCP is portable and elective. Neither replaces the other, and the design should not depend on the elective one.

### 7.4 What this is worth beyond the product

Every install is a machine running the standard rather than reading it. That is adoption by use, which is a different and stronger thing than a citation, and it is a channel the research programme does not currently have.

It also closes a loop the papers need. Installs produce opt-in telemetry, telemetry produces the distributions, and the distributions replace thresholds that are currently expert judgment. The calibration work and the distribution work stop being separate efforts.

The honest limit: this reaches people who already run coding agents and already care enough to install a quality plugin. That is not the general population of software, and any paper using the data has to say so.

## 8. Design constraints

### 8.1 The response must carry no gradient

An agent seeing a response after every single write will optimise against any property of it that varies with the score. The obvious ones are a grade or an indicator value. The non-obvious ones are message length, field order, the presence of an optional field, and **response latency**: a fast path for the common case publishes the verdict in the clock.

Requirement: every pass is byte-identical, or absent entirely, and takes indistinguishable time. Firing on every write makes this more important, not less.

### 8.2 The standard defines good; the baseline only detects change

The bands answer whether a level is acceptable. A baseline answers whether something moved. Separate questions, and the second is optional.

This matters because **the median file is written once per session and never again.** Across 10,876 file-and-session pairs, 56% have exactly one write and only 29% have three or more. For most files there is no trend to compute, and the tool still has a useful answer.

### 8.3 The baseline may not be self-generated

If the tool samples every write and computes limits from those samples, the agent writes its own yardstick. Baselines come from states recorded before the current session, or the tool reports `UNMEASURED` until enough exist.

## 9. Verdict vocabulary

| Verdict | Meaning | Hook behaviour |
|---|---|---|
| `IN_SPEC` | Within band, nothing changed | **Silent** |
| `OUT_OF_SPEC` | Outside the band | Surfaces: indicator, value, band, what would bring it in |
| `SHIFTED` | Changed since the baseline | Surfaces: indicator, window, evidence |
| `UNMEASURED` | Could not judge this | Surfaces: what it could not read, and why |
| `REFER` | A person is needed | Surfaces: what to look at |

`UNMEASURED` must read louder than `SHIFTED`. It is currently the quietest possible output in the card, which is the defect fixed on 2026-08-15.

## 10. Success metrics

- **Installs**, and the ratio still installed after thirty days. Uninstall is the metric that matters; an uninstall is a worse outcome than a non-install because it is a negative experience with the standard.
- **Signal rate:** proportion of writes producing any output at all. A hook that fires constantly is disabled within a day.
- **Override rate:** proportion of surfaced verdicts the developer ignores or suppresses.
- **Calibration progress:** distinct installs contributing telemetry, and whether the resulting distributions separate enough to set a threshold.
- **Counter-metric: added latency per write.** This sits in an edit loop. Slow is the same as absent, and it is also what keeps §8.1 honest.

## 11. Dependencies and blockers

| Item | State |
|---|---|
| Card converts "no data" into a capability claim | **Fixed** 2026-08-15 |
| Findings-list ordering unstable when findings share a line | **Fixed** 2026-08-15 |
| L1.18 thresholds stale against the corrected computation | **Open.** Values moved up to 12.7 points; bands not recalibrated |
| Plugin manifest supports a `hooks` key | **Unverified.** Blocks §7.2 |
| Output contract contradicts `tools/edit-replay/` | **Open.** Resolved in principle by §8.2 and §8.3 |
| Telemetry spec approved | **Open** |

**L1.18 is the blocker that matters.** It is the most useful of the four in scope, and shipping it means quoting a threshold set against a different calculation from the one producing the number.

## 12. Risks

**It gets uninstalled.** The dominant risk, and firing on every write raises it. Mitigated by silence on pass and by treating the signal rate as a release gate rather than a dashboard number.

**The agent games it.** Mitigated by §8.1, and the risk is higher here than for an elective tool because the agent sees the response constantly.

**Thresholds are wrong, so verdicts are wrong.** Live today. Every band is provisional and the canon says so.

**Claude Code only.** The hook does not reach other agents. Mitigated by the MCP path, which is why it stays in scope.

**Telemetry poisoned or dominated.** Mitigated by per-UID aggregation, plausibility rejection, and median summaries. See §7 of the telemetry spec.

## 13. Open decisions

1. Ship four indicators, or wait for more to become file-scoped?
2. Recalibrate L1.18 before shipping, or ship with a "provisional threshold" caveat in every surfaced verdict?
3. Is `SHIFTED` in v1 at all, given only 29% of files can produce it?
4. Does the hook ship in the existing `honest-skills` plugin, or its own?
5. Does the MCP live in this repository or its own?

## 14. Suggested phasing

**v0.1** Hook only, four indicators, silent on pass. Ships in the existing plugin. Answers whether the file meets the standard.

**v0.2** MCP server, same four indicators, for portability off Claude Code.

**v0.3** Telemetry, opt-in, off by default.

**v0.4** `SHIFTED`, once a baseline mechanism satisfies §8.3.

**v1.0** Thresholds recalibrated from collected distributions, at which point the verdicts mean what they say.
