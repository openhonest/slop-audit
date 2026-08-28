"""A file we read, called unreadable.

A clause that finds nothing it can measure returns None, and the runner had two labels for
that: not applicable, meaning the question does not arise in this language, and unreadable,
meaning the rule applies and this reader could not see the code. It chose between them by
asking whether the clause carried a sentence about finding nothing to read.

That was near enough while One Gherkin Per Function read Python's own parser, because the
only files it went quiet on were ones it genuinely could not read. It became false the moment
the clause was ported: a JavaScript file holding no step definitions is read perfectly well,
and the rule applies to it. Calling that unreadable claims a gap in the instrument that is
not there, and this instrument exists to name exactly that kind of claim.

The third answer is the true one: the file was read, the rule applies, and this file holds
none of what the clause measures.
"""

import pytest
from l1_analyzer import honest_code

_NO_STEPS = {
    "python": ("m.py", "def send(channel, data):\n    return go(channel, data)\n"),
    "javascript": ("app.js", "function send(channel, data) { return go(channel, data) }\n"),
    "java": ("App.java", "class A { int send(int c) { return go(c); } }\n"),
}


def _clause(name: str, source: str, code: str) -> dict:
    return next(c for c in honest_code.assess(honest_code.read_source_text(source, name))
                if c["code"] == code)


@pytest.mark.parametrize("lang", list(_NO_STEPS))
def test_a_file_we_read_is_not_reported_as_unreadable(lang):
    name, source = _NO_STEPS[lang]
    clause = _clause(name, source, "L1.21.15")
    assert not clause["decided"]
    assert clause["undecided"] != honest_code.UNREADABLE, clause["reason"]


@pytest.mark.parametrize("lang", list(_NO_STEPS))
def test_nor_as_a_question_that_does_not_arise(lang):
    """The other wrong label. The rule applies to every source file in the repository, which
    is the whole point of a bijection between functions and scenarios."""
    name, source = _NO_STEPS[lang]
    assert _clause(name, source, "L1.21.15")["undecided"] != honest_code.NOT_APPLICABLE


@pytest.mark.parametrize("lang", list(_NO_STEPS))
def test_it_says_the_file_was_read_and_held_none_of_what_the_clause_measures(lang):
    name, source = _NO_STEPS[lang]
    clause = _clause(name, source, "L1.21.15")
    assert clause["undecided"] == honest_code.NOTHING_TO_READ
    assert clause["reason"] == honest_code.clause_named("L1.21.15")["nothing_to_read"]


def test_the_new_kind_is_one_of_the_undecided_kinds():
    """A label the rest of the tool does not know about would be a fourth answer nobody
    counts, which is how an undecided clause quietly becomes a passing one."""
    assert honest_code.NOTHING_TO_READ in honest_code.UNDECIDED_KINDS


def test_a_file_that_truly_cannot_be_read_still_says_so():
    """The direction that must not move. A file the parser rejects is a gap in what we
    know, and softening it into "held nothing" would report a clean file we never read."""
    clause = _clause("broken.py", "def f(:\n", "L1.21.15")
    assert clause["undecided"] == honest_code.UNREADABLE, clause["reason"]
