# Report what the analyzer could not see as silence, not as a lower grade

**Status: proposal, not approved. Written 2026-08-15.** It changes how L1.18b reports and therefore changes published grades, so it needs a decision before any code moves.

## The recommendation

Split one number into two. Grade the code on the state the analyzer could observe. Report the state it could not observe as a silence index beside the grade, never inside it. Refuse to issue a grade at all when silence rises above a floor.

The tool currently reports its own blind spots as defects in the audited code. That is the same fault the portable binary had this morning, when it omitted six indicators and said nothing, and the same fault the parity differ had, when it compared only the keys the two implementations already shared. Three instances in one day is a pattern, and the pattern is that we let "I could not measure this" and "this is wrong" come out of the same hole.

## What happens today

`report.py:69` decides status from two counts:

    if counts["promiscuous"] > 0:  return "cannot"
    if counts["unresolved"] > 0:   return "might"
    return "can"

`report.py:90` turns that into a grade: `cannot` is F, `might` is D, and only `can` reaches A, B or C.

So **one unresolved state caps an entire repository at D**, whatever else is true of it. A codebase with 500 pieces of state, 499 of them provably finite, grades D if the analyzer cannot read one call.

The word "unresolved" is doing work it cannot support. `state_bounds.py:315-321` returns undecidable for any argument position unless the callee is one of eight named builtins or six named effect calls. Everything else is undecidable by default. That includes calls the analyzer could read and simply does not, such as `sorted`, and calls it genuinely cannot read, such as a third-party method. Both land in the same bucket, and that bucket costs a grade band.

The tool already computes the right quantity and then ignores it. `state_bounds.py:885` sets `resolvable_fraction` to the share of state it actually decided. Nothing in the grade consults it.

## What this costs, on real code

Three measurements from an external adopter's production codebases, taken this week:

| Repository | Counts | Grade today | Cause |
|---|---|---|---|
| open-vrm-app-3, before fixes | 1 unbounded, 1 undetermined | F | a real unbounded state |
| open-vrm-app-3, mid-fixes | 0 unbounded, 1 undetermined | D | the analyzer could not read one call |
| open-vrm-app-3, after fixes | 0, 0 | C | nothing left to see |
| bracer-v1 | 1 unbounded, 3 undetermined | F | one real finding, three blind spots |

The middle row is the whole argument. That repository sat at D for one reason: our analyzer could not see through a call. Nothing about their code changed between D and C. We fixed our reading and their grade rose two bands.

Of bracer-v1's three undetermined states, one is `sorted(by_doc.items(), ...)`, which we could read and do not. The other two are `openpyxl` save calls, which we genuinely cannot read. Under the current grade those three are indistinguishable from defects.

## The proposal

**One. Report silence as its own measure.** Silence is the share of state whose disposition the analyzer could not decide, which is one minus the resolvable fraction already computed. It is reported with the file and line of every silent site, so a reader can look at each one.

**Two. Grade on observed state only.** The counts that decide status become counts over decided state. An undecided state no longer contributes to `cannot` or `might`, because it is not evidence about the code.

**Three. Refuse to grade below a coverage floor.** When silence exceeds the floor, status is `na` and no grade is issued. This is the poka-yoke and it is the part that must not be dropped: without it, code that hides everything from the analyzer would score A on zero observed state. The floor makes obscurity produce no grade rather than a good one. The tool already has an `na` status and both consumers already handle it, so the machinery exists.

**Four. Keep a distinct verdict for genuinely unreadable calls.** "I could not see into this library" and "I have not taught the analyzer this builtin" are different facts. The first is a boundary the adopter could make readable with a typed wrapper. The second is our backlog. Reporting them as one number tells the adopter to fix something that is ours.

## Why silence is the right axis, and not a softer grade

Silence is actionable in the direction the framework already points. You reduce it by making a boundary readable, with an explicit contract at the edge, which is what the Honest Framework asks for anyway. The number then pushes the same way as the principle.

It also removes a perverse incentive. Today, using a third-party library lowers your correctness score, and the only action that follows is to use fewer libraries. Nobody should take that advice from us.

Finally, it stops the enumeration problem being load-bearing. The eight-name builtin list and the six-name effect list are correctness dependencies right now, because a name missing from either produces a confident wrong verdict. Under a silence axis a missing name raises silence instead. The tool says "I could not see this," which is true, and the lists become an optimization rather than a source of false findings.

## The cost, stated plainly

**Published grades change.** Any repository with undetermined state and no promiscuous state moves up. Comparisons against grades published before the change are invalid, and any measurement in a paper or a report card that quoted a D may now read differently. This is the real price and there is no version of the change that avoids it.

Two things reduce it. The change is monotone in a known direction: no repository can move down, so nobody's published grade becomes worse than what they were told. And the analyzer version can be pinned beside the grade, which the longitudinal work already recommends for other reasons.

## What must be decided

**The floor.** Below what coverage do we refuse to grade? A defensible starting point is that silence above 10% of state suppresses the grade, but the number should come from running the proposal over the pinned corpus and the two adopter codebases, not from taste.

**Whether silence appears in the grade at all.** The recommendation here is that it does not, and instead gates whether a grade exists. The alternative is a compound grade such as "C at 92% coverage." That is more honest on the face of it, and it is harder to quote correctly, which matters for a measure that ends up in procurement documents.

**Whether to fix `sorted` first or wait.** Adding readable builtins reduces silence without touching the grade design, and it is a smaller change. Doing it first makes the silence numbers used to set the floor more representative.

## What this does not change

The unbounded verdict keeps its full weight. A piece of state that provably reaches an unbounded decision is still F, and none of this softens that. The proposal only concerns state the analyzer did not decide, and its entire claim is that not deciding is not a finding.

## What D should mean once it is free

Moving silence off the grade vacates D, which today means "the analyzer did not decide." Adam's instruction is that D should carry a positive finding instead: **state whose reaching partition is finite, but too large to cover even with limit testing.**

That category does not exist in the classifier. `state_bounds.py:63` defines `_FINITE` as one label, and `_keyed_read` at line 259 returns finite or unbounded with nothing between them. A partition of two classes and a partition of four billion both come out as finite. So the grade cannot express the distinction because the measurement never made it.

### The distinction that makes it decidable

Cardinality alone is the wrong test, because limit testing defeats large ordered domains. A 64-bit integer compared against three constants induces four classes over an ordered domain, and boundary selection covers it with a handful of values. Size did not defeat the tester; structure saved them.

What limit testing cannot defeat is a large **unordered** partition. A map keyed by five hundred distinct string literals, each key reaching a different branch, induces five hundred classes with no boundaries between them. There is no value "just above" a string key. Covering it needs five hundred tests, and no boundary trick reduces that.

So the rule has two parts, and both are needed:

> D when the reaching partition is finite, its members are unordered, and its cardinality exceeds a stated bound.

The analyzer already knows the second part without new analysis. It reaches finiteness by distinct routes, and the route carries the structure. A comparison arm produces an ordered partition. A membership test against a closed set, or a keyed read against literal keys, produces an unordered one. Those are different branches of `_categorize` today and are simply not recorded.

### What has to be built

**Carry a count, not a category.** The finite verdict becomes finite plus a cardinality and an ordered flag. Every branch that currently returns `_FINITE` knows enough to supply both: a comparison chain of n operators gives n+1 ordered classes, a closed set of size k gives k+1 unordered, a literal-keyed read gives one class per distinct literal, an `isinstance` over k types gives k unordered.

**Decide what to do when the count is unknown.** Some finite partitions have no count the analyzer can recover. Under this proposal that is silence, not D, which is the same rule applied consistently: an unknown count is a limit of the analyzer, and D is a claim about the code.

**Compose across states.** Two states that decide the same branch multiply rather than add. This is the hard part and the place where a real codebase crosses any threshold fastest. A first version can report per-state cardinality and leave composition out, provided the report says so, because a per-state number that is honest beats a composed number that is guessed.

### The threshold

The bound has to come from measurement, not from taste. Run the counting version over the pinned corpus and the two adopter codebases, plot the distribution of per-state cardinalities, and look for where real code actually sits. A bound that puts most production state in D is measuring our impatience rather than their testability.

One anchor worth using: the path-cover check already reports how many end-to-end runs cover every branch, and an adopter's report this week read 3,431 runs. That number is large for a person and unremarkable for a machine, which is the clearest sign that the threshold question is about who is doing the testing, and that the document should say which.

### Order of work

This depends on the silence change and cannot ship before it. D is occupied. Until unresolved state moves off the grade, giving D a second meaning would make one letter mean both "we could not tell" and "we positively identified a coverage problem," which is worse than what we have now.

---

## What the measurement found

**Implemented 2026-08-15.** Both changes are in `tools/l1_analyzer`. The floor and the bound were run over the six pinned corpus repositories (`tools/slop-audit-rs/corpus.toml`), this repository, and nine local Python trees added because the pinned six are Java, C# and C and all six already grade F on proven unbounded state, so none of them can show what a floor does to a repository that would otherwise be graded.

### Silence, and who owns it

Per-repository silence, as a share of all state:

| Repository | Silence | Repository | Silence |
|---|---|---|---|
| libuv | 0.458 | honest-framework | 0.175 |
| json-c | 0.450 | multicardz | 0.123 |
| junit4 | 0.384 | declaro | 0.105 |
| gson | 0.269 | slop-audit, weights-watch, challenge, honest-starter, slop-audit-web, open-vrm-app | 0.000 |
| RestSharp | 0.245 | umbra | 0.500 |
| Newtonsoft.Json | 0.223 | | |

By reason, pooled over 667 silent states: **unmodeled callee 362, external boundary 255, dynamic dispatch 49, injected slot 1**. More than half the silence is a name we could teach the analyzer and have not. That is the number part four was written to expose, and it says the largest single reduction available is ours to make, not the adopter's.

**The floor is 0.50.** It sits just above the worst silence the analyzer produces on the pinned corpus, so no repository is refused a grade for a limit of our reading. That makes it a ratchet rather than a quality bar: every builtin taught to the analyzer lowers observed silence, and the floor comes down with it. A 0.10 floor, the starting point proposed above, would refuse to grade ten of the sixteen repositories measured, which measures our reading and not their obscurity.

The floor is consulted **after** the promiscuous check, not before. A promiscuous finding is a proof, and a proof stands whatever else went unread; letting the floor erase a proven F would be the same error backwards.

### Cardinality, and why no bound is set

Unordered partitions over state that decides something, pooled over all sixteen repositories, n=36:

| classes | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|
| states | 6 | 7 | 7 | 4 | 1 | 2 | 4 | 2 | 2 | 1 |

Ordered partitions, n=360, are almost all 2 classes (282 of them) and reach 15 at most. No partition of either kind was uncounted anywhere in the corpus.

**Not reproduced, 2026-08-18.** Re-running the same sixteen repositories under the current analyzer gives unordered n=94 with a widest of 20, including one state each at 16, 18 and 20, and ordered n=314 with a widest of 10. Both halves of the table below therefore disagree with the instrument that produced them. The no-upper-tail claim in the paragraph that follows is the whole argument for leaving the bound unset, and it does not currently hold. The cause is not yet known: it is either the classifier moving since 2026-08-15 or a difference between the re-run's counting method and the original's, and the re-run pooled findings whose state drives a decision, reading the class count and the ordered flag off each partition. Correcting the double-counted literal key on the same date accounts for almost none of it, moving four states down by a class or two and changing neither the count nor the maximum. Tracked as slop-audit-43g. Nothing below has been edited, because replacing measured figures with figures whose method has not been reconciled would repeat the error rather than fix it.

**The widest unordered partition in any repository measured was 14 classes, and there is no upper tail.** The distribution therefore fixes a floor for any bound — 14 or less would put ordinary production state in D — and says nothing at all about where above 15 to put it. Picking 20, or 100, would be inventing the number the measurement was supposed to supply. So `report.UNORDERED_CLASS_BOUND` is `None`, D is switched off, and no repository is graded D.

The empty tail is a limit of the instrument, not a fact about code, and it is the more important finding. The five-hundred-string-key dispatch table the rule was written for reaches this meter as a keyed read with a **variable** key, which is unbounded and already F. A partition is counted here only when the literals are written out one at a time, and nobody writes five hundred of those. **D as specified is close to unreachable by the current measurement.** Making it reachable means counting the keys of a literal table at its definition and following a variable key into it, which is a new analysis, not a threshold.

### What this version does not do

Cardinality is per state and does not compose. Two states that decide the same branch multiply; within one state the roll-up sums distinct discriminators rather than refining them. Both are under-counts, which is the safe direction for a measure that only accuses, and every report that quotes the number says so.
