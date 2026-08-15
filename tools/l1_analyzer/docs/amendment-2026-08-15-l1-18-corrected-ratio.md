# Amendment 2026-08-15: four corrections to L1.18, and the boundary exclusion is withdrawn

Corrects L1.18 in place. Four defects, all verified on this machine on 2026-08-15 rather than taken from a report, and all four fixed in one change because three of them are the same defect wearing different clothes: a rule written for one language and applied to nine.

This is the amendment `amendment-2026-08-01-l1-18-module-global.md` said would be needed. That one migrated Python to a structural scan and closed with "the eight other languages keep the legacy text heuristic ... should be migrated to field-based extraction per language, with per-grammar validation, in a later amendment." This is that amendment for Java and C#, and it fixes the shared keyword table the other six inherited.

## What was wrong

### 1. The I/O boundary exclusion never fired

The canon row for L1.18 promised to exclude "I/O boundary functions (route handlers, database adapters, CLI entry points) which are expected to interact with external state by design." What was implemented, at `mutable_state.py:213`, was `_BOUNDARY_MARKER = "honest: boundary"`: a comment a function had to carry. No repository that has not adopted this project's private marker was affected, which is every repository ever audited. The exclusion was documented, implemented, and inert, and the canon's promise was therefore a claim the instrument did not keep.

### 2. The immutability vocabulary was shared, so it matched no language

`mutable_state.py:145` read `const_keywords` through a default of `("const ", "final ", "readonly ", "let ", "val ")` — a union of five languages' keywords that no single language uses. Only javascript and go overrode it. (A proposal document reviewed alongside this work claimed ruby also overrode it; it did not, and the count of overriding languages is two.)

TypeScript therefore inherited a list containing `let `, and a module-level `let counter = 0` was classified immutable because its line contains the word:

```
let counter = 0;                     // .ts  -> immutable, function scores 0%
export function bump(): number { counter += 1; return counter; }

let counter = 0;                     // .js  -> mutable state, function scores 100%
export function bump() { counter += 1; return counter; }
```

Two files differing only in extension, two answers. C inherited the same table and would have honoured `let `, `val `, `final ` and `readonly `, none of which are C.

The shape that permitted this is the shared default itself. It is silent, it reads like a sensible fallback, and it is wrong one language at a time. TypeScript and C reached the text scan by *falling through* an `if/elif` chain on config flags, not by anyone choosing it for them, and they inherited its keyword table with it.

### 3. Java and C# fields were unreachable, twice over

`_find_module_mutable_names` collected candidates from root children and one level below. A Java or C# field sits at root, class declaration, class body, field declaration — one level deeper than the scan ever looked. No field entered the candidate set.

Even at the right depth the text heuristic required an `=` on the line, so `private int total;` was invisible regardless.

And `mutable_state.py:169` counted member access only when the node's text began with a receiver name, so only explicit `this.total` was seen. Bare `total`, which is the idiomatic form in both languages, was not.

Between them, L1.18 measured **how often Java and C# authors write `this.`**, which is a style preference. The measured consequence: JamesNK/Newtonsoft.Json scored 0.0% — 0 of 2,670 functions — a codebase in which the indicator detected literally nothing.

### 4. The ratio was not bound-aware

L1.18 counted a reference to outside state whether or not that state could take unboundedly many values. A read keyed by a literal against a closed set is finite and exhaustively testable; an unbounded lookup is not. The finite-testability classifier printed on the same panel already drew that distinction, per state, and the ratio beside it ignored it.

The golden fixture in `tests/test_state_bounds.py` had said so in its own comments since it was written: `self.enabled` is annotated "bounded state (bool)" and `len(self.cache)` "bounded PROJECTION of an unbounded dict". The ratio counted both.

## The new rules

**A function's references to external state count when, and only when, the finite-testability classifier could not bound the state they reach.** Bounded means all three of: the classifier's verdict is `neutral`, the state drives a decision, and its partition is counted. All three are needed. `neutral` is *also* what the classifier returns for state that reaches no decision at all — an accumulator written and returned but never branched on — and its partition is then `EMPTY`, meaning "nothing to cover", not "finitely many classes". Reading `neutral` alone as bounded cancelled correction 3 exactly where it was needed, because a plain field accumulator is precisely that shape. The verdict is the classifier's, taken verbatim; this module invents no second boundedness rule, because two rules for one concept drift and the ratio would then contradict the classifier printed beside it.

**Every language declares its own module scan and its own immutability keywords.** `LANG_CFG` gains `module_scan`, one of `python_fields`, `mutable_specifier`, `class_fields` or `text`, dispatched through a table rather than a fall-through chain. `const_keywords` is read by direct subscript with no default, so a language that omits it raises instead of inheriting a neighbour's grammar. TypeScript, JavaScript, Go and C declare `("const ",)`; Ruby declares `()`, because Ruby has no immutability keyword and spells a constant in capitals, which the scan already honours.

**In Java and C#, mutable state is every field not declared `final`, `readonly` or `const`.** Fields are found by a walk to any depth restricted to `field_declaration` nodes only. The restriction is what keeps method locals out: both languages list a local declaration type in `module_level_assign`, and a deep walk over *that* vocabulary would count every local as external state, an error worse than the one being fixed. Names come from the `variable_declarator`s, so `int a = 1, b;` binds two and an uninitialised field binds one. Mutability is read from the declared modifiers rather than guessed from the name's casing, because both languages have a keyword for the property and it is already in the source. Bare field access is then counted by the identifier arm of `_count_mutable_refs`, which is the other half of this correction.

**There is no I/O boundary exclusion.** The claim is withdrawn from the canon rather than reimplemented, and the marker is deleted with it. See the next section.

## Why the boundary exclusion is withdrawn rather than fixed

Whether it could be done by analysis was the open question, and it was investigated before anything was written. It cannot, and the evidence is four independent failures rather than one.

Measured across seven local trees (5,210 files, 77,576 function definitions) and the six pinned corpus repositories:

**A route-handler list cannot be written.** Python functions in these trees carry 250 distinct decorator spellings, 88 of them first-party. Seventeen are route-handler-ish; they cover **7.2%** of production functions locally and **0%** of the corpus, which holds six libraries and no web application. The match keys are variable names the developer invents: `router.get`, `app.get`, `test_app.get` and `_app.get` all appear, and no framework dictates any of them. Suffix matching collides immediately, because `.patch` catches `@router.patch` and `@mock.patch` alike. Java shows 65 distinct method annotations across two repositories, C# at least 214.

**"Database adapter" has no syntactic signature at all.** One measured module holds roughly 53 adapter functions and 6 pure ones, in one file, in one style, with no decorator and no marker separating them. Its I/O verbs are `find_one`, `find_many`, `create` and `update_one` — one in-house ORM's vocabulary, present in no public registry.

**"CLI entry point" had no marker whatsoever.** Zero `@click.command` and zero `@app.command` across all seven trees. Every CLI is `argparse` behind an undecorated `main()` reached from an `if __name__ == "__main__"` guard; multicardz alone has 84 such guards.

**The framework-agnostic alternative fails in both directions.** A rule of the form "the function calls an I/O primitive" matched 3,309 of 9,326 production functions (35.5%) in its loose form, and a hand-read 20-function sample gave **9 false positives, 45%**: `.get` on a dict is indistinguishable from an HTTP GET, and a single `logger.info` flags an otherwise pure delegation. It also reads `OP_DEPENDENCY_HANDLERS.get(op_type)` — dict-lookup polymorphism, this project's own recommended pattern — as an I/O call. Tightening the rule to `execute`, `cursor`, `commit`, `acquire`, `open`, `subprocess`, `socket` and `os.environ` drops matches to 11.6% and improves precision, at which point it matches **0 of the 53 adapters** in the module whose entire job is database access.

Roughly **20 distinct web, ORM, HTTP and CLI frameworks** are in use across seven repositories belonging to one person, one of them written in-house. An enumeration that misses one moves a repository's score by an amount decided by which framework its authors chose, which is not a measurement.

**The marker was deleted along with the claim, and that is a judgment call worth stating.** Keeping author declaration as the sole surviving form was the alternative. It was rejected because an exclusion a subject opts into is a lever a subject controls, this indicator's primary consumer is an AI that optimises exactly what it is told to optimise, and the scope rule in `scope.py` already carries a written warning about precisely this failure. A marker that excludes a function from a published ratio is a free score reduction for anyone who reads the source.

**The consequence is disclosed rather than hidden: L1.18 is inflated by the whole I/O layer of every codebase it measures, and always was.** Nothing about the numbers changes on this axis — the exclusion never fired — but the canon now says what the instrument does instead of what it intended.

## What the numbers did

Both passes run back to back with `PYTHONHASHSEED=0`, the corpus at its pinned commits. Because a live working tree is not a reproducible subject, the after-pass was run twice, once on either side of the before-pass, and the two after-passes were byte-identical; that control is what makes the local rows below a comparison rather than two unrelated readings.

| Repository | Language | Before | After | Δ | Before | After | Band |
|---|---|---:|---:|---:|---:|---:|---|
| google/gson | java | 4.3 | 17.0 | **+12.7** | 49/1140 | 194/1140 | **Healthy → Not Healthy** |
| junit-team/junit4 | java | 0.6 | 8.8 | **+8.2** | 10/1542 | 136/1542 | Healthy |
| JamesNK/Newtonsoft.Json | csharp | 0.0 | 10.1 | **+10.1** | 0/2670 | 269/2670 | Healthy |
| restsharp/RestSharp | csharp | 0.7 | 2.6 | +1.9 | 3/431 | 11/431 | Healthy |
| json-c/json-c | c | 4.6 | 1.7 | −2.9 | 11/241 | 4/241 | Healthy |
| libuv/libuv | c | 6.2 | 5.5 | −0.7 | 96/1551 | 85/1551 | Healthy |
| multicardz | python | 14.7 | 10.8 | −3.9 | 1314/8958 | 969/8958 | Healthy |
| buckler/iam | python | 61.3 | 59.9 | −1.4 | 1472/2402 | 1439/2402 | Slop |
| cardz | python | 39.2 | 38.5 | −0.7 | 352/898 | 346/898 | Not Healthy |
| buckler/idd | python | 17.8 | 17.2 | −0.6 | 275/1549 | 267/1549 | Not Healthy |
| declaro | python | 24.1 | 19.2 | −4.9 | 521/2163 | 416/2163 | Not Healthy |
| umbra | python | 0.5 | 0.5 | 0.0 | 5/1001 | 5/1001 | Healthy |
| slop-audit | python | 0.0 | 0.0 | 0.0 | 0/531 | 0/541 | Healthy |

Forced-language supplement, because the corpus contains two Java, two C# and two C repositories and nothing else:

| Tree | Language | Before | After | Δ | Before | After |
|---|---|---:|---:|---:|---:|---:|
| genX | typescript | 23.6 | 25.3 | +1.7 | 53/225 | 57/225 |
| multicardz | javascript | 24.1 | 23.0 | −1.1 | 1975/8202 | 1887/8202 |
| buckler/idd | javascript | 2.6 | 2.4 | −0.2 | 32/1227 | 30/1227 |
| cardz, genX | javascript | 4.2, 4.8 | 4.2, 4.8 | 0.0 | unchanged | unchanged |
| umbra | rust, go | 0.0 | 0.0 | 0.0 | 0/15, 0/7 | unchanged |

**Across 20 readings: 5 up, 9 down, 6 flat. Median 0.0, mean +0.9, range −4.9 to +12.7. One band moved, gson from Healthy to Not Healthy.**

**The direction is a property of the language, not of the codebase.** Java (+8.2, +12.7) and C# (+1.9, +10.1) rise because correction 3 makes state visible that was not visible at all. Python (median −0.7) and C (median −1.8) fall because correction 4 removes bounded state and neither language had an invisible-field defect for the other corrections to fix — Python's scan was already structural and already correct after the 2026-08-01 amendment. TypeScript rises (+1.7) on correction 2 alone. Anyone reading a before-and-after series without knowing the language will read a Java repository as having got worse and a Python repository as having got better, and neither happened.

The slop-audit row is the boundary withdrawal in miniature: the numerator stays 0, and the denominator rises from 531 to 541 because ten functions in the analyzer's own source carried the `honest: boundary` marker and were being removed from both counts. The analyzer remains self-clean on its own L1.18.

## The golden was recaptured, deliberately

`tests/golden/py_repo.json` moved on exactly one indicator, and both moved fields are L1.18's:

```
- "details": "5/6 functions reference external mutable state (python)",  "value": 83.3
+ "details": "3/6 functions reference unbounded external mutable state (python)",  "value": 50.0
```

The band did not change (both are Slop). No other indicator moved a byte, which is the evidence that this change is contained: L1.12, L1.14, L1.15, L1.16, L1.17, L1.19 and L1.20 are all identical in the recaptured file.

The two functions that dropped out are `reads_flag` and `uses_global`. `self.enabled` is a bool the fixture's own comment calls "bounded state (bool)", and `counter_state` is a module int bound once to `0` and never reassigned, which is a one-class partition and a constant in fact whatever its casing suggests. `cache_is_empty` still counts, because `self.cache` is read with a variable key elsewhere in the file and the classifier's verdict is per state key, not per reference — the conservative direction.

## L1.18b did not move

`state_bounds._enum_module_state` calls `_find_module_mutable_names`, so the coupling had to be checked rather than assumed. It calls it **only when `module_enum == "python"`**; Java, C#, TypeScript, JavaScript, Go, Rust and C each enumerate their own module state inside `state_bounds`. The Python path is `_module_mutables_python`, which this amendment does not touch. The whole L1.18b test suite passes unchanged, and the recaptured golden confirms it at the panel level.

## Regression cover

`tests/test_mutable_state_corrections.py`, 17 tests, at least two per defect. All were run against the unfixed code first, where 9 of them failed, so they measure the fix and not the fixture:

- the boundary marker no longer excludes a function, and no longer changes the denominator of the functions around it;
- a TypeScript module-level `let` is mutable state, a `const` is not, and the `.ts` and `.js` readings of the same construct are equal;
- Java and C# bare field access is counted; an uninitialised field is still state; `final`, `readonly` and `const` fields are not; and a method local is not harvested as a field;
- a literal-keyed read against a closed set is not counted, an unbounded key still is, and state that drives no decision is not mistaken for bounded state;
- every LANG_CFG entry declares a `module_scan`, and every text-scanned language declares its own `const_keywords`.

One test pins an interaction that surprises on first reading: a Java field that only ever meets a literal comparison (`if (total > 0)`) is seen by correction 3 and then excluded by correction 4, because a two-class partition is exhaustively testable. It is pinned so that changing it requires arguing with the classifier rather than quietly writing a second boundedness rule.

Two existing tests changed, and both were wrong before rather than made wrong by this:

- `test_l1_18_counts_mutable_module_global_but_not_constant` claimed in its comment that `counter` was "lowercase, reassigned" and never reassigned it. It passed on the strength of the name's casing rather than the mutation it was written to demonstrate. The fixture now reassigns, and the assertion is unchanged at 1/3.
- `test_l1_18_declared_boundary_is_excluded` is now `test_l1_18_has_no_boundary_exclusion_a_subject_can_claim`, and asserts the opposite: both functions count, marker or no marker.

## The port

`tools/slop-audit-rs` does not implement L1.18 — it declares `Coverage::NotPorted` and prints the reason — so nothing in the binary moved. Corpus parity re-run at 16/16 on all six repositories, with L1.18 reported as a GAP line as before. When L1.18 is ported, the classifier it now consults must be ported with it, or the ported ratio will read high by the whole bounded-state correction.

## Note for Paper A

**Every L1.18 figure taken with the pre-fix analyzer is affected, and the correction's sign depends on the language.** Java and C# figures are understated by a large margin — Newtonsoft.Json read 0.0% for a 2,670-function codebase — and Python and C figures are overstated by a smaller one. This is a defect correction, not a redefinition, but it is the largest single movement in L1.18 since it was written and it moved a band on one corpus repository. It belongs in the v1-versus-v2 side-by-side re-run per the finite-testability supersession rule, and the C# figures are affected on top of the movement already recorded in `amendment-2026-08-14-csharp-test-scope.md`.

The canon row's I/O-boundary sentence is withdrawn in the same change. Any published statement that L1.18 excludes route handlers, database adapters or CLI entry points was never true of the implementation and should be corrected wherever it appears.

## Reported, not fixed

**Go cannot use the bound-awareness correction.** The classifier keys Go state as `<Type>.<field>` while the ratio's reference walk sees `<receiver>.<field>`, so no Go reference is ever matched as bounded and Go keeps its uncorrected reading on that axis. It errs high, never falsely clean. Fixing it means teaching the walk the receiver's type, which is a resolution step the ratio does not currently do.

**A local variable shadowing a Java or C# field is counted as field access.** The reference walk matches bare identifiers by name, which is what makes bare field access reachable at all; a method-local `total` in a class that also declares a field `total` therefore counts. It errs high. Fixing it means scope resolution inside the method body.

**The measurement's language coverage is thin outside Java, C#, C and Python.** The pinned corpus has no TypeScript, Go, Ruby or Rust repository. The TypeScript correction — the defect that started this — is measured on one tree of 225 functions, and Go and Rust on trees of 7 and 15 functions. Ruby is not measured at all. Calibrating L1.18's 15/40 bands against the corrected number needs a corpus with those four languages in it first.

**Ruby, Go, C, JavaScript and TypeScript still use the text heuristic.** They now use it with their own keywords rather than a shared table, which is the defect this amendment closes, but a text scan over source lines remains the weakest of the four strategies. Migrating each to a structural scan is the continuation of the 2026-08-01 amendment's plan and is not done here.
