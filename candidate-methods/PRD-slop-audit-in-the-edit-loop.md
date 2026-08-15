# PRD: Slop Audit in the edit loop

**Status:** v0.1 built and shipped. Sections 1 through 13 remain the design; §14 records what has landed.
**Drafted:** 2026-08-15. **Revised:** 2026-08-15 after the hook shipped.
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

**What v0.1 actually ships is two and a half.** L1.16 and L1.17 are computed in the hook, because both are exact arithmetic over lines and neither has a rival implementation to disagree with. L1.18 is delegated to the `slop-audit-l1` binary and reports `UNMEASURED` where that binary is absent, which on a bare plugin install is everywhere. L1.14 secrets is not shipped: a secrets check that misses is worse than none, and the field has mature tools already.

L1.17 needs restating for this context: the canon expresses it as a percentage of files, which is meaningless for one file, but "is this file over a thousand lines" is exactly file-scoped.

## 7. Delivery and distribution

### 7.1 The hook

A `PostToolUse` hook on Write and Edit. It fires whether or not the agent wants it, which is the entire point: it converts the audit from advice into a step.

**Silent on pass.** No output at all when the verdict is `IN_SPEC`. A hook that prints on every write is noise, and noise gets uninstalled. This is the andon cord: it does not display a score to the worker, it is quiet and then it is not.

### 7.2 How the hook reaches a machine

Claude Code plugins ship hooks in `hooks/hooks.json` at the plugin root, in the same format as the `hooks` object in `settings.json`. They are enabled when the plugin is enabled. **No user edits any configuration file.** Verified against the plugin documentation on 2026-08-15; the documented example is a `PostToolUse` hook matching `Write|Edit`, which is exactly the shape this needs.

The marketplace already exists: `openhonest/honest-skills` publishes three skills at v0.3.0. One command then installs the skills and the audit together:

```
/plugin marketplace add openhonest/honest-skills
/plugin install honest-skills
```

**This also removes a question that was open.** An MCP server editing `settings.json` to install its own hook was considered as a fallback. It is unnecessary, and it was always the wrong shape: a tool that rewrites the host's configuration because it was installed for something else is escalating its own privileges, which is not a thing this project should ship.

### 7.3 One artifact, not two

A plugin root also carries `.mcp.json`, which declares MCP servers. So a single plugin ships the skills, the hook and the MCP server, installed by one command and versioned together.

The hook is Claude Code specific and fires without cooperation. The MCP is portable to Cursor, Codex and anything else speaking MCP, and serves the deliberate case: audit this file before I refactor it. Different jobs, same package.

### 7.4 Distribution channels

| Channel | Bar | State |
|---|---|---|
| `openhonest/honest-skills` marketplace | none, it is ours | Live, three skills |
| `anthropics/claude-plugins-community` | review pipeline plus automated safety screening; `claude plugin validate` must pass | **Not submitted.** Users add it with one command and install from it; approved plugins are pinned to a commit SHA and the catalog syncs nightly |
| awesome-claude-code | 14 days old and actively developed, or 100 stars | Blocked until 2026-08-28 |

The community marketplace is the channel worth the most and the one not currently used. Run `claude plugin validate` before submitting; the review pipeline runs the same check.

### 7.5 What this is worth beyond the product

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
| L1.18 declaration classifier still changing | **Open.** A change landing 2026-08-15 teaches it three declaration kinds it has no rule for |
| Plugin can ship a hook | **Resolved** 2026-08-15. `hooks/hooks.json` at plugin root, auto-enabled, no settings edit |
| Hook built, tested and published | **Done** 2026-08-15. `openhonest/honest-skills`, 100% branch coverage, CI on 3.9, 3.11 and 3.13 |
| L1.18 computed in the hook rather than delegated | **Blocked** on the classifier change. Design in `honest-skills/docs/l1-18-in-the-hook.md` |
| Output contract contradicts `tools/edit-replay/` | **Open.** Resolved in principle by §8.2 and §8.3 |
| Telemetry spec approved | **Open** |

**L1.18 is the blocker that matters.** It is the most useful of the four in scope, and it is blocked twice over: its thresholds were set against a different calculation from the one producing the number, and the classifier producing that number is still changing.

The second blocker moves published figures hard. libuv had 1,133 of 1,345 declarations unreadable; Newtonsoft.Json 678 of 1,360. Grades will fall when those become readable. A repository whose struct fields were 84 percent invisible was not passing, it was unexamined, so the fall is the instrument improving rather than the code degrading. Anything calibrated before it lands is calibrated against numbers that will not exist afterwards.

## 12. Risks

**It gets uninstalled.** The dominant risk, and firing on every write raises it. Mitigated by silence on pass and by treating the signal rate as a release gate rather than a dashboard number.

**The agent games it.** Mitigated by §8.1, and the risk is higher here than for an elective tool because the agent sees the response constantly.

**Thresholds are wrong, so verdicts are wrong.** Live today. Every band is provisional and the canon says so.

**The useful indicator does not run.** Live today. A bare install has no `slop-audit-l1` on PATH, so L1.18 reports `UNMEASURED` and the hook is reduced to line count and whitespace. This is honest and it is also thin. Closing it is the L1.18-in-the-hook work, and the cost of closing it is a third implementation to keep equal to the other two.

**Claude Code only.** The hook does not reach other agents. Mitigated by the MCP path, which is why it stays in scope.

**Telemetry poisoned or dominated.** Mitigated by per-UID aggregation, plausibility rejection, and median summaries. See §7 of the telemetry spec.

## 13. Open decisions

1. Ship four indicators, or wait for more to become file-scoped? **Decided:** shipped three, L1.14 dropped for the reason in §6.
2. Recalibrate L1.18 before shipping, or ship with a "provisional threshold" caveat in every surfaced verdict? **Decided:** the caveat, carried on every L1.18 finding and rendered to the reader rather than kept in the payload.
3. Is `SHIFTED` in v1 at all, given only 29% of files can produce it? **Open.**
4. Does the hook ship in the existing `honest-skills` plugin, or its own? **Decided:** the existing plugin.
5. Does the MCP live in this repository or its own? **Open.**

## 14. Suggested phasing

**v0.1 — shipped 2026-08-15.** Hook only, silent on pass, in the existing plugin. L1.16 and L1.17 computed locally, L1.18 delegated to the analyzer and `UNMEASURED` without it, reported once per session rather than once per write. Exit 0 and no output on a clean file; exit 2 and stderr on a finding, which is the only path that reaches the model. Twenty-eight tests, 100% branch coverage, CI on three interpreter versions. `claude plugin validate` clean.

**v0.1.1 — blocked.** L1.18 computed in the hook so a bare install measures it. Requires the ratio, a census denominator produced independently of its own enumerator, a refusal rule, capability fixtures that measure rather than assert, and a differential validator against the reference implementation as a CI gate. Waiting on the classifier change.

**v0.2** MCP server in the same plugin via `.mcp.json`, same indicators, for portability off Claude Code.

**v0.3** Telemetry, opt-in, off by default.

**v0.4** `SHIFTED`, once a baseline mechanism satisfies §8.3.

**v1.0** Thresholds recalibrated from collected distributions, at which point the verdicts mean what they say.
