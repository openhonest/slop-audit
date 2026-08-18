"""A borrowed, parenthesised or cast literal key is a literal key (L1.18b).

The sibling of test_negative_literal_index.py, and the same defect one wrapper along.
`is_unbounded_value` asked whether the key node's OWN type was a literal type, so any
wrapper hid the literal underneath. The unary wrapper was removed on 2026-08-14. The
borrow wrapper was not, and in Rust it is not an edge case: `map.contains_key(&1)` is
what real code writes and `contains_key(1)` does not compile for a borrowed key. So the
idiomatic spelling graded PROMISCUOUS, which is the F tier, and the unidiomatic one
graded NEUTRAL.

`reference_expression` was ALREADY in Rust's passthrough_types, so the flow walker
treated the borrow as transparent while this predicate did not. Two walks disagreeing
about the same wrapper is the shape that let it survive the first fix.

The vocabulary is its own key and deliberately NOT the flow passthrough set. Passthrough
holds `boolean_operator`, `not_operator`, `try_expression`, `await` and `expression_list`,
none of which preserve a literal's identity: `s[1 or x]` is not a constant index, and
folding it would be a false green rather than a missed one. The last test here is that
guard.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds


def _verdict(src: str, lang: str, ext: str, state: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / f"m.{ext}").write_text(src)
        r = state_bounds.classify(p, lang)
        return next((f["verdict"] for f in r["findings"] if f["state"] == state), "absent")


_RUST = ('use std::collections::HashMap;\nstruct S {{ by_id: HashMap<i32, i32> }}\n'
         'impl S {{\n  fn q(&self) -> i32 {{ if self.by_id.contains_key({key}) {{ 1 }} else {{ 0 }} }}\n}}\n')


def test_rust_borrowed_literal_key_reaches_the_same_verdict_as_the_bare_one():
    bare = _verdict(_RUST.format(key="1"), "rust", "rs", "self.by_id")
    borrowed = _verdict(_RUST.format(key="&1"), "rust", "rs", "self.by_id")
    assert bare == "neutral"
    assert borrowed == bare


def test_rust_a_borrowed_variable_key_stays_promiscuous():
    """The wrapper is peeled, not whitelisted. `&k` peels to an identifier, which is no
    literal, so a borrow never launders a variable into a constant."""
    assert _verdict(_RUST.format(key="&k"), "rust", "rs", "self.by_id") == "promiscuous"


def test_a_parenthesised_literal_key_is_a_literal_key_in_python():
    plain = 'S = {}\ndef g():\n    if S[1]:\n        return 1\n    return 0\n'
    parens = 'S = {}\ndef g():\n    if S[(1)]:\n        return 1\n    return 0\n'
    assert _verdict(plain, "python", "py", "S") == "neutral"
    assert _verdict(parens, "python", "py", "S") == _verdict(plain, "python", "py", "S")


def test_a_boolean_operator_over_a_literal_is_not_a_literal_key():
    """The guard the vocabulary exists to keep. `S[1 or x]` is not a constant index, and
    `boolean_operator` sits in the flow passthrough set, so reusing that set wholesale
    would have folded this to a false green."""
    src = 'S = {}\ndef g(x):\n    if S[1 or x]:\n        return 1\n    return 0\n'
    assert _verdict(src, "python", "py", "S") == "promiscuous"
