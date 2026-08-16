# Dispatch tables close open input, and the meter cannot see it

**Status: proposal, not approved. Written 2026-08-16.** It changes what L1.18b calls bounded, so it moves published numbers and needs an amendment before it ships.

## The rule

A table whose keys are written out is a closed set, and a read into it is bounded by the number of keys, **whatever the key expression is**. `HANDLERS[channel]` against `HANDLERS = {"email": ..., "sms": ...}` has a reaching partition of two. It does not become unbounded because `channel` is a parameter.

The spec already says half of this. `spec/03-layer1-indicators.md` records L1.18 as bound-aware, because "a read keyed by a literal against a closed set is exhaustively testable and an unbounded accumulator is not." The half it does not say is that the *key* need not be literal. The set is closed by the table's definition, not by the call site.

## What the meter does instead

It counts a partition only where the literals are written out one at a time at the read. A variable key is graded unbounded, so a bounded dispatch table is graded identically to a growing cache.

The consequence was measured while trying to set the grade-D threshold. Across nine repositories the classifier found 1,669 partitions. Only 39 were unordered, with a median of 5 classes and a maximum of 14, and no break anywhere in the distribution to put a threshold in. The conclusion recorded at the time is the finding:

> D is not empty because code is good. It is empty because F swallowed its population. A bounded 500-key dispatch table gets graded F today, identically to genuinely unbounded state.

And the reason the distribution has no tail:

> The sample is truncated by our own instrument, not by reality. Big tables never reach this distribution, because a variable-keyed lookup is already unbounded and already F.

So the D dial is set to `None` today, and the reason it could not be set is this defect rather than an absence of large dispatch in real code.

## Why this matters beyond grade D

It runs opposite to the closure blind spot recorded in the same period. That one makes the meter report too little: a closure mutating a captured accumulator scores 0.0 and Healthy in every language. This one makes it report too much. Both have the same root, which is that the universe of state is a list of declaration-site kinds and the partition is counted only from literals at the read.

The practical effect on a published number is therefore not one-way. A codebase carrying closures is understated. A codebase carrying large literal dispatch tables is overstated. Net direction per repository is unknown, and no disclosure currently reports either.

## The second half, which is not optional

A closed table read with a silent default is not closed for the caller. `table.get(key, default)` files an input nobody wrote a rule for under an answer written for a different input, and nothing downstream can tell a hit from a miss. The bound the table declares is real; the default discards it.

So the rule has two clauses, and a meter that implements only the first will bless code that has re-opened its own input space:

1. A read into a table with literal keys is bounded by the key count, whatever the key expression.
2. Clause 1 holds only where a miss is observable. A subscript raises; a `get` with a default does not. A defaulted read is not a bounded read, and it should surface as its own finding rather than as a clean bound.

The analyzer already writes this discipline down for itself, at `tools/l1_analyzer/l1_analyzer/state_sites.py:74`: `DECL_KIND` is "subscripted by both walks, never `.get`: a node type nobody assigned a kind must be a KeyError on the next run, because the alternative, a default kind, files a new construct under an existing capability answer and hides it there." The rule proposed here is that comment applied to the code under audit rather than only to the auditor.

## What it would take

Counting a literal table's keys at its definition, and following a variable key from the read back to that definition. That is new analysis rather than a threshold: today nothing resolves a name at a read site back to the binding that defines it. Scope is a single-module resolution in the common case, and the honest fallback where the table is imported or built at runtime is UNRESOLVED, not bounded.

Clause 2 is cheap by comparison: the read form is visible at the call site.

## What must be decided

**Whether it ships with the closure correction or separately.** They are the same root and move the number in opposite directions, so shipping them together is the only way to report a net effect that means anything. Shipping the closure fix alone publishes a number that is corrected in one direction and still wrong in the other.

**Whether grade D survives.** If the population it was written for has been sitting in F all along, then turning this on gives D a population for the first time, and the threshold question reopens on data that finally contains large tables. The 15-class figure that was rejected as indefensible was rejected against a truncated sample.

**Whether clause 2 is a finding or a modifier.** A defaulted read could downgrade the bound to UNRESOLVED, or it could stand as its own named finding beside a bound that is otherwise real. The second is more informative and more work.

## Related

- `../../../honest-framework/specs/finite-testability.md` §4, "Bounded includes declared-closed-set dynamic access", and the `closed-set-dispatch` vector in `finite-testability-vectors.json`, which already give the NEUTRAL verdict this proposal asks the meter to reach.
- `honest-code-principles.md`, "Dispatch Tables Close Open Input", which states the same rule as a coding practice.
- `collecting-unmeasured-constructs.md`, for what to do with a read this rule cannot resolve.
