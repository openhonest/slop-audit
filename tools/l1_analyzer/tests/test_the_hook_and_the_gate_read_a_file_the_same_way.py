"""One file, two callers, and they disagreed about whether it violates a clause.

The clause that reads inheritance excuses a base that is itself a declared shape: a
TypedDict extending a TypedDict declares a record, it does not share an implementation. A
base written in the next file along is the same declaration as one written here, so the
repository-wide run gathers every shape the tree declares before any clause runs.

The write hook did not. It measures one file, so it passed no shapes at all and reported a
record extending a record in a sibling module as inheriting for reuse. The gate, over the
same file, said nothing. The agent that writes the file gets the finding and the commit
that follows does not, so the hook teaches the agent to ignore the hook.

The hook is given a real path on disk, which is a tree it can walk. What it could not do
was the thing it was told not to do, and that reading came from `assess_file_text`, which
takes text and genuinely has no tree. Two entry points, one honest about its limit and one
inheriting the limit without the reason for it.
"""

import pathlib
import tempfile

import pytest
from l1_analyzer import cli, honest_code

_SHAPE = ("from typing import TypedDict\n"
          "\n"
          "\n"
          "class Row(TypedDict):\n"
          "    value: int\n")
_USES_IT = ("from shapes import Row\n"
            "\n"
            "\n"
            "class WideRow(Row):\n"
            "    detail: str\n")


@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t)
        (root / "shapes.py").write_text(_SHAPE)
        (root / "wide.py").write_text(_USES_IT)
        yield root


def _clause_five(assessment) -> list:
    return next(c["findings"] for c in assessment["clauses"] if c["code"] == "L1.21.5")


def test_a_record_extending_a_record_in_the_same_file_is_not_inheriting_for_reuse():
    """The case that always worked, held first so the two below are about where the base
    lives and not about the clause."""
    one_file = _SHAPE + "\n\nclass WideRow(Row):\n    detail: str\n"
    assert _clause_five(honest_code.assess_file_text(one_file, "m.py")) == []


def test_the_hook_does_not_flag_a_base_declared_in_a_sibling_module(repo, capsys):
    """The defect. The hook fires on every write, so a finding it gives that the commit
    does not is worse than no finding at all: it is the one that teaches an agent that this
    output is noise."""
    assert cli._report_honest_code([repo / "wide.py"], "hook") == 0
    assert capsys.readouterr().err == ""


def test_the_hook_still_flags_a_base_that_is_nothing_of_the_kind(repo, capsys):
    """The other direction, because widening a rule is only safe with the case it must not
    reach. A plain class shares an implementation wherever it is written."""
    (repo / "engine.py").write_text("class Engine:\n    def run(self) -> int:\n        return 1\n")
    (repo / "car.py").write_text("from engine import Engine\n\n\nclass Car(Engine):\n"
                                 "    def go(self) -> int:\n        return self.run()\n")
    assert cli._report_honest_code([repo / "car.py"], "hook") == 1
    assert "Engine" in capsys.readouterr().err


def test_a_file_measured_as_text_alone_still_reports_what_it_cannot_follow():
    """The entry point that takes text and no path keeps the old answer, and this holds it
    on purpose. It has genuinely searched no tree, and its emptiness is the true answer
    rather than an oversight to route around."""
    findings = _clause_five(honest_code.assess_file_text(_USES_IT, "wide.py"))
    assert findings


# --------------------------------------------------------------------------
# What the agreement costs, and when
# --------------------------------------------------------------------------

def test_a_file_with_no_base_from_outside_it_does_not_search_the_tree(repo):
    """The hook fires on every write, so the tree search has to be the exception.

    A base is accounted for when it names a declared shape or a class in the same file that
    reaches one, and only what is left sends the reader outside. Two of this package's
    seventy-six modules have such a base."""
    assert honest_code.shapes_around(repo / "shapes.py", _SHAPE) == frozenset()


def test_a_file_with_a_base_from_outside_it_does_search(repo):
    assert "Row" in honest_code.shapes_around(repo / "wide.py", _USES_IT)


def test_every_typed_record_does_not_count_as_a_base_from_outside():
    """The first version of this test was `declares a class with a base`, which every
    TypedDict satisfies: `class Row(TypedDict)` has one. It matched forty-three of the
    seventy-six modules here and paid the walk for most of the package."""
    assert not honest_code._bases_from_elsewhere(_SHAPE, "shapes.py")


def test_a_file_that_will_not_parse_pays_for_the_search(tmp_path):
    """It cannot be read, so it cannot be excused. Skipping the search on a file this could
    not parse would save a second by guessing, and the guess runs in the direction that
    produces a finding."""
    assert honest_code._bases_from_elsewhere("class Broken(:\n", "m.py")
