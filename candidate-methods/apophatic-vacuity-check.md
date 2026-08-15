# The vacuity check, stated only in the negative

**Status: proposal, not approved. Written 2026-08-15.**

## The recommendation

Add a check that finds paths where a positive verdict can be reached from an empty input, and give it no way to say anything good. It reports only what cannot be relied on. It has no Healthy band, no clean verdict, and no pass. It cannot certify an instrument, only fail to convict one.

The constraint is not a house style. It is what makes the check immune to the defect it detects. A checker with an affirmative output can fabricate that output from nothing, which is the exact failure being measured, and it would then certify itself.

## What it looks for

One shape, found eleven times in this codebase and its neighbors in two days:

**A denominator that can be zero, feeding an output that asserts a property.**

- the portable binary emitted fifteen rows against a reference twenty-one and said nothing about the six
- the parity differ compared the intersection of two key sets and read 16/16 across a set excluding the headline indicator
- `gitleaks` exits non-zero when it finds leaks, and the wrapper swallowed that to an empty string, so a repository holding live credentials read Healthy
- the card turned `verdict: n/a, counts 0/0/0` into "definitely CAN be exhaustively tested" with a path-cover figure attached
- silence, the resolvable fraction and the partition count were all computed over the classifier's own recognition set, so failing to recognize produced no signal anywhere
- L1.15 returns 0.0 and Healthy for any repository under a thousand production lines, however many escape hatches it holds
- a timeout handler captured the child's output and reported only that a timeout occurred

Seventy-seven emission points in this package produce a band or a verdict. The question at each is mechanical: can control reach it with the denominator at zero and the output affirmative.

## The four rules that keep it apophatic

**One. No Healthy band, and no band at all.** A band is a statement that a level is acceptable. This check never says a measurement is sound, because soundness is not what an absence of findings shows.

**Two. Zero findings is not a pass and must not render as one.** It renders as the negation with its own reach attached: *no vacuous path found, under 14 rules, across 77 emission points, in 9 of 9 languages*. The numbers are the disclosure. A reader who wants to know how much that is worth can see how much was looked at, which is the thing every check in this repository has failed to say.

**Three. Every finding is phrased as a withdrawal, never as a fault.** Not "this indicator is wrong" but "this output cannot be relied on when the input is empty, and here is the path". The check does not know whether the empty case ever occurs in practice. It knows the path exists.

**Four. It must be able to convict itself, and it is run against itself first.** A check that emits a band is its own finding. If the vacuity check ever reports clean on its own source, either the code is right or the check is broken, and the apophatic form means those two are distinguishable: it cannot report clean, it can only report the negation with its reach.

## Why the negative form is load-bearing rather than decorative

The positive form of this check would be "this instrument is trustworthy". That claim has a denominator: the set of ways an instrument can lie. Nobody can enumerate it. So a positive verdict would be computed over its own recognition set, which is the defect, one level up. Every affirmative safety claim has this problem and it is why the apophatic form is not available as a preference.

The negative form has no such denominator. "Here is a path" is a proof, and it needs no completeness to be true. "Here is no path" is not a claim at all under rule two, because it is always stated with its reach.

## The poka-yoke answer

Which category of bug does this make structurally impossible? For the audited code, none: it is a detector, and detectors prevent nothing.

For the checker, one, and it is the point. **A tool with no affirmative output cannot fabricate an affirmative output.** The eleven instances above are all a positive claim manufactured from an empty input. Remove the ability to make a positive claim and that class cannot occur in this check, by construction rather than by care.

## What would make it fail

It is worth saying in advance what would sink this.

If the eleven instances turn out to share no mechanical signature, and each needs its own hand-written rule, then the check is an enumeration wearing a detector's clothes, and this codebase has had five of those produce confident wrong answers in a week.

If the reachability question is undecidable often enough that most emission points come back unknown, the finding list is dominated by our own limits and says nothing about the code.

The test is cheap. Take the eleven, and see whether a single rule over the AST finds them without naming any of them.

## What it is not

It is not a replacement for a test suite, and it does not measure whether an instrument is correct. An indicator can be perfectly implemented, never vacuous, and still measure the wrong quantity. L1.19 does exactly that today: it reports branch coverage under a definition that calls for decision-space coverage, and no vacuity check would notice.
