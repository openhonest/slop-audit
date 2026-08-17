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
