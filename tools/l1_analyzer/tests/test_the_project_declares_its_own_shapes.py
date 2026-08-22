"""Two clauses that re-reported decisions the project had already made.

Both came from an adopter measuring L1.21 against a real package: 167 findings, of which
roughly a third were the analyzer not reading declarations that were already load-bearing
somewhere else in that project.

CLAUSE 5 AND THE EXCEPTION HIERARCHY. `DECLARED_SHAPES` knew the literal name `Exception`
and nothing about a class that derives from one, so `class ParseError(HonestCheckError)`
was reported as inheriting to share an implementation. An exception hierarchy is the normal
way to write exceptions and the framework's own rule permits it, so every second-level
exception in that package fired, sixteen of them in one file.

CLAUSE 4 AND THE DECLARED BOUNDARY. That package marks its edges with a `@boundary`
decorator, and its own checker reads it. Clause 4's whole rule is that I/O belongs at the
boundary, so a function DECLARING itself the boundary and doing I/O is conforming rather
than violating.

This is not the directory-wide exemption refused earlier. That would have been a
suppression, silencing a rule over a path. A boundary decorator is the project stating
where its edges are, which is the thing the rule is about. The clause infers the boundary
from the call graph when nothing says; a declaration is better evidence than an inference,
and where both exist the declaration wins.
"""

import ast

import pytest
from l1_analyzer import honest_code_rules as rules


def _module(text: str) -> dict:
    return {"path": "m.py", "language": "python", "text": text,
            "tree": ast.parse(text), "readable": True, "unreadable_reason": ""}


# --------------------------------------------------------------------------
# Clause 5: an exception hierarchy
# --------------------------------------------------------------------------

def test_a_class_deriving_from_a_project_exception_is_not_inheriting_for_reuse():
    """`class ParseError(HonestCheckError)` where HonestCheckError derives from Exception.
    Sixteen of these in one file fired as violations.

    The second half is what gives the first one teeth: change the root from Exception to
    anything else and the same two-class shape fires, so this fixture is reading the
    hierarchy rather than the number of classes."""
    source = ("class HonestCheckError(Exception):\n    pass\n\n\n"
              "class ParseError(HonestCheckError):\n    pass\n")
    assert rules.inheritance_for_reuse(_module(source)) == []
    assert rules.inheritance_for_reuse(_module(source.replace("(Exception)", "(Widget)"))), (
        "the same shape with a non-exception root reports nothing, so this fixture cannot "
        "tell whether the hierarchy was followed")


def test_a_deep_exception_hierarchy_is_still_exceptions():
    source = ("class Base(Exception):\n    pass\n\n\n"
              "class Middle(Base):\n    pass\n\n\n"
              "class Leaf(Middle):\n    pass\n")
    assert rules.inheritance_for_reuse(_module(source)) == []


def test_an_exception_hierarchy_is_not_a_data_class_either():
    source = ("class Base(Exception):\n    pass\n\n\n"
              "class Detailed(Base):\n"
              "    def __init__(self, path):\n        self.path = path\n")
    assert rules.data_classes(_module(source)) == []


def test_a_class_named_like_an_exception_but_deriving_from_nothing_of_the_kind():
    """The name is not the rule. A class called `Error` that inherits an implementation is
    inheriting an implementation."""
    source = ("class Widget:\n    pass\n\n\nclass ThingError(Widget):\n    pass\n")
    assert rules.inheritance_for_reuse(_module(source))


def test_ordinary_inheritance_in_the_same_file_is_still_found():
    """The exception carve-out must not swallow the clause. A class hierarchy beside an
    exception hierarchy is still a class hierarchy."""
    source = ("class Base(Exception):\n    pass\n\n\n"
              "class Leaf(Base):\n    pass\n\n\n"
              "class User:\n    pass\n\n\nclass Admin(User):\n    pass\n")
    assert [f["symbol"] for f in rules.inheritance_for_reuse(_module(source))] == ["Admin"]


def test_a_base_from_another_module_cannot_be_traced_and_is_still_reported():
    """What this does NOT decide, said where it is decided. A base defined elsewhere may
    well be an exception, and one file cannot tell. It stays reported, which is the
    direction that sends a reader to look rather than the one that hides it."""
    assert rules.inheritance_for_reuse(_module("class Leaf(SomethingImported):\n    pass\n"))


# --------------------------------------------------------------------------
# Clause 4: the declared boundary
# --------------------------------------------------------------------------

def test_a_function_that_declares_itself_the_boundary_may_do_io():
    """The rule is that I/O belongs at the boundary. A function saying it IS the boundary
    and then doing I/O is conforming, and the project's own checker already reads this."""
    source = ("@boundary\ndef load(path):\n    return path.read_text()\n\n\n"
              "def total(path):\n    return load(path)\n")
    assert rules.io_below_the_boundary(_module(source)) == []


@pytest.mark.parametrize("spelling", [
    "@boundary", "@boundary()", "@honest.boundary", "@boundary_in", "@boundary_out",
])
def test_the_declaration_is_recognised_however_it_is_spelled(spelling):
    """Both directions, in one test, because one direction cannot tell whether the fixture
    is discriminating.

    An adopter verifying this from outside built a case where every function did I/O and
    nothing called anything: it returned no findings with the decorator AND without it, so
    it would have passed whether or not the feature existed. A fixture with no interior
    cannot exercise a rule about interiors.

    Stripping the decorator from the SAME source is what proves this test has teeth."""
    declared = (f"{spelling}\ndef load(path):\n    return path.read_text()\n\n\n"
                "def total(path):\n    return load(path)\n")
    undeclared = declared.replace(spelling + "\n", "")
    assert rules.io_below_the_boundary(_module(declared)) == [], spelling
    assert rules.io_below_the_boundary(_module(undeclared)), (
        f"the fixture for {spelling} reports nothing either way, so it cannot tell whether "
        "the declaration was read")


def test_an_undeclared_function_doing_io_is_still_found():
    """The carve-out reads a declaration. Where there is none, the call graph is still the
    evidence and the clause still fires."""
    source = ("def load(path):\n    return path.read_text()\n\n\n"
              "def total(path):\n    return load(path)\n")
    assert [f["symbol"] for f in rules.io_below_the_boundary(_module(source))] == ["load"]


def test_a_declared_boundary_does_not_excuse_its_callers():
    """The declaration is about the function that carries it. A function with no decorator
    doing its own I/O is not covered by a sibling's."""
    source = ("@boundary\ndef load(path):\n    return path.read_text()\n\n\n"
              "def save(path, text):\n    path.write_text(text)\n\n\n"
              "def run(path):\n    return load(path), save(path, 'x')\n")
    assert [f["symbol"] for f in rules.io_below_the_boundary(_module(source))] == ["save"]


def test_a_decorator_that_merely_mentions_the_word_is_not_a_declaration():
    """What a decorator does is decided by what it names, not by what it carries. The same
    lesson clause 16 learned from a parametrize holding an exit handler as test data."""
    source = ("@pytest.mark.parametrize('case', ['boundary'])\n"
              "def load(case, path):\n    return path.read_text()\n\n\n"
              "def total(path):\n    return load(path)\n")
    assert rules.io_below_the_boundary(_module(source))
