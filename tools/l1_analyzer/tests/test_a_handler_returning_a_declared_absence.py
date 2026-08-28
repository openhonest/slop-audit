"""Twelve exceptions on one rule, and eleven of them were not twelve decisions.

The rule says a handler that throws the error away reports success for work that failed.
That is right, and this package carries twelve comments telling it to allow the thing
anyway, which is the largest group of exceptions in the repository by a factor of two.

Reading them together, they are not twelve judgments. They are one shape the rule cannot
see. A reader at an edge cannot read something, and it returns the absent case of its own
declared return type: `dict | None`, `str | None`, a callable or nothing. The absence is in
the contract, so every caller has to handle it and the type checker says so. That is not a
swallowed error. It is what the Honest Code rule on implicit defaults asks for: absence as
an explicit case of a bounded type.

So the rule was asking for an exception it should never have needed, and the fix is in the
rule rather than in the twelve comments.

The other nine stay. A function declaring `-> str` and returning the empty string has not
declared anything: no caller can tell an absent file from an empty one, and the comment at
each of those sites says exactly that. A rule that cleared those too would be excusing the
shape it exists to name.
"""

import pytest
from l1_analyzer import honest_code_edges as edges
from l1_analyzer import honest_code_read as read

_DECLARED = '''import json
from pathlib import Path


def _package_json(repo: Path) -> dict | None:
    try:
        return json.loads((repo / "package.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
'''

_UNDECLARED = '''from pathlib import Path


def head_of(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""
'''

_SWALLOWED = '''def go(path):
    try:
        return do(path)
    except OSError:
        return None
'''


def _found(source: str, lang: str = "python") -> list[dict]:
    return [f for f in (edges.swallowed_exceptions(read.read_tree(source, lang)) or [])
            if f["withheld_by"] == ""]


def test_a_handler_returning_the_absence_its_signature_declares_is_not_a_swallow():
    assert _found(_DECLARED) == []


def test_a_handler_returning_an_empty_string_from_a_plain_type_is_still_reported():
    """The nine that stay. `-> str` declares nothing about absence, so no caller can tell
    an unreadable file from an empty one, and this is the shape the rule exists to name."""
    assert _found(_UNDECLARED), "an undeclared empty answer is still a swallow"


def test_a_handler_in_a_function_declaring_no_return_type_is_still_reported():
    """The absence has to be DECLARED. A function saying nothing about what it returns has
    not put the absent case in anyone's contract."""
    assert _found(_SWALLOWED), "an undeclared None is still a swallow"


@pytest.mark.parametrize("declared", ["dict | None", "Optional[dict]", "None | dict"])
def test_each_way_python_declares_an_absence_is_read(declared):
    source = _DECLARED.replace("dict | None", declared)
    assert _found(source) == [], declared


def test_a_handler_returning_something_else_entirely_is_still_reported():
    """Declaring an absence permits returning THAT. It does not permit returning a made-up
    value the caller cannot tell from a real one."""
    source = _DECLARED.replace("        return None\n", "        return {}\n")
    assert _found(source), "an empty dict is not the declared absence"


@pytest.mark.parametrize("lang", ["javascript", "ruby"])
def test_a_language_that_declares_no_return_type_cannot_use_this_route(lang):
    """Nothing changes where there is no declaration to read, so this cannot become a way to
    go quiet by writing less. The mechanism is the assertion: a language naming no marker for
    a declared absence is refused before anything else is looked at."""
    from l1_analyzer.lang_spec import LANG_SPEC

    assert LANG_SPEC[lang]["absent_markers"] == ()


def test_a_javascript_handler_returning_null_is_still_reported():
    assert _found("function go(p) {\n  try { return do_(p) } catch (e) { return null }\n}\n",
                  "javascript")


def test_ruby_returns_nothing_here_and_did_before_this_change():
    """Not a regression, and not a pass either. Ruby's rescue clause yields its last
    expression with no return keyword, and this rule reads returns, so an implicit nil has
    always been invisible to it. Recorded so the gap is a known one rather than read as a
    clean file."""
    assert _found("def go(p)\n  do_(p)\nrescue StandardError\n  nil\nend\n", "ruby") == []
