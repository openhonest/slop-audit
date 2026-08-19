"""The argument wrappers are load-bearing since 2026-08-18, and nothing said so.

`_escapes` once tested `parent.type == "argument_list"` alone, so `f(*self.a)`,
`f(**self.a)` and `f(x=self.a)` handed the bare attribute to an unknown callee
undetected. It was fixed in c562cda as DRIFT REMOVAL rather than as a live defect, and
the bead recording it says why: the classifier failed closed on those three constructs,
naming each as an unread construct, before the filter was ever called. The fix was for
"the day the classifier grows rows for those constructs".

That day was 2026-08-18. `keyword_argument` joined Python's passthrough types this
morning, so `f(x=self.a)` now reaches the argument row instead of stopping at the
terminal, and `_argument_list_above` is what stands between that and a write-once
clearance of a value handed to an unknown callee.

Nothing asserted it. The fix was made against a future that arrived, and the test that
would notice if someone simplified `_ARGUMENT_WRAPPERS` away did not exist.
"""

import pathlib
import tempfile

import pytest
from l1_analyzer import state_bounds, state_bounds_filters

_SHAPES = {
    "keyword": "        return sink(rows=self._a)\n",
    "list_splat": "        return sink(*self._a)\n",
    "dict_splat": "        return sink(**self._a)\n",
}


def _verdict(body: str) -> str:
    src = ("class Q:\n    def __init__(self):\n        self._a = {}\n"
           "    def send(self, sink):\n" + body)
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(src)
        r = state_bounds.classify(p, "python")
        f = next((x for x in r["findings"] if x["state"].endswith("_a")), {})
    assert f, "the attribute should be found"
    return f["verdict"]


@pytest.mark.parametrize("shape", sorted(_SHAPES))
def test_a_value_handed_to_an_unknown_callee_through_a_wrapper_is_not_cleared(shape):
    assert _verdict(_SHAPES[shape]) != "neutral", (
        f"{shape}: an attribute handed to a callee nobody modelled must not read as bounded")


def test_the_wrapper_vocabulary_still_names_all_three():
    """The direct assertion. Removing an entry here reopens the hole c562cda closed, and
    for `keyword_argument` that is now a live path rather than a future one."""
    assert state_bounds_filters._ARGUMENT_WRAPPERS == {
        "list_splat", "dictionary_splat", "keyword_argument"}
