"""Our type-escape count rewards the sloppier annotation.

An adopter found this by making their annotations MORE precise and watching our number get
worse. Six handlers took `_req: dict` and returned `Any`. They wrote out the
`dict[str, Any]` both already meant, which is true and better, and our count went from 12.52
to 13.78 escapes per thousand lines. They kept the change.

The ranking is upside down for a whole family:

    dict              means dict[Any, Any], the least precise mapping the language has, 0
    dict[str, Any]    key pinned, value honestly open, 1
    dict[str, str]    fully precise, 0

The middle rung is where real code lands, because the key is a string and the value often
genuinely is not one thing. It is strictly better than the top rung and we score it worse.

The arithmetic is not the problem. An author who watches this number learns to write `dict`,
which is worse and which we cannot see at all. A `# type: ignore` announces itself. A bare
generic announces nothing and scores perfectly, which is the shape this whole instrument
exists to name.
"""

import pytest
from l1_analyzer import honest_code_read as read
from l1_analyzer.indicators import _count_type_escapes_in_tree
from l1_analyzer.lang_cfg import LANG_CFG


def _escapes(source: str, lang: str = "python") -> int:
    return _count_type_escapes_in_tree(read.read_tree(source, lang)["root"], LANG_CFG[lang])


@pytest.mark.parametrize("generic", ["dict", "list", "tuple", "set", "frozenset"])
def test_a_bare_generic_annotation_is_an_escape(generic):
    assert _escapes(f"def go(items: {generic}) -> int:\n    return len(items)\n") == 1, generic


def test_a_precise_annotation_is_not():
    assert _escapes("def go(items: dict[str, str]) -> int:\n    return len(items)\n") == 0


def test_the_middle_rung_now_scores_better_than_the_bare_one():
    """The ranking, asserted directly. Pinning the key is an improvement and has to read
    as one, or an author who watches the number is taught to undo it."""
    bare = _escapes("def go(items: dict) -> int:\n    return len(items)\n")
    pinned = _escapes("def go(items: dict[str, Any]) -> int:\n    return len(items)\n")
    precise = _escapes("def go(items: dict[str, str]) -> int:\n    return len(items)\n")
    assert precise <= pinned < bare + 1
    assert bare >= 1, "the least precise annotation must not score best"


def test_a_bare_generic_used_as_a_value_is_not_an_escape():
    """`dict()` builds a mapping and annotates nothing. Charging it would report every
    constructor in the file."""
    assert _escapes("def go():\n    out = dict()\n    out['a'] = list()\n    return out\n") == 0


def test_a_bare_generic_in_an_isinstance_check_is_not_an_escape():
    """A runtime type test names a type and declares nothing. Another clause has opinions
    about that check; this one is counting annotations."""
    assert _escapes("def go(x):\n    return isinstance(x, dict)\n") == 0


def test_a_return_annotation_counts_too():
    assert _escapes("def go() -> list:\n    return []\n") == 1


def test_a_variable_annotation_counts_too():
    assert _escapes("seen: dict = {}\n") == 1


def test_any_alone_still_counts_once():
    """Nothing about this change touches what Any costs."""
    assert _escapes("def go(x: Any) -> Any:\n    return x\n") == 2
