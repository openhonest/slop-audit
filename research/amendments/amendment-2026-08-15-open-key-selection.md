# Amendment 2026-08-15: an unbounded key selects, and selection is a decision

## What was wrong

L1.18b graded one runtime shape two different ways depending on the surface language. A container read at a key the caller chooses was PROMISCUOUS in C and NEUTRAL in Python.

```python
class S:
    def __init__(self):
        self.cache = {}
    def put(self, k, v):
        self.cache[k] = v
    def get(self, k):
        return self.cache[k]
```

```c
static int cache[256];
void put(int k, int v) { cache[k] = v; }
int get(int k) { return cache[k]; }
```

| | before | after |
|---|---|---|
| Python | **neutral** | promiscuous |
| C, Java, C#, Ruby, Rust, Go, TypeScript, JavaScript | promiscuous | promiscuous |

The indicator measures a property of the code at runtime. Nothing in that question mentions a language, so a divergence is a defect in at least one of the readings, and this one was a MISS in the most-used language on the indicator the standard rests on.

## The mechanism

The classifier was right in both languages. `_categorize` graded the keyed read UNBOUNDED and `_verdict` returned PROMISCUOUS for Python exactly as for C. The verdict was then overturned by `state_bounds_filters`, which is Python-only.

Two of its rules cleared the shape, and the minimal reproduction reaches a different one from the realistic one:

| source | clearing rule |
|---|---|
| `self.cache = {}` plus `return self.cache[k]` | write-once: one whole-attribute assignment, no in-place mutation, nothing returned whole, nothing passed to an unknown callee |
| the same plus `self.cache[k] = v` | carried value: no reference to the attribute appears in a test expression |

Neither rule is wrong about what it checks. Both are wrong about what makes this shape unbounded. The carried-value rule reads the decision off the KEYWORD — is there an `if` — when a subscript by an unbounded key is itself the decision: the container answers one way per key, the caller chooses the key, and moving the `if` into the caller does not remove it. The write-once rule argues immutability, which says nothing about how many classes a key cuts the contents into.

The structural cause is wider than either rule, and it is not fixed here. **`state_bounds_filters` is Python-only and sits downstream of a language-independent classifier.** Every shape it clears is a shape where Python's answer can differ from the other eight languages, and nothing in the tree compared them. The per-language conformance suites each state their own expected verdict case by case, so eight of them could say one thing and the ninth another with a green suite. That is how this defect shipped and how it stayed.

## The fix

One guard in `state_bounds_filters`, before the rules and after the memoization check:

```python
def _is_open_key(key):
    if key is not None and key.type == "slice":
        return False
    key = _unwrap_unary(key)
    if key is None or key.type in _PY["literal_types"]:
        return False
    return not _is_state_of_this_class(key)
```

A reference that is the collection of a subscript READ — not a store target — whose key is an open key keeps its finding. Three lines are drawn, and each one is a case the guard must not reach.

**A literal key is not open.** `self.cache["seven"]` cuts one class out of the container and leaves a bounded question. The unary unwrap comes from the 2026-08-14 amendment: `[-1]` is a constant position.

**A key that is state in this class is not open.** `self._rows[self._i]` is the cursor shape, and `self._i` already carries its own finding, bounded there by `self._i >= len(self._rows)`. Charging the container for it as well counts one decision twice, which is what made the cursor a false positive. A key that arrives as a parameter is carried by no other finding, so it lands here or nowhere.

**A slice is not a key.** `self._hash[:4]` and `self.alerts[-limit:]` take a contiguous run, not one stored value out of unboundedly many. This line was measured rather than predicted: the first draft flagged `self.e164_hash[:4].hex()` in buckler/iam, because tree-sitter spells `[:4]` as a `slice` node and the draft asked only whether the node was a literal.

**A store target is not a selection.** `d[k] = v`, `d[k] += 1` and `del d[k]` put a value in rather than take one out, so the write-only accumulator rule keeps working unchanged.

**Memoization is the one shape allowed past the guard**, and it moved above it for that reason. A presence-gated, result-invariant cache answers the same for a key whether or not the key is stored, so the partition its keyed read cuts belongs to the function being memoised: delete the cache and every observable answer is unchanged. No other rule can make that argument, which is why no other rule is exempt.

The guard cannot create a finding. `is_false_positive` is consulted only when the classifier has already reached a non-neutral verdict, so returning False leaves that verdict standing. Every verdict this change produces is one the classifier reached on its own.

## What was reversed

`test_carried_value_that_drives_no_decision_clears` asserted the carried-value rule's own fixture NEUTRAL, and that fixture carried a fourth method:

```python
def page(self, k):
    return self._qs[k]
```

That is the same runtime shape as the C `value-indexed-cache` vector, which has always read PROMISCUOUS. The two cannot both be right about one behaviour, and the C answer is the one kept. The reversal is recorded as its own KEEP case, `test_carried_builder_sliced_by_an_open_key_keeps`, rather than left in a commit message.

**The cost is real.** Every builder that exposes positional access by a parameter now reads promiscuous, and that is the population declaro-persistum was cleared out of. The builder chain itself still clears, and so does the same builder sliced by a literal; only the open-key read moved. If the reversal is wrong, it is C that has to change, because the property is one property.

## What the numbers did

Twelve repositories, before and after in one process, with the guard neutralised for the `before` pass. **No grade changed and no band changed anywhere.** Five states moved, all Python, all of them a container read at a key from outside the class.

| Repo | Lang | Grade | neutral / promiscuous / unresolved |
|---|---|---|---|
| multicardz | python | F → F | 548/23/71 → 547/24/71 |
| buckler/iam | python | F → F | 860/19/48 → 859/19/49 |
| cardz | python | F → F | 158/14/28 → 156/16/28 |
| declaro | python | F → F | 315/24/30 → 314/25/30 |
| umbra | python | C → C | 2/0/2 unchanged |
| slop-audit | python | A → A | 0/0/0 unchanged |
| google/gson | java | F → F | 391/20/151 unchanged |
| junit-team/junit4 | java | F → F | 195/9/127 unchanged |
| JamesNK/Newtonsoft.Json | csharp | F → F | 1058/36/170 unchanged |
| restsharp/RestSharp | csharp | F → F | 259/10/58 unchanged |
| json-c/json-c | c | F → F | 25/5/21 unchanged |
| libuv/libuv | c | F → F | 197/4/172 unchanged |

The six corpus repositories are Java, C# and C, and the filter is Python-only, so their zero is structural rather than lucky. `validate_corpus.py` re-run: every compared indicator equal across all six.

Every state that moved, read at the source:

| State | Movement | Judgement |
|---|---|---|
| `cardz packages/shared/cache/cache_manager.py:52 self._cache_locks` | neutral → promiscuous | Real. A lock per workspace id, `self._cache_locks[workspace_id]` read at line 201 with the id a parameter. No finite suite enumerates the workspaces. |
| `declaro .../performance_monitor.py:101 self.metric_history` | neutral → promiscuous | Real. `defaultdict(deque)` read at `self.metric_history[metric_name]`, the name a parameter. |
| `multicardz apps/shared/services/performance_tracker.py:174 self.session_history` | neutral → promiscuous | Real. Same shape, keyed by session. |
| `cardz hooks/services/tag_validator.py:303 self.lines` | neutral → promiscuous | Real but the weakest. `content.split('\n')` read at `self.lines[line_num - 1]`, guarded by `line_num <= len(self.lines)`. The guard bounds the index to the container; it does not enumerate the answers. |
| `iam middleware/hmac_middleware.py:137 self.secrets` | neutral → **unresolved** | Real. The classifier already read this UNRESOLVED; write-once used to clear it. `self.secrets[app_type]` selects a secret chain by an open key, which is an escape route the write-once rule's own `_escapes` check does not cover, so the fail-closed verdict now stands as the entry point's docstring always said it should. |

## Regression cover

`tools/l1_analyzer/tests/test_state_bounds_filters.py`, seven new cases, three KEEP and four CLEAR:

- `test_unbounded_keyed_read_of_a_container_this_class_owns_keeps` — the defect, with the store present.
- `test_unbounded_keyed_read_keeps_even_with_no_second_writer` — the same without the store, so write-once alone cannot satisfy the fix.
- `test_carried_builder_sliced_by_an_open_key_keeps` — the reversal, recorded.
- `test_keyed_read_by_state_this_class_bounds_clears` — the cursor, which must not regress.
- `test_carried_value_sliced_by_a_literal_still_clears` — the guard reads the key, not the presence of a subscript.
- `test_literal_width_slice_of_a_carried_value_clears` — the iam false alarm.
- `test_variable_width_slice_of_a_carried_value_clears` — the slice boundary, stated so it cannot drift.

Red first, against the unfixed code: 2 failed, 20 passed, both failures the two open-key KEEP cases, both reading `neutral` where `promiscuous` was asserted.

`tools/l1_analyzer/tests/test_finite_testability_cross_language.py` is the suite whose absence let this ship: see below.

## The suite that was missing

Seven runtime shapes, each expressed in all nine languages, each declaring ONE verdict as a property of the behaviour. Two assertions per shape. `test_every_language_agrees_on_the_shape` is the regression guard and names both sides of any split. `test_the_agreed_verdict_is_the_one_the_behaviour_entails` is the correctness guard, because nine languages can agree on a wrong answer.

Run against the unfixed code it fails exactly as intended:

```
open-key-read-returned: languages disagree about one runtime shape ->
  neutral: python; promiscuous: c, csharp, go, java, javascript, ruby, rust, typescript
```

The matrix after the fix:

| Shape | py | ts | js | java | c# | rb | rs | go | c |
|---|---|---|---|---|---|---|---|---|---|
| open-key-read-into-branch | promiscuous ×9 | | | | | | | | |
| open-key-read-returned | promiscuous ×9 | | | | | | | | |
| literal-key-only | neutral ×9 | | | | | | | | |
| write-only-accumulator | neutral ×9 | | | | | | | | |
| presence-test-branches-converge | **neutral** | promiscuous | promiscuous | promiscuous | promiscuous | promiscuous | promiscuous | promiscuous | n/a |
| bounded-scalar-vs-constants | neutral ×9 | | | | | | | | |
| state-handed-to-an-unreadable-call | unresolved ×9 | | | | | | | | |

C cannot express `presence-test-branches-converge`: it has no membership test and no growing container, so a fixed array answers for every index whether or not anything was stored there. That is an absence in the language, declared as `None` in the fixture table and argued in the shape's prose, not a gap in the fixture.

## Reported and not fixed: the presence-gated tally (bd `slop-audit-90t`)

The one open disagreement, and it points the other way. `if k not in self.hits: self.hits[k] = 0` followed by `self.hits[k] += 1` is NEUTRAL in Python and PROMISCUOUS in the other seven that can express it. **Python is the correct side.** The gate's two arms fall through to the same statement, so no test can tell them apart, and nothing reads the tally back out, so the count reaches no decision. The other seven have no accumulator rule because `state_bounds_filters` was never ported.

It is filed rather than folded in because both repairs are large. Removing Python's accumulator rule would regress a deliberate false-positive removal and would be wrong on the merits. Porting the rule to eight grammars is the structural repair and it needs its own corpus run.

**The two cross-language conformance tests for that shape are RED in the tree, on purpose.** A suite that goes quiet about a disagreement is the failure this file exists to describe.

## Note for Paper A

L1.18b verdicts can only move from NEUTRAL toward PROMISCUOUS or UNRESOLVED under this change, never the reverse, and only for Python state read at a key the class does not bound. It is a miss correction, not a definitional change: the predicate is unaltered and the classifier is untouched. Corpus movement is zero, so no published corpus number changes.

L1.18 reads `state_bounds._analyze_file` for its bound-awareness correction, so this change moves L1.18's number wherever it moves L1.18b's. No L1.18 band moved on any of the twelve repositories measured.
