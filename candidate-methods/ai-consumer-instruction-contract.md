# The instruction contract: process control inside the agent's edit loop (CANDIDATE)

**Status: candidate.** Not implemented, not canon. Written 2026-08-14, rewritten the same day at a different tempo.

## The bottom line

The process under control is **the agent's edit loop**, not the team's quarterly practice. Each write to a file is a sample. Feedback arrives while the agent is still working on that file, not after a commit and not in a report a CIO reads later.

Measured today, so this is affordable: the portable Rust binary audits a single-file directory in 68 ms including process spawn, and the Python analyzer runs the L1.18 classifier on one file in 261 to 345 ms, nearly all of it interpreter start. A per-edit audit costs less than the agent's own tokenization.

Three things change when the consumer is mid-edit rather than reading a report.

1. **A signal is an interrupt, not a finding.** It has to be silent in the common case or it will be turned off within a day.
2. **The chart's job is to separate a bad turn from a bad file.** A point outside the file's own limits means this edit did something new. A stably bad file is common cause and reacting to it is tampering.
3. **The loop must not report the score.** A number returned on every edit is a gradient, and a gradient is what an optimizer needs. This is the single design decision that keeps a tight feedback loop from becoming a gaming loop, and it is not optional.

An earlier draft of this document assumed windows of commits, a frozen historical baseline and a report. That cadence is wrong for this consumer. The four fields of the instruction survive. Almost nothing else does.

## 1. The subgroup is one write to one file

**Not one turn.** A turn may touch four files or none, and it has no single denominator. Turns are also not observable as a unit by anything outside the harness.

**Not one tool call.** Reads are not samples, and a single logical edit is often several calls.

**One completed write against one file.** It is atomic, it is machine-observable at the point the bytes hit disk, and it has a fixed denominator.

The constant-subgroup problem dissolves once the area of opportunity is the **file** rather than the edit. Every reading is a complete measurement of one file, so two consecutive readings share nearly the same denominator, which is the constancy an XmR chart needs. The charted statistic must therefore be a rate over the file (escapes per KLOC, mutable functions as a share of functions), never a count.

One residual problem, and it needs a stated rule rather than a silent assumption: the file grows during a session. **If measured LOC moves more than 50 percent from the baseline median, the limits are void and the chart reverts to "insufficient basis."** The 50 percent is arbitrary. Stating it is not.

Coalescing rule: one audit per completed write tool call, however many hunks it contained. A multi-hunk edit is one sample.

## 2. The baseline is the file's own committed revisions, frozen for the session

The three candidates and how each fails:

**Session-local, from the first N edits.** The first edits of a session are systematically unrepresentative, and a session that starts badly writes its own degradation into the center line. Worse, an agent that is optimized against limits it also generated is a closed loop with no external reference.

**Carried from the repository's commit history.** Right in spirit, wrong unit. A commit-window subgroup and a single-file edit are different quantities with different inherent variation, so those limits cannot be transferred.

**Per-file.** Right unit, no data. A file gets edited three times in a session and never reaches eight points.

**Chosen: a per-file baseline built from the file's own committed revisions.** For each file, check out the blob at each of the last K commits that touched it, run the fast panel on each blob, and compute limits from that series. The unit matches exactly, because a committed revision of a file **is** a saved version of that file. The tempo differs; the thing being measured does not. That equivalence is what makes this work and it is not available to either of the other options.

Cost: K times 68 ms, once per file, lazily on that file's first edit. At K equal to 20 that is 1.4 seconds, paid once.

The failure mode, stated rather than patched: **a new file has no baseline and gets no chart, and neither does a file with fewer than 8 revisions.** That is a large fraction of agent work. The honest handling is the detection-power gate from §7 of `layer1-longitudinal-method.md`, applied at this tempo: such a file reports against the specification bands only, with the explicit verdict "no control limits, insufficient history." It is never "stable."

## 3. The signal is an interrupt, and the response vocabulary has three members

The chart earns its place here by making one distinction nothing else makes:

| Reading | Meaning | Response |
|---|---|---|
| Inside limits, inside band | Stable and good | `continue` |
| Inside limits, outside band | **Bad file.** Common cause. | `continue`, and record it |
| Outside limits | **Bad turn.** This edit is unlike the file's history. | `revise_before_continuing` |
| Aperture membership broken, or a bright line crossed | Instrument or safety | `halt_and_report` |

The second row is the important one and its response is a null response. A stably bad file is a property of the practice, not of this edit. Interrupting the agent about it is Deming's funnel, and at seconds per sample it would interrupt on nearly every edit of every legacy file.

**Why not revert.** Automatic revert is wrong twice. It destroys work that may be correct, and it makes the metric authoritative over the task. An out-of-limits point says the edit is unlike the file's history, which is also what a correct refactor looks like. So the response is revise, within the same turn, before proceeding. An agent that judges the reading wrong may proceed with a recorded dissent, and that dissent is data about the instrument.

**Why halt is reserved.** Only two conditions halt: a broken aperture membership check (§4) and L1.14, a secret in the file. Both are cases where continuing is worse than stopping and where a human should see it.

Rate limit: at most one interrupt per file per turn. A large edit that trips six sites yields one instruction, not six.

Which signal rules can fire at this tempo. Rule 1, one point outside limits, is the primary and fires from the first edit. Rule 3, a moving range above the upper range limit, fires on a single volatile edit and is useful. Rule 2, eight consecutive points on one side, needs eight edits of the same file in one session, which happens but is not common. Report which rules are armed; a reader who assumes all three are live has been misled.

## 4. The aperture invariant, checked by assertion rather than by a reader

At this tempo nobody reads a reading, so the check has to be a pure function over two consecutive readings that is silent three times out of four.

The naive rule fails immediately. "The aperture must not shrink" fires on almost every good edit: deleting dead code shrinks measured LOC and is the correct remedy for L1.12, and replacing an if/elif chain with a dispatch table shrinks decision points and is the correct remedy for L1.19. The earlier draft noticed this for L1.19 and treated it as one awkward exception. At per-edit tempo it is the normal case, and a rule that fires on good edits gets disabled.

**The workable version separates deletion from reclassification.** Size is the wrong quantity; membership is the right one. Carry a hash over the set of measured **symbols**, not a count of lines, and compare consecutive readings:

- A symbol whose text no longer exists anywhere in the tree was **deleted**. Normal. Silent.
- A symbol whose text still exists but which left the measured set was **reclassified**. That is the violation, and it is the whole gaming class: the rename to `*_test.py`, the move under `vendor/`, the ignore directive at the head of the file, the path that now matches an exclusion.

The check returns one of four values, `unchanged`, `grew`, `shrank_by_deletion`, `shrank_by_reclassification`. Only the last produces output, and it halts.

The file-level half is cheaper and should ship first: `in_scope(path)` is already a pure function, so evaluate it before and after the write. A file that was in scope and is no longer has been reclassified, whatever else changed.

Cost, and it is real: this needs a symbol index the tool does not have. Without it, deletion and reclassification are indistinguishable and the invariant is guesswork.

## 5. What the agent receives

The four fields from the earlier draft survive: a closed-vocabulary `action`, a `remedy_class`, an `invariant`, an `expected_effect`. What changes is size, ordering and one field that must be deleted.

**One instruction, never a list.** A report can carry 44 findings. A mid-edit consumer gets one. The next audit is 68 ms away, so there is no reason to batch, and a batch of instructions is a batch the agent will triage by convenience.

**The action comes first, and in the common case it is the only field.**

```json
{"action": "continue"}
```

That is the whole payload for an in-control edit. No value, no band, no indicator name. See §7 for why the score is absent rather than merely deprioritized.

The non-silent case:

```json
{
  "action": "revise_before_continuing",
  "indicator": "L1.18",
  "site": { "file": "l1_analyzer/mutable_state.py", "symbol": "collect_bindings" },
  "remedy_class": "declare_at_boundary",
  "forbidden": ["rename_path", "move_into_test_scope", "add_ignore_directive", "widen_scope_exclusion"],
  "rule_fired": "point_outside_limits",
  "basis": { "baseline_revisions": 14, "source": "file_history" },
  "expected_effect": { "direction": "decrease", "unit": "mutable_functions" }
}
```

**`site` is a symbol, not a line.** Line numbers are stale by the time the agent reads them, because the agent is still editing.

**`basis` is new and it is what lets the agent decline honestly.** An instruction computed from 14 revisions of this file and one computed from no baseline at all deserve different weight, and only the instruction knows which it is.

**`rule_fired` is new.** Without it the agent cannot tell a special cause from a band failure, and those have opposite correct responses.

**`human` is deleted**, except under `halt_and_report` where a person does read it. There is no human in this loop, and free prose is the field most likely to be interpreted differently on every run.

**`expected_effect` changes character.** At report tempo it was a commitment verified days later. Here the next reading is the next write of the same file, seconds away, so it becomes a live guard: an instruction whose predicted movement does not appear is **withdrawn, not reissued**. Reissuing a refuted instruction is exactly how this loop becomes a nag. Note that `by_at_least` is gone, because a magnitude is a score.

**A latency budget belongs in the contract.** 100 ms for the fast panel. On timeout the loop emits `continue` and records a miss. An auditor that stalls the agent will be removed from the loop, so it must be structurally unable to stall it.

## 6. Which indicators can run at this tempo

This table is the honest core of the document. It is short on the left column and that is the finding.

| Indicator | Scope | Why |
|---|---|---|
| L1.1 Doc-only commit ratio | Commit | Ratio over `git log`. Undefined on an uncommitted file. |
| L1.2 Code-only commit ratio | Commit | Same |
| L1.3 Mixed commit ratio | Commit | Same |
| L1.4 Doc lines as share of lines added | Commit | Same |
| L1.5 Code delete/add ratio | Commit | Same |
| L1.6 Net-negative commit ratio | Commit | Same |
| L1.7 High-delete-ratio commit ratio | Commit | Same |
| L1.8 Test-to-production ratio | Commit | As implemented it is a `git log` query. It is the one of the eight that could be redefined as a ratio over the current tree, and if it were it would become repo-scoped, not per-file. |
| L1.9 Pre-commit hook config | Repo | Presence at repo root. Constant within a session. |
| L1.10 CI/CD pipeline config | Repo | Same |
| L1.11 Containerization | Repo | Same |
| L1.12 Unreachable code ratio | Repo | Reachability is a whole-program property. Per-file it reports symbols as dead that other files call, and a false positive is the worst thing to hand a tight loop. |
| L1.13 Fuzzy duplication ratio | Repo | A clone needs two sites. One file sees only its internal clones, and the dominant AI duplication pattern is across files. |
| **L1.14 Secret scan hits** | **Per-edit** | Purely local. A secret in the buffer is a secret. Bright line, halts. |
| **L1.15 Type-escape density** | **Per-edit** | Per-file scan, exact sites, unambiguous remedy class. Chartable as a rate. |
| **L1.16 Trailing-whitespace density** | **Per-edit** | Runs, but see below. |
| **L1.17 God-file concentration** | **Per-edit, degenerate** | Collapses to "is this file over 1,000 lines." A bright line, not a chart. |
| **L1.18 Mutable state ratio** | **Per-edit** | Per-file AST pass, 261 to 345 ms measured. The slowest item in the loop and the most informative. A rate over the file's functions, so it charts properly. |
| L1.19 Decision-space coverage | **Half** | The denominator is per-file and fast; the reference binary enumerated 92 decision points in one file. The numerator needs a test-execution trace over the repo. Per-edit you get a decision-point **count**, which is a different indicator and must be named as one rather than passed off as L1.19. |
| L1.20 Test determinism | Repo, slow | Five randomized full-suite runs. Minutes. Not in this loop at any tempo. |

Eight indicators need a commit. Seven need the whole repo. **Five run per edit, and only three of those are chartable**, because L1.14 and L1.17 are bright lines with no variation to chart. So this loop is a three-indicator chart plus two bright lines, not a twenty-indicator panel, and calling it a Slop Audit at this tempo would overstate it by a factor of four.

**Drop L1.16 from this loop.** It runs, and it should not. Its meaning is "nobody opened this file between the AI writing it and the commit landing," which is a staleness proxy. A per-edit loop with a formatter zeroes it while the underlying condition is unchanged. It is an indicator that measuring destroys, and that is a reason to exclude it, not to report it carefully.

That leaves **L1.15 and L1.18 as the chartable pair**, plus L1.14 and L1.17 as bright lines.

## 7. Gaming, which is the reason to be careful rather than fast

A per-edit score is the strongest gaming pressure this instrument can be placed under, and it is worse than the report case in three specific ways.

1. **The optimizer gets thousands of trials per hour** against a deterministic function, at 68 ms each.
2. **Feedback arrives faster than deliberation.** Behavior that moves the number lands before any reasoning about whether it should.
3. **The aperture rules calibrated for report tempo fire constantly here** (§4), so the pressure to relax them is continuous.

**What makes the loop safe is withholding the value.** An alarm and an objective differ precisely: an objective returns a number on every edit, and a number on every edit is a gradient. An alarm returns the same output for every edit that is in control, which offers nothing to climb. So the agent receives `{"action": "continue"}` with no score attached, or an instruction naming sites. It never receives "L1.18 is 12.3 percent." This is a design constraint, not a preference, and every field in §5 was checked against it.

That is not complete safety, and three holes remain open.

**The agent can run the auditor itself.** The binary is in the tree. A harness can withhold it, but a coding agent with a shell can reimplement the L1.15 grep in a minute. **This loop's safety rests on the agent not being adversarial, and that assumption should be written down rather than left implicit.** It is the assumption most likely to stop holding.

**Withholding the score costs verification.** The agent cannot check its own `expected_effect` if it cannot see the value, so verification moves into the loop and out of the agent. You can have an agent-verifiable prediction or a gradient-free channel. Not both. This document picks gradient-free.

**The letter-versus-meaning gap is untouched and gets worse with speed.** The earlier draft named it: `Any` replaced by a five-member union is `narrow_type` performed, invariant held, and possibly meaningless. At 68 ms per trial the agent finds that move faster. Of the two chartable indicators, L1.18 resists this better than L1.15, because reducing mutable state requires changing the shape, and the cheap fakes (threading a mutable object through the parameter list, hiding state in a default argument) are themselves detectable. Detectable, though, only if something looks for them, and nothing does.

**Stated plainly: this loop is not yet safe to run as an objective. It is safe to run as an alarm, and only because an alarm gives no gradient.** Anyone who adds a score display to it has changed it into the other thing.

## What it does not solve

**It does not verify intent.** Declared-against-exercised is measurable. Declared-against-meant is not, and nothing here reaches it.

**It does not work on new files**, which is much of what an agent writes. No history, no baseline, no chart, and the correct output in that case is an admission rather than a default limit.

**It does not detect the aperture move without a symbol index** (§4). Until that index exists, deletion and reclassification look identical and the invariant is a hope.

**It does not help where the finding is the absence of something.** L1.10 asking for more CI pipelines is satisfied by five empty workflow files. Speed makes that easier to automate, not harder.

## Smallest useful first step

Build none of the statistics. Test the thing most likely to kill the design, which is the interrupt rate.

1. Run the existing Rust binary against the single written file after every write, with a 100 ms budget and `continue` on timeout.
2. Emit exactly two checks, both bright lines that need no baseline and return no value: `in_scope(path)` compared before and after the write, and L1.14.
3. Measure how often it fires across a week of real sessions.

**If it interrupts more than once per session, the loop is noise and nothing else in this document should be built.** If the rate is tolerable, add L1.18 with a per-file baseline from committed revisions and find out whether the chart signals at all before adding L1.15, the instruction payload or the symbol index.

That order is deliberate. Every version of this design that has been sketched, including the one this file replaced, front-loads the statistics and leaves the question of whether anyone can stand the interruptions for later.
