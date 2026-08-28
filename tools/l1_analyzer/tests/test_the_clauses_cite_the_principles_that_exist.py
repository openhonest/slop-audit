"""Every principle this instrument names is a principle that exists, by its current name.

The Honest Code principles lived in twelve copies holding twenty-two entries between them.
No copy held them all, four numbered them and the rest used headings, and the numbering
differed between the numbered ones. So a citation like "rule 4" resolved to different
principles depending on which copy a reader had, and this package cited eight of them that
way.

They are one repository now, and three were renamed on the day it landed. Nothing detected
the broken citations, here or anywhere, which is what this file is for. It reads the
canonical document when it is present and checks that every principle this package names by
name is in it.

Skipped rather than failed when the document is absent. A checkout without the sibling
repository is an ordinary state, and failing there would report a missing neighbour as a
defect in this code.
"""

import pathlib
import re

import pytest

_CANON = (pathlib.Path(__file__).resolve().parents[4]
          / "honest-code-principles" / "honest-code-principles.md")
_PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "l1_analyzer"

# Named in prose here, and each has to be a heading in the canonical document. Kept as a
# list rather than scraped from the source: a scraper would have to guess which capitalised
# phrase is a citation, and guessing wrong in the quiet direction is how this drifted.
_CITED = (
    "Lookup Polymorphism",
    "Pure Functions Over Methods",
    "I/O at the Boundary",
    "Composition Over Inheritance",
    "Typed Exceptions at the Boundary",
    "Configuration as Parameters",
    "No Implicit Defaults",
    "Dispatch Tables Close Open Input",
)


def _headings() -> set[str]:
    return {line[3:].strip() for line in _CANON.read_text().splitlines()
            if line.startswith("## ")}


@pytest.mark.skipif(not _CANON.is_file(), reason="the principles repository is not checked out here")
@pytest.mark.parametrize("principle", _CITED)
def test_every_principle_this_package_names_exists_under_that_name(principle):
    assert principle in _headings(), (
        f"{principle!r} is cited in this package and is not a heading in the canonical "
        "document; it was renamed or removed")


@pytest.mark.skipif(not _CANON.is_file(), reason="the principles repository is not checked out here")
def test_no_source_file_cites_a_principle_by_number():
    """The numbering was never stable and is now provably not. A number in a citation is a
    reference to whichever copy the writer had open."""
    cited = []
    for path in sorted(_PACKAGE.glob("*.py")):
        for n, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(r"\b[Rr]ules? \d+\b", line):
                cited.append(f"{path.name}:{n}")
    assert cited == [], f"cite the principle by name: {cited}"


@pytest.mark.skipif(not _CANON.is_file(), reason="the principles repository is not checked out here")
def test_every_clause_names_a_principle_that_exists():
    """A clause's name is what a reader compares against the document, so it has to be the
    document's words. Two were stale on the day the principles became one repository:
    Dict-Lookup Polymorphism had become Lookup Polymorphism and Flat Composition had become
    Composition Over Inheritance, and the report kept the old names.

    Clause 2 is the one exception and it is marked rather than renamed. Typed Dicts Over
    Classes was folded into Pure Functions Over Methods upstream; this instrument still
    measures the two halves separately, because a class that only holds data and a method
    that should be a function are different findings with different remedies."""
    from l1_analyzer.honest_code import CLAUSES

    headings = _headings()
    unnamed = [c["name"] for c in CLAUSES
               if c["name"] not in headings and not c["name"].startswith("Pure Functions Over Methods")]
    assert unnamed == [], f"these clause names are not principles: {unnamed}"


@pytest.mark.skipif(not _CANON.is_file(), reason="the principles repository is not checked out here")
def test_the_principles_no_clause_measures_are_named_here():
    """One principle has no clause. Naming it in a test rather than leaving the gap silent,
    so the next person to read this knows what the instrument does not cover.

    It was three on 2026-08-28 and is one. References Resolve Statically and Type
    Declarations Over Imperative Validation both got clauses that day, which is why the
    conformity share stopped being a share of twenty rules over twenty-two principles.

    Constrain AI with Data Shape Contracts is the one left, and it is left deliberately. The
    canon marks it as mitigating a failure rather than eliminating one, so a clause here
    would report a repository for declining a mitigation, which is a different thing from
    breaking a rule.

    The list moves because the document moves, which is why this reads the document.

    A conformity share over the clauses that exist cannot see a principle nobody wrote a
    clause for, which is the same failure this instrument reports in other people's code."""
    from l1_analyzer.honest_code import CLAUSES

    measured = {c["name"] for c in CLAUSES}
    unmeasured = {h for h in _headings()
                  if h not in measured and not h.startswith("Typed Dicts")}
    assert unmeasured == {"Constrain AI with Data Shape Contracts"}, unmeasured
