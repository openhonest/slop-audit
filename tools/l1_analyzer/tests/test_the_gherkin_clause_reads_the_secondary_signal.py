"""Clause 15 reads the secondary signal and says so, because it cannot read the rule.

The principle is One Gherkin Per Function, and the rule is a bijection: every function
carries exactly one scenario naming it, a function with no scenario is code nothing
describes, and a scenario with no function describes code that does not exist. The counts
having to reconcile is what makes a missing test, a test that asserts nothing, and a test
whose subject is gone all visible, when each is invisible alone.

The document calls step-definition length the SECONDARY signal, and that is the only half
this clause reads. It was named after the old framing, Simple Gherkin Steps Signal Honest
Architecture, and reported "not applicable" for any file holding no step definitions. That
is what a reader saw for every source file in a repository with no scenarios at all, which
is the case the rule is most about.

A bijection needs the functions and the feature files together, and where a project keeps
its features is a convention this reader does not know. So it is undecided, with the reason
said, rather than a verdict of not-applicable that reads as nothing to answer for.
"""

import pytest
from l1_analyzer import honest_code
from l1_analyzer import honest_code_read as read
from l1_analyzer import honest_code_rules as rules

_STEPS = ('from pytest_bdd import given\n\n\n'
          '@given("a thing")\ndef a_thing():\n' + "    x = 1\n" * 40 + "    return x\n")


def _assess(source: str) -> dict:
    return next(c for c in honest_code.assess(honest_code.read_source_text(source, "m.py"))
                if c["code"] == "L1.21.15")


def test_a_long_step_is_still_reported():
    """The half it can read, unchanged by the port to the shared node vocabulary."""
    found = rules.heavy_step_definitions(read.read_tree(_STEPS, "python"))
    assert [f["symbol"] for f in found] == ["a_thing"], found


def test_a_file_with_no_step_definitions_is_undecided_rather_than_not_applicable():
    """The case the rule is most about: a source file in a repository with no scenarios."""
    clause = _assess("def send(channel, data):\n    return go(channel, data)\n")
    assert not clause["decided"]
    assert clause["undecided"] != honest_code.NOT_APPLICABLE, clause["undecided"]


def test_the_reason_names_the_bijection_as_the_thing_it_could_not_read():
    clause = _assess("def send(channel, data):\n    return go(channel, data)\n")
    assert "scenario" in clause["reason"].lower()


@pytest.mark.parametrize("code", ["L1.21.15"])
def test_the_clause_is_named_for_the_principle_it_belongs_to(code):
    clause = next(c for c in honest_code.CLAUSES if c["code"] == code)
    assert clause["name"] == "One Gherkin Per Function"
