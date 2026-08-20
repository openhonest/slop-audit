# The prove loop, run against a real model for the first time

**Status:** first live end-to-end run. Records what the loop did, not a verdict about any codebase.
**Analyzer commit:** `ff1d4a7` plus the decline-reporting fix.
**Target:** `tools/l1_analyzer` (this repository's own package), swept as a Python project under its own interpreter.
**Model:** `claude-sonnet-5`, key read from `~/dev/.env`.

## Bottom line

The loop works. Given an uncovered branch, a model writes a test, the test compiles, runs in the target's own environment, and lands in a named outcome bucket. Nothing was retained, because a proof is retained only when the generated test FAILS and so proves a divergence between the code and the behaviour a reader would expect.

| ceiling | located | attempted | generated and run | passed | retained | declined |
|---|---|---|---|---|---|---|
| 2 | 155 | 2 | 2 | 2 | 0 | 0 |
| 20 | 157 | 20 | 15 | 15 | 0 | 5 |
| 3 | 157 | 3 | 2 | 2 | 0 | 1 |

Every generated test passed. On this package, over these branches, the model could not write an assertion the code failed. That is a weak positive signal about the code and a strong one about the loop: fifteen tests that compile and run against real production code, generated from nothing but the function source and the branch location.

**Correction, 2026-08-19, later the same day.** Read those pass counts as an upper bound, not a measurement. At the time of these runs the loop could not tell a test that asserted and held from one that asserted nothing: a body whose assertion sat inside a nested function nobody calls ran green and was filed under `pass`, whose report reads "branch correct." The loop asks for the BODY of a test, and a whole test module is the shape every pytest file a model has read actually has, so the wrong shape was the more familiar one.

The tool now refuses such a body at the proposal, in both languages, and a refused proposal is counted as a decline rather than a pass. These runs predate that. The passing test sources are not kept, only the retained ones, so nothing here can say how many of the thirty passes evaluated an assertion. A re-run under the fixed tool would settle it and has not been made.

Two of the swept trees were checked against the other fault found the same day: `l1_analyzer` and `requests` both carry `__init__.py`, so the module path handed to the model was correct for both and the namespace-package defect did not touch these runs.

## Four defects the run found, none findable without it

Each was shipped, and each was invisible to a suite that stubs the model.

**The reply reader assumed the first content block is text.** `response.content[0].text` raised `AttributeError` on every call, because a thinking-capable model puts a `ThinkingBlock` first. A direct probe against the same key and model succeeded, since it asked a question short enough to produce no thinking block, so the failure read as a configuration problem for two rounds.

**One `None` stood for four refusals.** No key, no SDK installed, a failed request, and a model with nothing usable to say all returned nothing. The first sweep reported "the model returned nothing usable for 2 of them" when no request had been made: `anthropic` is an optional extra and was not installed.

**A declined gap was counted nowhere.** It was dropped before the tally, so a call that cost money left no trace and the sweep fell through to the sentence it prints when it located nothing at all, over a module with 154 uncovered branches.

**The breakdown accounted for 15 of 20 attempts.** Declines were named only when nothing ran, so a reader reconciling the 20-attempt run against its bill was five short with nothing to explain the gap.

## What this does not show

No proof was retained, so the retention gate is still unexercised against a real model. The two pinned corpus repositories were offered and refused: both fail their own `pytest` with exit 4, so sweeping them means installing their development dependencies, which would mutate the parity baseline. Neither has been swept.

The ceiling is a total across the run, adjustable, and starts at 5. Every figure above is bounded by it, and the tool says so in its own output rather than leaving a truncated sweep to read as a complete one.
