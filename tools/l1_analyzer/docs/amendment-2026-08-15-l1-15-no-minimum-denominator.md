# Amendment 2026-08-15: L1.15 loses its thousand-line floor, and gains no minimum in its place

L1.15 published a fabricated number over a non-empty input for as long as it has existed. Any repository or file under 1,000 production lines reported 0.0 escapes per kLOC and band Healthy, however many escape hatches it actually held. The floor is deleted. Both implementations moved in this change, and corpus parity is re-run at 16/16 across all six pinned repositories.

**No published repository figure moves.** Every repository ever measured is over 1,000 lines, so the value, the band and the grade are identical on all twelve subjects measured here. The movement is at file scope, and it is large: 840 of 3,046 individual files, 27.6 percent, leave a band they were never measured into.

An external adopter found the defect and stated the consequence better than the code did. At per-edit tempo an agent holds one file, and under the floor every file below a thousand lines banded Healthy by construction. L1.15 was therefore useless at file scope, which is the scale this standard is now being built toward.

## What was wrong

`indicators.py:838` read:

```python
density = (escape_count / (total_loc / 1000)) if total_loc > 1000 else 0.0
```

and `type_escapes.rs:137` carried the same rule, ported verbatim.

Two separate claims came out of that one line, and the second is the worse of them.

**Over an empty input it asserted a property it had not tested.** Zero escapes over zero lines is the same 0.0 as zero escapes over a thousand, and the band field, the one a reader actually looks at, cannot tell them apart. This is the shape `vacuity.py` was written to find, and it names L1.15 among its four findings.

**Over a non-empty input it substituted a constant for lines it had already counted correctly.** This is the half that has no defence. The files were read, the tree was parsed, the escapes were counted, and the last step of arithmetic threw the count away and wrote the healthy end of the scale in its place. A refusal over an absent input is honest. A verdict over a present input the tool declined to divide is not.

**The threshold had no derivation.** Not in `03-layer1-indicators.md`, whose bands are `<1 / 1-5 / >5` per kLOC with nothing under them. Not in the calibration note. Not in any of the twelve prior amendments. The canon and the implementation disagreed, and the canon was right, so the divergence is recorded here as an implementation defect rather than settled by inventing a justification after the fact.

## The new rule

**There is no minimum denominator, and the absence of one is the rule.** Escapes are divided by however few production lines there are.

**Zero production lines refuses.** With no line to divide by there is no density, so the indicator returns `value: "n/a"`, `band: "n/a"`, `details: "no production source lines found"`. This is the `_test_to_prod_ratio` precedent four hundred lines up in the same module, and it is consistent with the canon, which already records L1.15 as n/a for a codebase with no statically-typed files.

**The denominator is printed exactly.** `details` moves from `"{n} escapes in ~{k}kLOC"` to `"{n} escapes in {loc} production LOC"`. Rounded to whole thousands the old string read `~0kLOC` for every input the floor used to swallow, so the disclosure that exists to let a reader recompute the ratio hid the only term that moved. A count beside its exact denominator is checkable at any size. This string is the only field that moves on a repository-scale panel, and it is why the frozen golden was touched.

## Why the floor was deleted rather than replaced

Three fixes were on the table. The measurement, not taste, chose between them, and the deciding numbers are below.

### The jumpiness objection is real and describes 3.8 percent of the sample

A rate over a small denominator moves in large steps. One escape in a 200-line file reads 5.03/kLOC and bands Slop, and the next edit can move it by the width of the whole scale. If most small-file Slop bands were that shape, the reading would be noise wearing a verdict.

They are not. Of the 687 files at or under 1,000 lines that now band Slop, **117, or 17.0 percent, are driven by a single escape**. That is 3.8 percent of the 3,046-file sample. The median small Slop file holds **4 escapes in 201 lines**. These are files with a real concentration of escape hatches, not files caught by an unlucky denominator.

The worst readings the floor was publishing as 0.0 and Healthy settle it:

| Reading | Escapes / LOC | File |
|---:|---:|---|
| 235.8/kLOC | 29 / 123 | `newtonsoft/Src/Newtonsoft.Json/Serialization/JsonDynamicContract.cs` |
| 232.1/kLOC | 52 / 224 | `newtonsoft/Src/Newtonsoft.Json/Utilities/FSharpUtils.cs` |
| 224.1/kLOC | 13 / 58 | `declaro/.../abstractions/pragma_compat.py` |
| 220.8/kLOC | 34 / 154 | `newtonsoft/Src/Newtonsoft.Json/Utilities/BoxedPrimitives.cs` |
| 186.7/kLOC | 14 / 75 | `cardz/packages/shared/src/wasm/dispatch_handlers.py` |

A file that is 52 escapes in 224 lines is an escape-hatch file by any reading. Calling it Healthy is not conservatism about small samples. So the answer to "is 5.0/kLOC on a small file wrong, or merely uncomfortable" is: merely uncomfortable, and it is the minority case besides. The variance is a property of a ratio, it is visible in the count and the line total printed beside it, and an instrument that hides its own variance by asserting the healthy end of the scale is worse than one that reports a jumpy figure. A reader can see variance. A reader cannot see a substitution.

### A minimum denominator silences most of the corpus, and no minimum is derivable

Reporting `n/a` below a floor is honest, and it is what this project has done elsewhere this week. It needs a number, and here is what each candidate costs, measured over the 2,976 files the analyzer reads at file scope:

| Minimum | Files reporting n/a | Share |
|---:|---:|---:|
| 100 LOC | 1,336 | 44.9% |
| 200 LOC | 1,930 | 64.9% |
| 300 LOC | 2,271 | 76.3% |
| 500 LOC | 2,600 | 87.4% |
| 1,000 LOC | 2,874 | 96.6% |

Even the smallest candidate silences nearly half the sample, and it damps the variance least. The floor that was there silenced 96.6 percent, which is the adopter's complaint restated as a number. Choosing among these needs a derivation, and inventing one is the failure this project has refused three times already. Refusal over an input the tool successfully read is not the same virtue as refusal over an input it could not read; the first is a second fabrication in the other direction.

### Publishing the count without the density is the same fix wearing a different hat

The count is already published, at every size, before and after this change. What option three actually proposes to remove is the band, and it removes it below some size, which is the underivable minimum again. It also does not work on its own terms: 29 escapes is alarming in a 123-line file and unremarkable in a 5,000-line one, so a bare count cannot band without the denominator the canon defines the bands in terms of.

## What the numbers did

Both passes ran with `PYTHONHASHSEED=0`, from two git worktrees at the same commit, so the only difference between them is this change. A concurrent agent was editing `state_bounds.py` and its neighbours in the live tree throughout, which is why the measurement was taken from worktrees rather than in place.

Because a live working tree is not a reproducible subject, the before-pass was run twice, once on either side of the after-pass. `declaro` moved by one escape between the two, from 1,351 to 1,350, because its working tree was edited by its own author in between. The second before-pass is therefore the comparison, and the first is discarded. That control is what makes the local rows below a comparison rather than two unrelated readings.

### Repository scope: nothing moves

| Repository | Language | Before | After | Band | Grade |
|---|---|---:|---:|---|---|
| google/gson | java | 12.54 | 12.54 | Slop | F, unchanged |
| junit-team/junit4 | java | 14.72 | 14.72 | Slop | F, unchanged |
| JamesNK/Newtonsoft.Json | csharp | 15.22 | 15.22 | Slop | F, unchanged |
| restsharp/RestSharp | csharp | 6.44 | 6.44 | Slop | F, unchanged |
| json-c/json-c | c | n/a | n/a | n/a | F, unchanged |
| libuv/libuv | c | n/a | n/a | n/a | F, unchanged |
| multicardz | python | 1.29 | 1.29 | Not Healthy | F, unchanged |
| buckler/iam | python | 10.28 | 10.28 | Slop | F, unchanged |
| cardz | python | 14.0 | 14.0 | Slop | F, unchanged |
| declaro | python | 19.66 | 19.66 | Slop | F, unchanged |
| umbra | python | 0.41 | 0.41 | Healthy | C, unchanged |
| slop-audit | python | 0.0 | 0.0 | Healthy | A, unchanged |

**Twelve subjects, no value moved, no band moved, no grade moved, and hygiene is identical to three decimal places on every one.** L1.15 carries hygiene weight 3 of 11, the joint-highest, so this was the risk worth measuring, and it did not fire. The smallest subject in the set holds 9,639 production lines. The floor could not reach any of them.

That result is itself the finding. **The defect is invisible at the scale every published figure was taken at, and total at the scale the tool is now being asked to work at.** A parity corpus of six libraries cannot see it, and did not.

### File scope: 840 of 3,046 files move

Each file was measured alone in a tree of its own, which is what an agent holds at per-edit tempo. Sample: every production file of the repository's language, capped at 400 per repository by a fixed-seed draw.

| Repository | Files | Before: H / NH / S / n/a | After: H / NH / S / n/a | Moved |
|---|---:|---|---|---:|
| buckler/iam | 400 | 393 / 2 / 5 / 0 | 169 / 21 / 170 / 40 | 224 (56%) |
| google/gson | 264 | 258 / 2 / 4 / 0 | 115 / 15 / 134 / 0 | 143 (54%) |
| declaro | 317 | 314 / 0 / 3 / 0 | 176 / 15 / 122 / 4 | 138 (44%) |
| junit-team/junit4 | 400 | 398 / 0 / 2 / 0 | 309 / 4 / 87 / 0 | 89 (22%) |
| JamesNK/Newtonsoft.Json | 400 | 385 / 5 / 10 / 0 | 297 / 11 / 92 / 0 | 88 (22%) |
| multicardz | 400 | 394 / 5 / 1 / 0 | 331 / 18 / 34 / 17 | 63 (16%) |
| cardz | 400 | 399 / 0 / 1 / 0 | 340 / 9 / 45 / 6 | 59 (15%) |
| restsharp/RestSharp | 255 | 255 / 0 / 0 / 0 | 224 / 4 / 27 / 0 | 31 (12%) |
| umbra | 97 | 97 / 0 / 0 / 0 | 94 / 0 / 2 / 1 | 3 (3%) |
| slop-audit | 113 | 113 / 0 / 0 / 0 | 111 / 0 / 0 / 2 | 2 (2%) |
| **All** | **3,046** | **3,006 / 14 / 26 / 0** | **2,166 / 97 / 713 / 70** | **840 (28%)** |

Every transition runs in one direction, which is what a removed fabrication looks like:

- Healthy to Slop: 687
- Healthy to Not Healthy: 83
- Healthy to n/a: 70
- unchanged: 2,206

**Before this change the indicator had no discriminating power at file scope at all.** 2,940 of 3,046 files sit under 1,000 lines, and all of them read Healthy whatever they contained. The 40 non-Healthy readings in the whole before-column came from the 106 files over 1,000 lines. RestSharp scored 255 Healthy out of 255 while its repository reading was 6.44/kLOC and Slop, which is a contradiction the panel could not express.

The 70 files that now read n/a are test files, drawn into the sample by extension and then excluded by L1.15's production scope once they stand alone. Held alone, each of them previously reported "0.0 escapes per kLOC, Healthy" over a file the analyzer never opened. They now refuse.

**This repository's two n/a files and umbra's one are the same case, and slop-audit's 111 Healthy readings are all earned.** Its repository reading stays 0.0 and its gate stays clean.

## The red was run first

Four tests were written against the unfixed code. Three failed and the fourth, the control, passed:

```
assert 0.0 == 1000.0     test_l1_15_a_small_file_of_nothing_but_escapes_is_not_healthy
assert 0.0 == 5.03       test_l1_15_one_escape_at_file_scope_is_measured
assert (0.0 == 'n/a')    test_l1_15_no_production_lines_is_na_not_healthy
passed                   test_l1_15_a_clean_small_file_still_reads_healthy
```

The control is the one that matters most. Honest zero is the thing a fix like this can break: a small file the analyzer really read and really found nothing in must keep its Healthy, earned rather than manufactured. It did.

## Regression cover

`tests/test_basic.py`, four tests, the red set above.

`tests/test_read_nothing.py`, one test. That module carried a survey of four empty-denominator claims and a docstring promising that when one of them is fixed, "the fix moves the assertion here and the survey stays true instead of going stale". The survey is now three, and `test_l1_15_no_longer_manufactures_a_band_from_an_empty_denominator` holds the moved assertion. L1.16, L1.17 and `absolute_paths.scan` are unchanged and still listed.

`tests/test_vacuity.py`, one test. This is the evidence that stands independent of the tests written to drive the change. `vacuity.py` finds this shape from the shape alone, without being told where the instances are; it found `_compute_type_escapes`, and it no longer does. The replacement refusal is not a second instance, and the test says why: `total_loc == 0` returns band `n/a`, and a fix that kept publishing a verdict over nothing would still be caught. `vacuity.py`'s own docstring records the transition from four live instances to three.

`type_escapes.rs`, four tests, the same four cases. They reach `analyze`, which does I/O, through a one-file tree under the system temp directory rather than through a new dev-dependency: adding a crate to the lockfile of a binary whose whole claim is portability would cost more than the test is worth.

## The golden moved on one field, deliberately

`tests/golden/py_repo.json` changed one string:

```
- "details": "0 escapes in ~0kLOC",
+ "details": "0 escapes in 28 production LOC",
```

The fixture is 28 lines with no escapes. Its value stays 0.0 and its band stays Healthy, so this is the disclosure change and nothing else. It was hand-edited rather than recaptured, because a concurrent agent was changing L1.18 in the same tree and a recapture would have absorbed that work into this amendment's evidence.

## The port

Both sides carried one rule, so they had to lose it together. `tools/slop-audit-rs/src/indicators/type_escapes.rs` takes the identical change, including the exact-denominator string, because the parity differ compares `details` verbatim.

`uv run --no-project python validate_corpus.py` reports **16/16 compared indicators equal on all six pinned repositories**. `cargo test` passes 30 of 30.

## Note for Paper A

**No published repository figure is affected, and that is a stronger claim than it sounds.** Every subject in the pinned corpus and every local tree exceeds the floor by an order of magnitude, so no L1.15 number taken with the pre-fix analyzer at repository scope is wrong. Unlike the L1.18 corrections recorded the same day, this one needs no v1-versus-v2 re-run.

**Any L1.15 figure taken at file or module scope with the pre-fix analyzer is worthless.** It reads Healthy by construction below a thousand lines and carries no information. There is no such published figure that I found, but the tool would have produced one on request, and 96.6 percent of the files in a 3,046-file sample would have been affected.

**The band thresholds are unchanged and remain uncalibrated at file scope.** `<1 / 1-5 / >5` per kLOC was seeded from industry tool defaults and GitClear 2024 against whole repositories. Nothing in the calibration note claims those boundaries survive the change of scale, and this amendment does not claim it either. What the fix establishes is that the tool now reports the ratio it says it reports. Whether 5/kLOC is the right Slop boundary for a 200-line file is a calibration question, and it is open.

## Reported, not fixed

**L1.16, L1.17 and `absolute_paths.scan` still carry the empty-denominator half of this defect.** All three divide by a count that can be zero and substitute 0.0, and `vacuity.py` still finds all three. None of them carries the worse half, the constant over a non-empty input, so none is as urgent. They are listed in `test_read_nothing.py` and they were left alone here to keep this change contained to one indicator.

**The band thresholds were not recalibrated for file scope.** See the note above. Doing it needs a file-scope corpus and a rework or defect signal to correlate against, neither of which exists yet.

**The sample is capped at 400 files per repository and covers three languages.** Java, C# and Python. TypeScript, Go, Kotlin and Swift are typed languages with escape tokens in `LANG_CFG` and no repository in the corpus, so the file-scope distribution above is not measured for them. The direction of the fix cannot differ by language, because the change is one line of arithmetic applied after the language-specific counting, but the magnitude can.

**The `~kLOC` string appeared in one frozen golden and nowhere else that I could find.** I grepped the tools tree for `kLOC` and found the two emitters, this amendment's predecessors, and the golden. If a downstream consumer parses that string, this change breaks it, and the count is still the first token either way.
