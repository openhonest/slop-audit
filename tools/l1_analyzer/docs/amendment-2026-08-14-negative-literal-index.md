# Amendment 2026-08-14: a negated literal index is a literal index

## What was wrong

L1.18b graded `self._stack[-1]` PROMISCUOUS and `self._stack[0]` NEUTRAL, on two files identical but for one character. A stack-based parser is the commonest shape that trips it, and because one promiscuous piece of state drives the whole repository verdict to CANNOT, the cost is a false F on the entire codebase. A live external adopter was given one on a production repository.

Minimal reproduction, at base commit `c07e96a`:

```python
class P:
    def __init__(self):
        self._stack = []

    def open(self, tag):
        self._stack.append(tag)

    def close(self, tag, i):
        while len(self._stack) > 1:
            top = self._stack[INDEX]
            if top == tag:
                return True
        return False
```

| INDEX | before | after |
|---|---|---|
| `0` | 1 neutral / 0 promiscuous | 1 neutral / 0 promiscuous |
| `-1` | **0 neutral / 1 promiscuous** | 1 neutral / 0 promiscuous |
| `+1` | **0 neutral / 1 promiscuous** | 1 neutral / 0 promiscuous |
| `i` | 0 neutral / 1 promiscuous | 0 neutral / 1 promiscuous |

## The mechanism

`_is_unbounded_value` asked one question: is the index node's own type in the language's `literal_types`? Every grammar in the table parses `s[-1]` as a *unary node wrapping* the integer, not as a signed literal, so the wrapper hid the literal and a constant index read as an unbounded lookup.

The node type differs per grammar. Dumped from the actual parsers rather than assumed:

| Language | `s[-1]` index node | operand |
|---|---|---|
| python | `unary_operator` | `integer` |
| typescript | `unary_expression` | `number` |
| javascript | `unary_expression` | `number` |
| java | `unary_expression` | `decimal_integer_literal` |
| csharp | `prefix_unary_expression` | `integer_literal` |
| rust | `unary_expression` | `integer_literal` |
| ruby | `unary` | `integer` |
| go | `unary_expression` | `int_literal` |
| c | `number_literal` (signed, folded) | n/a |

**C was not immune, and the diagnosis that it might be was wrong.** The tree-sitter-c lexer folds an adjacent sign into a single signed `number_literal`, so `s[-1]` never had the defect. The fold is whitespace-sensitive: `s[- 1]` is a `unary_expression` exactly like everywhere else. C is fixed with the rest, because a meter that is correct only while the author omits a space is not correct.

The operator token is unnamed in all nine grammars, so the first named child is the operand in every one.

## The fix

A new `unary_types` entry per language in `lang_spec.py`, and `_unwrap_unary` in `state_bounds.py`, applied inside `_is_unbounded_value`:

```python
def _unwrap_unary(node, sp):
    while node is not None and node.type in sp.get("unary_types", ()):
        node = _first_named(node)
    return node
```

**Unwrapping, not whitelisting.** The wrapper is peeled and the question is then asked of the operand, so `-1` resolves to a literal and `-i` resolves to an identifier and stays PROMISCUOUS. Whitelisting the wrapper node type would have laundered every variable behind a minus sign into a false green. The loop handles a stack of operators (`- -1`).

`_is_unbounded_value` serves both the subscript index and the keyed-read call argument, so one change covers both paths. That matters: the keyed-read arm was independently affected, confirmed by parse dump in Java (`map.get(-1)` -> `unary_expression`), C# (`ContainsKey(-1)` -> `prefix_unary_expression`), Ruby (`h.fetch(-1)` -> `unary`) and TypeScript (`this.s.get(-1)` -> `unary_expression`).

Nine LANG_SPEC entries changed: python, typescript, javascript, java, csharp, rust, ruby, c, go. No language was left out.

## Where the line is drawn

**Binary operators stay unbounded.** `s[1 - 1]` is a constant a human can see, but the meter does not fold arithmetic, and it parses as `binary_expression` in every grammar. Leaving it PROMISCUOUS is the conservative side of the line: never a false green. A test asserts this in every language so the scope cannot drift by accident.

Two incidental consequences, both correct. Rust has no unary plus, so `s[+1]` is a parse error there and stays unbounded; that is not valid Rust. C#'s index-from-end operator `x[^1]` also parses as `prefix_unary_expression` over a literal, so it now reads as bounded, which it is: `^1` is the last element, a constant position.

## What the numbers did

**Zero movement across the parity corpus.** All six repositories at their pinned commits, byte-identical L1.18b output before and after, down to the per-finding `file:line:state` list of promiscuous states:

| Repo | Lang | Verdict | neutral / promiscuous / unresolved |
|---|---|---|---|
| google/gson | java | promiscuous | 371 / 18 / 173 |
| junit-team/junit4 | java | promiscuous | 187 / 9 / 135 |
| JamesNK/Newtonsoft.Json | csharp | promiscuous | 464 / 33 / 143 |
| restsharp/RestSharp | csharp | promiscuous | 72 / 8 / 26 |
| json-c/json-c | c | promiscuous | 17 / 5 / 18 |
| libuv/libuv | c | promiscuous | 113 / 2 / 97 |

The zero is explained, not assumed. Counting the exact shape the fix changes, a subscript whose index is a unary node wrapping a literal, in production scope:

| Repo | `s[-literal]` | `s[-variable]` | `s[literal]` |
|---|---|---|---|
| google/gson | 0 | 0 | 62 |
| junit-team/junit4 | 0 | 0 | 8 |
| JamesNK/Newtonsoft.Json | 0 | 2 | 83 |
| restsharp/RestSharp | 1 | 0 | 14 |
| json-c/json-c | 0 | 0 | 148 |
| libuv/libuv | 0 | 4 | 495 |

One occurrence in six repositories, and it is `baseUrl.AbsoluteUri[^1]` in `src/RestSharp/Request/UriExtensions.cs:32`, indexing a local rather than a tracked piece of state, so it reaches no finding.

**The corpus cannot regression-test this defect class, and that is the reportable gap.** It holds java, csharp and c only. Java and C# arrays cannot be indexed by a negative integer, and C folds the sign, so the three languages where `s[-1]` is ordinary idiom (Python, Ruby, JavaScript/TypeScript) have no corpus entry at all. The defect was found by an external adopter rather than by the corpus because the corpus is structurally blind to it. A Python entry and a Ruby or TypeScript entry would close that blindness.

## Regression cover

`tests/test_negative_literal_index.py`, 54 cases over all nine languages, built from one source template per language with only the index token substituted:

- `test_positive_literal_index_is_neutral`: the control, `[0]`. Green before and after; without it the rest proves nothing.
- `test_negative_literal_index_matches_positive`: `[-1]` must reach the same verdict as `[0]`.
- `test_unary_plus_literal_index_matches_bare`: `[+1]`, every language but Rust.
- `test_variable_index_stays_promiscuous`: `[i]`, the behaviour the fix must not break.
- `test_negated_variable_index_stays_promiscuous`: `[-i]`, which proves the change unwraps rather than whitelists.
- `test_c_spaced_sign_is_the_case_the_lexer_does_not_fold`: `[- 1]` in C.
- `test_binary_expression_index_stays_unbounded`: `[1 - 1]`, holding the scope line.

Run red first against the unfixed code at `c07e96a`: **16 failed, 38 passed**. The 16 are the eight unary-node grammars on `[-1]`, seven of them again on `[+1]`, and the C spaced-sign case. The 38 that passed are the controls and guards, which must hold in both states, and did.

Full suite: 425 passed, 1 skipped (371 + 54 new; the 372 baseline was 371 passed plus 1 skipped).

## The port

**No port. L1.18b does not exist in Rust.** `tools/slop-audit-rs/src/indicators/` carries seven indicator modules and no state-bounds module, and `validate.py` compares only codes present in both panels, so L1.18b is never in the comparison set. The one mention of it in `validate.py` is a sort-order comment. Parity is unaffected by construction, and was re-run to confirm: 16/16 indicators equal on this repository, and 16/16 on each of the six corpus repositories.

## Reported and not fixed: the borrow wrapper (bd `slop-audit-i4l`)

The architectural cause is wider than the instance repaired here. `_is_unbounded_value` compares **one** node type against `literal_types`, so *any* wrapper node hides the literal underneath. Negation was one wrapper. The borrow is another, and it is still open:

```
self.by_id.contains_key(&1)   -> promiscuous
self.by_id.contains_key(1)    -> neutral
```

The borrowed form is the one real Rust code writes, so Rust keyed reads on literal keys are misclassified today whatever the sign. `reference_expression` is *already* in Rust's `passthrough_types`, which means the flow walker treats that wrapper as transparent while `_is_unbounded_value` does not: two walks in the same file disagreeing about the same node.

The structural repair is a `transparent_value_wrappers` set (unary, reference, parenthesis, cast) read by `_is_unbounded_value`. It must stay **distinct** from the flow-walk `passthrough_types` and must not simply reuse it, because that set also carries `boolean_operator`, and folding `s[1 or x]` to its first operand would manufacture exactly the false green this meter exists to prevent.

It is filed rather than folded in because it is a wider blast radius than this repair: unlike the unary fix, it moves positive-literal keyed reads too, and it needs its own corpus run.

## Note for Paper A

L1.18b verdicts can only move from PROMISCUOUS toward NEUTRAL under this fix, never the reverse, and only for state whose sole unbounded evidence was a negated literal. It is a false-positive correction, not a definitional change. Corpus movement is zero, so no published corpus number changes.
