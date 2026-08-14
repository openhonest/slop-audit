# The instruction contract: JSON for an AI consumer (CANDIDATE)

**Status: candidate.** Not implemented, not canon. Written 2026-08-14.

## The bottom line

The JSON output today reports a **state**: a value, a band, a details string. A human reads a state and decides what to do. An AI consumer cannot, reliably, because "Slop" does not name an action and prose advice is interpreted differently every run.

So the output must emit a **transition** instead: do this exact thing, at these exact sites, do not do these things, and here is what the next measurement will show if you did it. The next run then verifies. That loop is what makes the number process control rather than a grade, and it is the same loop whether the actor is a person or a model.

The instruction has to carry four things the current output does not: **a closed-vocabulary action**, **the remedy class**, **an invariant naming what must not move**, and **an expected effect**. The invariant is the load-bearing one, because the cheapest way for any optimiser to improve an indicator is to shrink what the instrument can see.

## Why the invariant, first

The scope rule was gameable until today: renaming a package to `Core.Tests` removed it from eight measures and flipped the gate, with zero bytes changed. That specific hole is closed. The class is not, and cannot be closed by patching rules one at a time, because every scope rule is a rule about what to look at and any such rule can be satisfied by looking away.

The general defence is not a better rule. It is to make the aperture a **measured quantity** that travels with the score, and to state, in the instruction itself, that it must not shrink. Then aperture shrink stops being an undetected win and becomes a detected signal, which is exactly what a control chart is for.

## The shape

Three additions to the existing JSON. Nothing is removed, so every current consumer keeps working.

### 1. `surface`, per run

```json
"surface": {
  "measured_files": 48,
  "measured_loc": 9123,
  "scoped_out": { "vendored": 89, "tests": 12, "docs": 3 },
  "measured_fraction": 0.80,
  "aperture_digest": "sha256:5f2c…"
}
```

`aperture_digest` is a hash over the sorted list of measured file paths. It is the identity of what was looked at. Two runs with the same digest looked at the same code; two runs with different digests did not, and any comparison between their scores is a comparison of two different questions.

### 2. `instructions`, an ordered array

```json
{
  "id": "L1.15:narrow_type:tools/l1_analyzer/cli.py:292:Any",
  "indicator": "L1.15",
  "action": "narrow_type",
  "site": { "file": "tools/l1_analyzer/cli.py", "line": 292, "token": "Any" },
  "remedy_class": "declare_at_boundary",
  "forbidden": [
    "rename_path", "move_into_test_scope", "delete_file",
    "add_ignore_directive", "widen_scope_exclusion", "split_file_only"
  ],
  "invariant": { "measured_files_min": 48, "measured_loc_min": 9123 },
  "expected_effect": { "indicator": "L1.15", "direction": "decrease", "by_at_least": 1, "unit": "escapes" },
  "human": "The panel value is a dict[str, object]; narrow it to the union it actually holds."
}
```

Four fields carry the weight.

**`action`** comes from a closed vocabulary, never free text: `narrow_type`, `remove_escape_hatch`, `split_file`, `remove_dead_symbol`, `deduplicate_block`, `remove_secret`, `bound_state`, `replace_branch_with_dispatch`, `add_test`. A closed set is what makes two runs of the same model produce the same edit.

**`remedy_class`** is not decoration and is the field most likely to prevent wasted work. Umbra's evidence: 72 percent of its silences are types permitting more than the code means, which close with a declaration at the boundary, and a quarter are branches that dispatch removes. Only a small remainder wants a test. An AI handed a finding with no remedy class defaults to writing a test, and would have written 1,478 of them. The classes are `declare_at_boundary`, `remove_by_dispatch`, `delete`, `extract`, `add_test`.

**`forbidden`** enumerates the aperture moves. It is not a hope that the model behaves; it is the list the verifier checks against the diff.

**`expected_effect`** is what makes the instruction an intervention rather than a suggestion. It is a prediction, made before the edit, that the next run either confirms or refutes.

### 3. `verification`, on the following run

```json
"verification": {
  "against_run": "sha256:5f2c…",
  "instructions_closed": 3,
  "instructions_open": 41,
  "effects_confirmed": 3,
  "effects_refuted": 0,
  "aperture": "unchanged",
  "verdict": "intervention_effective"
}
```

`aperture` takes one of `unchanged`, `grew`, `shrank`. A `shrank` with improved scores is the gaming signature and must be reported as such, not as an improvement.

## How it counts toward the SPC

The longitudinal reading in `layer1-longitudinal-method.md` treats each measurement window as a subgroup and asks whether the process changed. The instruction contract supplies the missing half: **what was done to the process between subgroups.**

- Without instructions, a chart shows movement and nobody knows why. Attribution is guesswork.
- With them, each point carries the interventions issued before it and whether their predicted effects landed. A point that moves with confirmed effects is a **deliberate process change**. A point that moves with no instructions closed is a **special cause to investigate**. A point that improves while the aperture shrank is **tampering with the instrument**, which is a third thing entirely and currently invisible.

That is the difference between a chart of a process and a chart of a process you are steering.

It also gives the action rule something to act on. "Stable and bad" tells a CIO to change the practice. The instruction set is the practice change, expressed as a list of edits with predicted effects, and the next window says whether it worked.

## What it costs

- **Stable identities.** Instruction `id` must survive a file move, or every refactor looks like 40 closed and 40 new instructions. Path-plus-line is fragile; path-plus-symbol is better; neither is free.
- **Per-indicator work.** Nine of the twenty indicators can emit site-level instructions today. L1.1 through L1.8 are commit-history ratios with no site, and their instruction is a practice change, not an edit. Those need a different shape and probably a different verb.
- **A verifier.** The `forbidden` list is worth nothing without something that reads the diff and checks it. That is a new component, and it is the piece most likely to be skipped.
- **Prediction is a commitment.** `by_at_least` will sometimes be wrong, and a wrong prediction is a visible failure of the instrument. That is the correct trade and it should be stated rather than softened.

## What it does not solve

**It does not stop a model satisfying the letter.** `Any` replaced by a five-member union is `narrow_type` performed, effect confirmed, invariant held, and possibly meaningless. Declared-against-exercised is measurable; declared-against-meant is not, and nothing here reaches it.

**It does not make L1.19 unambiguous.** Replacing an if/elif chain with a dispatch table removes decision points. That is aperture shrink and it is also the correct remedy, so `replace_branch_with_dispatch` will trip an aperture check that cannot tell it from a rename. The honest handling is to whitelist that action as an expected aperture reducer and report it separately, not to pretend the ambiguity is resolved.

**It does not help where the finding is the absence of something.** L1.10 asking for more CI pipelines is satisfied by five empty workflow files. An instruction contract makes that easier to automate, not harder.

## Smallest useful first step

Do not build all of it. Build `surface` and the `invariant`, for one indicator, and wire the aperture check into the existing gate:

1. Emit `surface` in the JSON, including `aperture_digest`.
2. Add `--min-measured-fraction` to the gate, ratcheted in `.pre-commit-config.yaml` beside the two ratchets already there.
3. Emit `instructions` for L1.15 only, since its sites are exact and its remedy class is unambiguous.

That is a day's work, it closes the aperture class rather than one hole in it, and everything above can be added to it incrementally without breaking a consumer.
