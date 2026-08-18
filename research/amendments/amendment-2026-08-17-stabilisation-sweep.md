# Amendment 2026-08-17: nine blind spots closed, and every published number they touched

## What this covers

28 commits on `restructure/spec-research-tools-split`, `8b10367..1190568`. They close nine defects in which the analyzer published a value it had not earned, and each one moves numbers the instrument has already reported. The instrument is cited as Zenodo DOI 10.5281/zenodo.20385346, so no figure from a run before `1190568` should be quoted without checking it against this document.

One amendment rather than nine, deliberately. Each fix moved the corpus, and writing an amendment per fix produces a stream of amendments that each need amending.

## What is verified here, and what is not

Every before/after in the reproductions below was run by hand on this machine and is quoted from real output.

**The corpus figures are not.** The six pinned corpus repositories are not checked out on this machine, so the effect on libuv, json-c, gson, junit4, Newtonsoft.Json and RestSharp has not been measured. During the work an agent reported libuv moving from 6.1 Healthy to 50.7 Slop and json-c from 1.7 Healthy to 34.9 Not Healthy on L1.18. Those two figures are plausible and consistent with the mechanism, and they are **unverified**: treat them as an indication of scale and not as a result. A corpus re-run is owed before any C figure is published again.

## The nine, and what each one moves

### 1. C could not reach a struct field through a pointer

`_count_mutable_refs` hard-coded `.` as the member operator, and `_receiver_names` returned an empty set for any language with no `this` keyword and no Go method receiver. C spells the reach `s->cache` and has neither, so the member-access arm could not fire on any C repository ever audited.

```c
struct Store { int cache[256]; };
void put(struct Store *s, int k, int v) { s->cache[k] = v; }
int get(int k) { return cache[k]; }
```

| | before | after |
|---|---|---|
| L1.18 | 0.0, Healthy, 0/2 functions | **50.0, Slop, 1/2 functions** |

Moves: every C repository's L1.18, upward. `member_op` and `receiver_scan` are now declared per language and dispatched through a table read by subscript, so a language that names no scan raises rather than reaching the empty set by omission.

### 2. C file-scope declarations needed an equals sign to exist

C reached the text heuristic by the same omission, and that heuristic requires `=` on the line. `static int cache[256];` therefore declared no state at all.

On the fixture in `tests/test_module_globals.py` the text scan found `counter` and missed `cache`, `buf`, `NAME` and `MAX`; the classifier enumerated all five. Two measures of one file disagreeing about what is even a candidate is the defect; the array was the instance.

| | before | after |
|---|---|---|
| L1.18 on a file whose only state is `static int cache[256]` | 0.0, Healthy | **100.0, Slop** |

Moves: every C repository's L1.18, upward, and independently of item 1.

### 3. Four measures banded an empty denominator as clean

L1.16, L1.17 and L1.18 substituted `0.0` for an undefined ratio and banded it Healthy; `absolute_paths` returned "no hardcoded machine-specific absolute paths" over zero files read. A reader could not tell read-and-clean from not-looked-at, and the failure ran the wrong way round: the less the analyzer read, the cleaner the verdict.

| on a repository with no production files | before | after |
|---|---|---|
| L1.16 trailing whitespace | 0.0%, Clean | **n/a, No data** |
| L1.17 god-file concentration | 0.0%, Clean | **n/a, No data** |
| absolute paths | clean | **refuses, naming the extensions searched** |

Moves: every small, empty or unrecognised-language repository. A Clean becomes an n/a. `incomplete.py` is the mechanism: a measure raises rather than deciding what to do about its own ignorance, and one boundary, `indicators._measure`, turns the refusal into n/a with the basis printed.

### 4. Zero state read was published as "100% finitely testable"

The sharpest of the nine. A fourteen-line Ruby file whose entire state is an unbounded `@@cache` keyed by an arbitrary argument and an unbounded `$seen`:

> **Grade: C** — 100% of its state is finitely testable
> This code definitely CAN be exhaustively tested.
> Finitely testable: 0 / Provably unbounded: 0 / Undecided by the analyzer (silence): 0

Three lines below, the card asserted that "hiding state from the analyzer buys no letter". The letter was bought by exactly that. The letter tracks hygiene and so varies; the constant is the 100% and the CAN sentence.

Every guard against this was bypassed rather than absent. The silence floor divides by the recognised set, so zero recognised gives fraction 0.0 and the above-half rule never trips. The census refusal required `declared > 0`, so counting nothing disabled it. `judged_fraction` was computed, published as null, and read by nothing.

| | before | after |
|---|---|---|
| the same repository | Grade C, 100% finitely testable | **exit 2, INCOMPLETE CODE, no grade** |

Moves: any repository whose state the classifier does not recognise. A grade becomes a refusal.

### 5. The census refusal could not fire

`state_census.CAPABILITY` marked all nineteen language/kind pairs admitted, so `reachable` always equalled `declared` and `census_unread` could never return True. The whole disclosure chain hanging off it was dead in production: `report.census_unread`, `card._census_note`, the "Insufficient basis" wording.

Re-measuring all nineteen pairs at site granularity found them genuinely admitted, so the values were not wrong; the granularity was. Capability was recorded per language and kind against one fixture, while readability varies site by site. The refusal now runs on `visited`, the classifier's own per-site record on the repository being audited.

A Rust struct field no method in the file touches now reads declared 1, visited 0, and the card prints "Insufficient basis. No grade, and no claim either way", names the construct, and offers to learn it.

Moves: any repository with declarations the classifier's walk never visits. A grade becomes a refusal. Across the six pinned corpus repositories and ten local trees, `visited` reached zero on none, so no repository that used to grade is expected to be refused.

### 6. `_flow` had no row for a call in a decorator

`@app.get("/")` is the whole of what the honest-framework reference server does with `app`, and no row read it, so the reference server came back unresolved on its own route table. The call-target row already excluded `app.get(p)(handler)` and its comment called that "the decorator idiom in call form", but excluding a shape from one row is not handling it, and both forms fell to the total row.

| | before | after |
|---|---|---|
| `app` in a FastAPI-style module | unresolved, `call in decorator` | **neutral** |

Moves: every Python repository using route decorators, and the equivalent in JavaScript, TypeScript, Java, C# and Rust. Silence falls and verdicts may change with it. `decorator_types` is declared per language, probed against each grammar rather than assumed, because the node name collides: `attribute` means member access in Python and a decorator in C# and Rust.

### 7. Python declared no keyed-read methods

`keyed_read` was an empty frozenset for Python while JavaScript and TypeScript both declared `get` and `has`. `dict.get(k)` is the same keyed read as `Map.get(k)`, so `self._h.get(k, 0)` fell through to "the method result flows on" and the walk then met an assignment it had no row for. A stored-value row was added with it, read through `assign_right`, a field every language had declared and nothing had ever read.

Moves: Python repositories using `dict.get`. Previously unresolved sites now resolve.

### 8. The accumulator rule ran in one language of nine

`state_bounds_filters` opened with `_PY = LANG_SPEC["python"]` and was gated at the call site, so seven languages reported `promiscuous` on a per-key tally that Python correctly cleared: `if k not in hits: hits[k] = 0` then `hits[k] += 1`, where every reference is a write and nothing reads the count back out.

| the same shape | before | after |
|---|---|---|
| Python | neutral | neutral |
| C#, Go, Java, JavaScript, Ruby, Rust, TypeScript | **promiscuous** | **neutral** |

Verified independently on a Ruby tally outside the suite: `@hits` reads neutral where it read promiscuous. Moves: seven languages, downward. Promiscuous counts fall and verdicts may improve.

C reaches the rule and declines, which is correct rather than a gap: it declares no membership operator and no presence method, so the gated shape cannot be written in it.

## What did not move a number

Fifteen of sixteen `_REACHABLE_AFTER` jump-target rows never fired. Instrumented over 717 files and 9,019 terminator blocks: 36 `case_clause`s reached, zero fires. Only C spells a switch body with the node it uses for every other block, which is why C's row was the one that ever worked. Deleting the fifteen changed no reading, because they could not produce one. L1.12 on this repository reads 0.19% either way.

The gate ratchet and the secret scanner changed behaviour without changing a published L1 number. The gate told adopters on a C repository to lower their thread-safety baseline to zero on a reading that never happened, and now says the surface was not measured. `secret_scan` compared a regex character offset against tree-sitter byte offsets, so a credential under non-ASCII text was dropped silently; L1.14 counts may rise on any file carrying an accented comment above a credential.

## What is still owed

A corpus re-run, and it is the reason this document cannot close the question. Six pinned repositories and the supplementary local trees need one pass at `1190568`, and the resulting table belongs beside this one.

`slop-audit-c7r` was open and unfixed when this document was first written, and was fixed the same day in `1190568`. It belongs with the eight above and is recorded here as the ninth. `_compute_decision_space` used one shared node-type set holding the bare strings `"if"`, `"case"` and `"when"`, and walked unnamed children, so in most grammars the keyword token inside an already-matched node matched again: a single Python `if` counted 2. In the other direction Ruby's `unless`, `elsif` and ternary went unseen, and a C switch with a case and a default counted 2 where a reader would say 3. The errors ran opposite ways and did not cancel.

One shared set could not work, which is why it survived: Ruby's `if`, `unless`, `case` and `when` are named node types while Python's `if` is an unnamed keyword token. The table is now declared per language, probed against each grammar, and read by subscript, and the walk reads named children only. The rule the figure means is written beside the table: an `if`, `elsif`, `unless` or ternary counts one each, an `else` counts nothing because it is the other path of an `if` that already counted, and each arm of a switch or match counts one while the container counts nothing.

| | before | after |
|---|---|---|
| this repository's Python scope, 53 files | 3042 | **1499** |

Moves: every L1.19 static figure in every language, and by roughly half on the one repository measured. The README carried 2017 from an older 37-file snapshot and now carries 1499 with a dated note. One residual is named rather than hidden: Ruby spells a `case`'s `else` with the same node type as an `if`'s `else`, so no flat set separates them and a Ruby `case` enumerates its `when` arms only, where the other seven grammars also count their default.

`slop-audit-uef` is open: the validation protocol has never been run, and `validation/` holds a protocol and no results. Both controls exist and are named there. Running it against `1190568` is the next thing, and its results and this amendment belong to one stable pass.

## Four more, per language: the node that writes its own operand, and two Rust regions nobody could read

Added after the nine above, same day, against `slop-audit-3e5` (Go), `slop-audit-3q6` (C#), `slop-audit-4j8` (Ruby) and `slop-audit-0ha` (Rust). Every before/after below was run by hand on this machine and is quoted from real output. No figure on this repository's own package moves: it is Python, and every table row added here is empty for Python.

### 10. Four grammars spell a read-modify-write, and none of them spells it as an assignment

`n++`, `++n`, `c.n++` and `@xs << x` are one runtime step in four notations, and not one of them involves an assignment node, so `assign_types` could never reach any of them. The classifier had no row for the shape at all, which is why the same defect was open in four languages under four different bead numbers. The table now carries one row per grammar, `write_in_place_ops`, mapping node type to the operator tokens that make it a write; the operator is checked and not only the node type, because C# spells the null-forgiving `x!` with the same node as `x++` and Ruby spells every binary operator with the same node as `<<`.

| the counter or append | before | after |
|---|---|---|
| C# `hits++;` | unresolved, `identifier in postfix_unary_expression` | **neutral, observe-only** |
| Java `hits++;` | unresolved, `identifier in update_expression` | **neutral, observe-only** |
| JavaScript / TypeScript `this.n++;` | unresolved, `member_expression in update_expression` | **neutral, observe-only** |
| C `n++;` | unresolved, `identifier in update_expression` | **neutral, observe-only** |
| Go `c.n++` | unresolved, `selector_expression in inc_statement` | **neutral, observe-only** |
| C# / Java `if (hits++ > 3)` | unresolved | **neutral, drives a decision** |
| Ruby `@rows << x if x` | unresolved, `binary in unless_modifier` | **neutral, observe-only** |
| Ruby `@seen << x unless @seen.include?(x)` | unresolved | **promiscuous**, which is what `@seen.push(x)` already read |

The last row is the point of the Ruby half. `_RUBY_MUTATING` carried the string `"<<"` and was matched against method names, and Ruby parses an append as a `binary` node, so only the rare `@xs.<<(x)` spelling could ever match. Two spellings of one operation reported two different verdicts and neither of them was "write".

Moves: six languages. Unresolved counts fall and the silence index falls with them; a tally whose count is read back becomes promiscuous where it was silent. One trade is named rather than hidden: Ruby's `<<` is an append on an Array or a String and a left shift on an Integer, and no static reading separates them, so an integer shift stored in an instance variable now reads as a write. The two spellings agreeing is worth more than the rare shift, and it is recorded here so a reader can disagree.

The row is read twice, and the order is the rule. An in-place write is transparent on the way up, so `if (hits++ > 3)` still reaches the comparison; only when every other row has declined does the node read as a write and nothing more.

### 11. Go's commonest store, its only loop, and its channel receive

Three readings, one language, all verified by parsing on 2026-08-17.

| | before | after |
|---|---|---|
| `m := c.store` | unresolved, `expression_list in short_var_declaration` | **neutral, observe-only** |
| `for p.running { }` | unresolved, `selector_expression in for_statement` | **neutral, drives a decision** |
| `for i := 0; g.live; i++ { }` | unresolved, `selector_expression in for_clause` | **neutral, drives a decision** |
| `return <-w.jobs` | **neutral, observe-only** | **unresolved**, `selector_expression in unary_expression` |

`:=` is the commonest store in Go and `short_var_declaration` was in no assign key. Go's only loop is `for`, and it holds its condition three ways: a bare first named child, a `for_clause` that names a `condition` field, or nothing at all. `branch_cond` reads a field, so it found nothing in the first form however the node type was declared, and `for_clause` was named nowhere. Both are declared now, the positional form through `bare_cond_types` with the child types that are never a condition, so `for { }` and `for k := range m { }` do not read their bodies as tests.

The last row runs the other way and is the one worth reading twice. `<-ch` is a `unary_expression`, exactly as `-x` is, and `unary_expression` is on Go's transparent-wrapper list, so a channel receive walked through as if the channel itself flowed on and the field came back clean. It does not flow on: the receive consumes an element. `opaque_unary_ops` names the operator, the wrapper row declines, and the reading stops and says so.

Moves: Go, in both directions. Three unresolved readings become decided; every consuming channel receive becomes an unresolved that used to be a clean observe-only.

### 12. Rust: every reference inside a macro was invisible, and a mutable borrow was a write nobody could see

`macro_invocation` swallows its arguments into an unparsed `token_tree`. `format!("{}", self.v.len())` holds no `field_expression` and no `call_expression`, and the flat token sequence does not even keep the field name attached to `self`, so a reference walk finds nothing there. A state used only inside macros read as state nothing touches.

| | before | after |
|---|---|---|
| `self.v` written once, then `format!("{}", self.v.len())` | **neutral, observe-only** | **unresolved**, reason `unparsed_region` |
| `let r = &mut self.v; r.push(1);` | unresolved, `unmodeled_construct` | unresolved, reason **`mutable_alias`** |
| `helper(&mut self.v)` | unresolved, `unmodeled_callee` | unresolved, reason **`mutable_alias`** |

The first row fails closed rather than descending into the tokens by text, because an invisible reference reported as an absence is the exact failure this instrument exists to name. What is refused is a state whose own bare name appears among the tokens; `println!("tick")` beside a field called `n` refuses nothing. The match is by bare name and therefore over-refuses - a local called `v` inside a macro refuses a field called `v` - which is the direction to be wrong in when the alternative is clearing a state on a reading that skipped part of it. The check is the last word on a finding, after the false-positive filters, so no rule can clear a state back on a reading that was incomplete.

The second and third rows change no verdict and change what the reader is told, which is the whole value of the silence index. `&mut self.v` hands the field out under a name the walk cannot follow, so `let r = &mut self.v; r.push(1);` writes it through a local with no relation to it and every rule that argues from where the field's own references sit is unsound from that line on. Reporting it as `unmodeled_construct` sends a reader to write a dispatch row; reporting it as `mutable_alias` says the reading has a limit. `&self.v` stays the transparent wrapper it was: a shared borrow cannot be written through, and only the `mutable_specifier` child separates the two.

Two silence reasons are added, `unparsed_region` and `mutable_alias`, so every consumer of `silence.by_reason` sees two more keys, both zero on a repository that trips neither.

Moves: Rust. A macro-heavy repository's silence index rises, which is a statement about the reading and not about the code.

### What was already fixed, and what is still open

C#'s subscript key was reported as a defect and was not one: `sub_key` already descends the `bracketed_argument_list` to the `argument` and out to the key, and `tests/test_state_bounds_filters_cross_language.py` has held that since the reading was written. A literal-keyed C# subscript reads neutral and an open-keyed one reads promiscuous, verified again here. Go's `branch_types` was likewise already carrying `for_statement` rather than the `while_statement` the bead recorded.

Six readings were found by this sweep and are not fixed:

- **Go `delete(d, k)`** puts the container in an argument slot of a builtin that is not on `extra_bounded`, so the plainest key removal in the language reads unresolved with reason `unmodeled_callee`.
- **Go `for k := range s.m`** reads unresolved, `selector_expression in range_clause`. Iterating a state map has no row.
- **Ruby `@cache[k] ||= compute(k)`** reads neutral and observe-only, because the `||=` is both the read and the write and only the write is seen. The same cache written as a read plus a store reads promiscuous and then needs the memoization rule's premises to clear. One shape, two routes, and only one of them checks a premise.
- **Ruby `return @cache[k]`** wraps its value in an `argument_list`, so a rule reading the return's first named child gets the wrapper.
- **C# `d.Remove(k, out var v)`** hands a stored value back through an `out` argument. `Remove` is on the mutating set, so the reference reads as a write and the value leaving through `v` is invisible.
- **Rust write-once soundness.** The mutable-alias premise the rule needs is now checked in the classifier, and the rule itself is still Python-only, so nothing consumes the premise yet. What keeps a Rust alias from being cleared today is the `unresolved` verdict: only write-once may clear an unresolved, and write-once cannot run for Rust. Widening it is where the premise starts earning its place.
