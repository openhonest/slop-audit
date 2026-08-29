"""We counted a docstring as setup, and told an author to delete an explanation.

The rule says a step definition needing thirty lines of setup means the code under test has
hidden dependencies. It measured the lines the function spans, so a comment and a docstring
counted as setup.

An adopter measured their eight remaining sites and six were already under the threshold in
code alone:

    then_fk_preserved            reported 38, code 18, docstring 16
    then_fk_checked              reported 41, code 14, comment 16
    when_drop_column             reported 87, code 42, comment 37

The sixteen-line docstring on the first one records a defect that suite paid for: the body
used to catch every exception with a comment saying the constraint had worked, so a typo in
the SQL, a closed connection or a bug in the package all read as success. The step passed
when the thing it tested was broken.

So the number told them to delete the explanation, and the family of rules this belongs to
exists to encourage exactly that explanation. A step is long because of its setup or because
somebody wrote down why it exists, and those want opposite responses.

Statements, not lines, which is what setup means. It also stops the number depending on how
a call is wrapped.
"""

from l1_analyzer import honest_code_markers as markers
from l1_analyzer import honest_code_read as read

_BOUND = 'from pytest_bdd import scenarios, then\n\nscenarios("f.feature")\n\n\n'


def _found(source: str, lang: str = "python") -> list[dict]:
    return markers.heavy_step_definitions(read.read_tree(_BOUND + source, lang)) or []


def _step(statements: int, prose: int) -> str:
    doc = '    """' + "\n".join("    explanation" for _ in range(prose)) + '"""\n' if prose else ""
    body = "\n".join(f"    call_{i}()" for i in range(statements))
    return '@then("it holds")\ndef then_it(ctx):\n' + doc + body + "\n"


def test_a_step_that_is_mostly_explanation_is_not_reported():
    """Eighteen statements and a sixteen-line docstring. Their real site."""
    assert _found(_step(statements=18, prose=16)) == []


def test_a_step_that_is_mostly_comment_is_not_reported():
    comments = "\n".join("    # why this step exists" for _ in range(20))
    assert _found('@then("it holds")\ndef then_it(ctx):\n' + comments + "\n"
                  + "\n".join(f"    call_{i}()" for i in range(14)) + "\n") == []


def test_a_step_that_really_does_thirty_statements_of_setup_is_reported():
    """The rule, unchanged. This is what it was always meant to find."""
    found = _found(_step(statements=42, prose=0))
    assert found, "forty-two statements of setup is what the rule is about"
    assert "42" in found[0]["detail"]


def test_the_count_reported_is_statements_and_says_so():
    found = _found(_step(statements=42, prose=30))
    assert found, "the prose does not save a step that is genuinely long"
    assert "42" in found[0]["detail"], found[0]["detail"]
    assert "statement" in found[0]["detail"]


def test_a_wrapped_call_counts_once():
    """The second thing statements buy. A call spread over four lines is one statement, and
    a number that moved when somebody reformatted was measuring the formatter."""
    wrapped = '@then("it holds")\ndef then_it(ctx):\n' + "".join(
        f"    call_{i}(\n        first,\n        second,\n    )\n" for i in range(20))
    assert _found(wrapped) == []


def test_a_step_of_two_statements_is_still_left_alone():
    assert _found(_step(statements=2, prose=0)) == []
